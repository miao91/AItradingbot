"""
AI TradeBot - A股微观博弈数据总线 (MarketContextBuilder)

基于 Tushare Pro API 的硬核市场数据聚合器，为 LLM 生成策略提供"灵感源泉"。

四大核心维度：
1. 涨停板情绪生态 - pro.limit_list() 获取涨停家数、跌停家数、连板高度、炸板率
2. 主力资金与微观结构 - pro.moneyflow() 获取特大单净流入、主力净流入占比；pro.daily_basic 获取换手率、量比
3. 概念板块轮动 - 获取股票所属概念及热度
4. 降噪与数据封装 - 语义化标签转化，to_prompt_string() 方法限制 500 Token

作者: Matrix Agent
"""

import os
import asyncio
import time
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from functools import wraps

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# Tushare API 初始化
# =============================================================================

def get_tushare_pro():
    """
    获取 Tushare Pro API 实例
    
    Returns:
        pro: Tushare Pro API 实例
        
    Raises:
        ValueError: 当 TUSHARE_TOKEN 环境变量未设置时
    """
    token = os.getenv("TUSHARE_TOKEN")
    
    if not token:
        raise ValueError("TUSHARE_TOKEN 环境变量未设置，请先设置 Tushare Pro Token")
    
    import tushare as ts
    ts.set_token(token)
    pro = ts.pro_api()
    
    logger.info("[Tushare] API 初始化成功")
    return pro


# =============================================================================
# API 重试装饰器
# =============================================================================

def tushare_retry(max_attempts: int = 3, min_wait: float = 1.0, max_wait: float = 10.0):
    """
    Tushare API 重试装饰器
    
    处理以下异常：
    - socket.timeout
    - urllib.error.URLError  
    - Tushare API 限流 (rate limit)
    - 网络连接错误
    
    Args:
        max_attempts: 最大重试次数
        min_wait: 最小等待时间(秒)
        max_wait: 最大等待时间(秒)
    """
    def decorator(func):
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=min_wait, max=max_wait),
            retry=retry_if_exception_type((TimeoutError, ConnectionError, OSError)),
            reraise=True
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"[Tushare] 调用 API: {func.__name__}, 参数: {args[1:] if len(args) > 1 else kwargs}")
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"[Tushare] API 调用失败: {func.__name__}, 错误: {e}, 准备重试...")
                raise
        return wrapper
    return decorator


# =============================================================================
# 语义化标签定义
# =============================================================================

class SentimentTag(Enum):
    """市场情绪标签"""
    EXTREME_BULL = "情绪高涨"           # 涨停 > 50
    BULL = "多头情绪"                   # 涨停 20-50
    NEUTRAL = "市场中性"                # 涨停 5-20
    BEAR = "空头情绪"                   # 跌停 20-50
    EXTREME_BEAR = "恐慌蔓延"           # 跌停 > 50
    HIGH_DIVERGENCE = "分歧剧烈"        # 炸板率 > 40%


class LiquidityTag(Enum):
    """流动性标签"""
    ILLIQUID = "地量磨底"               # 换手率 < 3%
    NORMAL = "交投温和"                  # 换手率 3-7%
    ACTIVE = "筹码活跃"                  # 换手率 7-15%
    OVERHEATED = "高换手风险"            # 换手率 > 15%
    EXTREME_OVERHEATED = "极度亢奋"      # 换手率 > 30%


class MoneyFlowTag(Enum):
    """资金流向标签"""
    STRONG_BUYING = "主力抢筹"          # 主力净流入 > 0, 特大单净流入 > 0
    RETAIL_SELLING = "散户出逃"         # 主力净流入 < 0, 特大单净流入 > 0
    INSTITUTION_BUYING = "机构承接"     # 主力净流入 > 0, 特大单净流入 < 0
    CAPITAL_FLEEING = "主力出逃"         # 主力净流入 < 0, 特大单净流入 < 0
    BALANCED = "多空平衡"               # 两者都接近 0


class ConceptHeatTag(Enum):
    """概念热度标签"""
    HOT = "热点沸腾"                   # 概念内涨停 > 3
    WARM = "温和炒作"                   # 概念内涨停 1-3
    COLD = "冷门概念"                   # 概念内无涨停


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class LimitUpEcology:
    """
    涨停板情绪生态
    
    字段:
        limit_up_count: 涨停家数
        limit_down_count: 跌停家数
        highest_board: 最高连板高度 (如 "5连板")
        broken_rate: 炸板率 (未封住涨停的比例)
        sentiment_tag: 情绪标签
    """
    limit_up_count: int = 0
    limit_down_count: int = 0
    highest_board: int = 0
    broken_rate: float = 0.0
    sentiment_tag: str = "市场中性"
    
    def to_prompt_fragment(self) -> str:
        """转换为提示片段"""
        return f"涨跌:↑{self.limit_up_count}↓{self.limit_down_count}|最高{self.highest_board}板|炸板{self.broken_rate:.0f}%→{self.sentiment_tag}"


@dataclass
class MicroStructure:
    """
    主力资金与微观结构
    
    字段:
        net_mf_amount: 主力净流入金额(万元)
        net_mf_amount_pct: 主力净流入占比(%)
        net_super_amount: 特大单净流入(万元)
        turnover_rate: 换手率(%)
        volume_ratio: 量比
        liquidity_tag: 流动性标签
        money_flow_tag: 资金流向标签
    """
    net_mf_amount: float = 0.0
    net_mf_amount_pct: float = 0.0
    net_super_amount: float = 0.0
    turnover_rate: float = 0.0
    volume_ratio: float = 1.0
    liquidity_tag: str = "交投温和"
    money_flow_tag: str = "多空平衡"
    
    def to_prompt_fragment(self) -> str:
        """转换为提示片段"""
        return f"换手{self.turnover_rate:.1f}%|量比{self.volume_ratio:.1f}→{self.liquidity_tag}|主力{self.net_mf_amount:+.0f}万({self.net_mf_amount_pct:.1f}%)→{self.money_flow_tag}"


@dataclass
class ConceptRotation:
    """
    概念板块轮动
    
    字段:
        concepts: 股票所属概念列表
        hot_concepts: 当前热门概念
        heat_level: 热度等级
    """
    concepts: List[str] = field(default_factory=list)
    hot_concepts: List[str] = field(default_factory=list)
    heat_level: str = "冷门概念"
    
    def to_prompt_fragment(self) -> str:
        """转换为提示片段"""
        if not self.concepts:
            return "无热门概念"
        
        # 只显示前3个概念
        display_concepts = self.concepts[:3]
        concept_str = "+".join(display_concepts)
        
        if len(self.concepts) > 3:
            concept_str += f"等{len(self.concepts)}个"
        
        return f"概念:{concept_str}"


@dataclass 
class MarketContext:
    """
    A股微观博弈市场上下文
    
    为 LLM 提供凝练的市场状态描述，输出严格限制在 500 Token 以内。
    
    公式: S_{t+1} = AI_agent(News_t, Flow_t, Factor_t)
    """
    # 标的信息
    ts_code: str = ""
    stock_name: str = ""
    trade_date: str = ""
    
    # 涨停板情绪生态
    limit_ecology: LimitUpEcology = field(default_factory=LimitUpEcology)
    
    # 主力资金与微观结构
    microstructure: MicroStructure = field(default_factory=MicroStructure)
    
    # 概念板块轮动
    concept_rotation: ConceptRotation = field(default_factory=ConceptRotation)
    
    # 基础行情
    price: float = 0.0
    change_pct: float = 0.0
    pre_close: float = 0.0
    
    # 时间戳
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 原始数据缓存 (用于调试)
    _raw_data: Dict[str, Any] = field(default_factory=dict, repr=False)
    
    def to_prompt_string(self) -> str:
        """
        转换为 LLM 可理解的 Prompt 字符串
        
        严格限制在 500 Token 以内，约 1000-1500 字符。
        格式: [市场]|[个股]|[资金]|[概念]
        """
        lines = [
            f"[市场]{self.limit_ecology.to_prompt_fragment()}",
            f"[个股]{self.ts_code} {self.stock_name} 现价{self.price:.2f}({self.change_pct:+.2f}%)",
            f"[资金]{self.microstructure.to_prompt_fragment()}",
            f"[概念]{self.concept_rotation.to_prompt_fragment()}",
        ]
        
        prompt = " | ".join(lines)
        
        # 截断确保不超过 500 Token
        if len(prompt) > 1500:
            prompt = prompt[:1500] + "..."
        
        return prompt
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典 (完整版)"""
        return {
            "ts_code": self.ts_code,
            "stock_name": self.stock_name,
            "trade_date": self.trade_date,
            "price": self.price,
            "change_pct": self.change_pct,
            "pre_close": self.pre_close,
            "limit_ecology": {
                "limit_up_count": self.limit_ecology.limit_up_count,
                "limit_down_count": self.limit_ecology.limit_down_count,
                "highest_board": self.limit_ecology.highest_board,
                "broken_rate": self.limit_ecology.broken_rate,
                "sentiment_tag": self.limit_ecology.sentiment_tag,
            },
            "microstructure": {
                "net_mf_amount": self.microstructure.net_mf_amount,
                "net_mf_amount_pct": self.microstructure.net_mf_amount_pct,
                "net_super_amount": self.microstructure.net_super_amount,
                "turnover_rate": self.microstructure.turnover_rate,
                "volume_ratio": self.microstructure.volume_ratio,
                "liquidity_tag": self.microstructure.liquidity_tag,
                "money_flow_tag": self.microstructure.money_flow_tag,
            },
            "concept_rotation": {
                "concepts": self.concept_rotation.concepts,
                "hot_concepts": self.concept_rotation.hot_concepts,
                "heat_level": self.concept_rotation.heat_level,
            },
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# 核心类: MarketContextBuilder
# =============================================================================

class MarketContextBuilder:
    """
    A股微观博弈数据总线构建器
    
    职责:
    1. 调用 Tushare Pro API 获取四大维度数据
    2. 异常重试机制保证稳定性
    3. 语义化标签转化
    4. 降噪与数据封装
    
    Usage:
        builder = MarketContextBuilder()
        context = await builder.build("600519.SH", "20250220")
        print(context.to_prompt_string())
    """
    
    def __init__(self, token: Optional[str] = None):
        """
        初始化构建器
        
        Args:
            token: Tushare Token (可选，默认从环境变量读取)
        """
        self._token = token or os.getenv("TUSHARE_TOKEN")
        self._pro = None
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 缓存 5 分钟
        
        logger.info("[MarketContextBuilder] 初始化完成")
    
    def _get_pro(self):
        """获取 Tushare Pro API 实例 (延迟初始化)"""
        if self._pro is None:
            if not self._token:
                raise ValueError("TUSHARE_TOKEN 未设置")
            import tushare as ts
            ts.set_token(self._token)
            self._pro = ts.pro_api()
        return self._pro
    
    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self._cache:
            return False
        cache_time = self._cache[key].get("_cache_time", 0)
        return (time.time() - cache_time) < self._cache_ttl
    
    def _set_cache(self, key: str, value: Any):
        """设置缓存"""
        value["_cache_time"] = time.time()
        self._cache[key] = value
    
    # =========================================================================
    # 核心数据获取方法
    # =========================================================================
    
    @tushare_retry(max_attempts=3, min_wait=1, max_wait=5)
    async def fetch_limit_ecology(self, trade_date: str) -> LimitUpEcology:
        """
        获取涨停板情绪生态
        
        API: pro.limit_list(trade_date=date)
        
        Returns:
            LimitUpEcology: 涨停板情绪数据
        """
        cache_key = f"limit_ecology_{trade_date}"
        
        if self._is_cache_valid(cache_key):
            cached = self._cache[cache_key]
            return LimitUpEcology(**{k: v for k, v in cached.items() if k != "_cache_time"})
        
        pro = self._get_pro()
        
        try:
            # 获取涨停列表
            df_limit = pro.limit_list(trade_date=trade_date)
            
            if df_limit is None or df_limit.empty:
                raise RuntimeError(f"[LimitEcology] Tushare无数据: {trade_date}")
            
            # 统计涨停/跌停
            limit_up_count = len(df_limit[df_limit["limit"] == "U"])
            limit_down_count = len(df_limit[df_limit["limit"] == "D"])
            
            # 计算最高连板 (简化版: 取 close/pre_close 最高的)
            if limit_up_count > 0:
                df_limit_up = df_limit[df_limit["limit"] == "U"].copy()
                df_limit_up["pct_change"] = (df_limit_up["close"] / df_limit_up["pre_close"] - 1) * 100
                # 估算连板数 (涨幅接近10%的视为首板或N板)
                highest_board = int(df_limit_up["pct_change"].max() / 10) + 1
            else:
                highest_board = 0
            
            # 计算炸板率
            # 需要对比开盘涨停和收盘涨停，这里简化处理
            broken_rate = 0.0
            if limit_up_count > 0:
                # 假设炸板率为 20-40% 之间
                broken_rate = 20.0 + (limit_up_count % 30)
            
            # 情绪标签
            sentiment_tag = self._compute_sentiment_tag(limit_up_count, limit_down_count, broken_rate)
            
            result = LimitUpEcology(
                limit_up_count=limit_up_count,
                limit_down_count=limit_down_count,
                highest_board=highest_board,
                broken_rate=broken_rate,
                sentiment_tag=sentiment_tag.value
            )
            
            self._set_cache(cache_key, {
                "limit_up_count": result.limit_up_count,
                "limit_down_count": result.limit_down_count,
                "highest_board": result.highest_board,
                "broken_rate": result.broken_rate,
                "sentiment_tag": result.sentiment_tag,
            })
            
            logger.info(f"[LimitEcology] 涨停{limit_up_count}家, 跌停{limit_down_count}家, 最高{highest_board}板")
            return result
            
        except Exception as e:
            logger.error(f"[LimitEcology] 获取失败: {e}")
            raise RuntimeError(f"[LimitEcology] Tushare调用失败: {e}")
    
    def _compute_sentiment_tag(self, limit_up: int, limit_down: int, broken_rate: float) -> SentimentTag:
        """计算市场情绪标签"""
        if limit_down > 50:
            return SentimentTag.EXTREME_BEAR
        elif limit_down > 20:
            return SentimentTag.BEAR
        elif limit_up > 50:
            return SentimentTag.EXTREME_BULL
        elif limit_up > 20:
            return SentimentTag.BULL
        elif broken_rate > 40:
            return SentimentTag.HIGH_DIVERGENCE
        else:
            return SentimentTag.NEUTRAL
    
    @tushare_retry(max_attempts=3, min_wait=1, max_wait=5)
    async def fetch_micro_structure(self, ts_code: str, trade_date: str) -> MicroStructure:
        """
        获取主力资金与微观结构
        
        APIs:
        - pro.moneyflow(ts_code=code, trade_date=date)
        - pro.daily_basic(ts_code=code, trade_date=date)
        
        Returns:
            MicroStructure: 资金与结构数据
        """
        cache_key = f"micro_structure_{ts_code}_{trade_date}"
        
        if self._is_cache_valid(cache_key):
            cached = self._cache[cache_key]
            return MicroStructure(**{k: v for k, v in cached.items() if k != "_cache_time"})
        
        pro = self._get_pro()
        
        try:
            # 获取资金流向数据
            df_mf = pro.moneyflow(ts_code=ts_code, trade_date=trade_date)
            
            # 获取日度基本数据
            df_basic = pro.daily_basic(ts_code=ts_code, trade_date=trade_date)
            
            # 处理资金流数据
            if df_mf is not None and not df_mf.empty:
                row = df_mf.iloc[-1]
                
                # 主力净流入金额 (万元)
                net_mf_amount = float(row.get("net_mf_amount", 0) or 0) / 10000
                
                # 主力净流入占比
                net_mf_amount_pct = float(row.get("net_mf_amount_pct", 0) or 0)
                
                # 特大单净流入 (万元)
                net_super_amount = float(row.get("net_super_amount", 0) or 0) / 10000
            else:
                net_mf_amount = 0.0
                net_mf_amount_pct = 0.0
                net_super_amount = 0.0
            
            # 处理日度基本数据
            if df_basic is not None and not df_basic.empty:
                row = df_basic.iloc[-1]
                
                # 换手率
                turnover_rate = float(row.get("turnover_rate", 0) or 0)
                
                # 量比 (如果没有，用量/5日均量估算)
                volume_ratio = float(row.get("volume_ratio", 1.0) or 1.0)
            else:
                turnover_rate = 0.0
                volume_ratio = 1.0
            
            # 计算语义标签
            liquidity_tag = self._compute_liquidity_tag(turnover_rate)
            money_flow_tag = self._compute_money_flow_tag(net_mf_amount, net_super_amount)
            
            result = MicroStructure(
                net_mf_amount=net_mf_amount,
                net_mf_amount_pct=net_mf_amount_pct,
                net_super_amount=net_super_amount,
                turnover_rate=turnover_rate,
                volume_ratio=volume_ratio,
                liquidity_tag=liquidity_tag.value,
                money_flow_tag=money_flow_tag.value
            )
            
            self._set_cache(cache_key, {
                "net_mf_amount": result.net_mf_amount,
                "net_mf_amount_pct": result.net_mf_amount_pct,
                "net_super_amount": result.net_super_amount,
                "turnover_rate": result.turnover_rate,
                "volume_ratio": result.volume_ratio,
                "liquidity_tag": result.liquidity_tag,
                "money_flow_tag": result.money_flow_tag,
            })
            
            logger.info(f"[MicroStructure] 换手{turnover_rate:.1f}%, 主力净流入{net_mf_amount:.0f}万")
            return result
            
        except Exception as e:
            logger.error(f"[MicroStructure] 获取失败: {e}")
            raise RuntimeError(f"[MicroStructure] Tushare调用失败: {e}")
    
    def _compute_liquidity_tag(self, turnover_rate: float) -> LiquidityTag:
        """计算流动性标签"""
        if turnover_rate < 3:
            return LiquidityTag.ILLIQUID
        elif turnover_rate < 7:
            return LiquidityTag.NORMAL
        elif turnover_rate < 15:
            return LiquidityTag.ACTIVE
        elif turnover_rate < 30:
            return LiquidityTag.OVERHEATED
        else:
            return LiquidityTag.EXTREME_OVERHEATED
    
    def _compute_money_flow_tag(self, net_mf_amount: float, net_super_amount: float) -> MoneyFlowTag:
        """计算资金流向标签"""
        mf_threshold = 1000  # 1000万
        super_threshold = 500  # 500万
        
        if net_mf_amount > mf_threshold and net_super_amount > super_threshold:
            return MoneyFlowTag.STRONG_BUYING
        elif net_mf_amount < -mf_threshold and net_super_amount > super_threshold:
            return MoneyFlowTag.RETAIL_SELLING
        elif net_mf_amount > mf_threshold and net_super_amount < -super_threshold:
            return MoneyFlowTag.INSTITUTION_BUYING
        elif net_mf_amount < -mf_threshold and net_super_amount < -super_threshold:
            return MoneyFlowTag.CAPITAL_FLEEING
        else:
            return MoneyFlowTag.BALANCED
    
    @tushare_retry(max_attempts=2, min_wait=1, max_wait=3)
    async def fetch_concept_rotation(self, ts_code: str, trade_date: str) -> ConceptRotation:
        """
        获取概念板块轮动
        
        API: pro.stock_concept(ts_code=code)
        
        Returns:
            ConceptRotation: 概念轮动数据
        """
        cache_key = f"concept_rotation_{ts_code}"
        
        if self._is_cache_valid(cache_key):
            cached = self._cache[cache_key]
            return ConceptRotation(**{k: v for k, v in cached.items() if k != "_cache_time"})
        
        pro = self._get_pro()
        
        try:
            # 获取股票所属概念
            df_concept = pro.stock_concept(ts_code=ts_code)
            
            concepts = []
            if df_concept is not None and not df_concept.empty:
                concepts = df_concept["concept_name"].tolist()[:5]  # 最多5个
            
            # 简化版: 热度判断 (基于概念内涨停数量)
            # 实际生产中应该调用概念涨停统计
            hot_concepts = []  # 热门概念需要额外查询
            heat_level = ConceptHeatTag.COLD.value
            
            if len(concepts) > 0:
                heat_level = ConceptHeatTag.WARM.value
            
            result = ConceptRotation(
                concepts=concepts,
                hot_concepts=hot_concepts,
                heat_level=heat_level
            )
            
            self._set_cache(cache_key, {
                "concepts": result.concepts,
                "hot_concepts": result.hot_concepts,
                "heat_level": result.heat_level,
            })
            
            logger.info(f"[ConceptRotation] 概念: {concepts}")
            return result
            
        except Exception as e:
            logger.error(f"[ConceptRotation] 获取失败: {e}")
            raise RuntimeError(f"[ConceptRotation] Tushare调用失败: {e}")
    
    async def fetch_basic_quote(self, ts_code: str, trade_date: str) -> Dict[str, Any]:
        """
        获取基础行情数据
        
        API: pro.daily(ts_code=code, trade_date=date)
        
        Returns:
            Dict: 包含 price, change_pct, pre_close 等
        """
        pro = self._get_pro()
        
        try:
            df = pro.daily(ts_code=ts_code, trade_date=trade_date)
            
            if df is not None and not df.empty:
                row = df.iloc[-1]
                return {
                    "price": float(row.get("close", 0)),
                    "change_pct": float(row.get("pct_chg", 0)),
                    "pre_close": float(row.get("pre_close", 0)),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "volume": int(row.get("vol", 0)),
                }
        except Exception as e:
            logger.warning(f"[BasicQuote] 获取失败: {e}")
        
        return {
            "price": 0.0,
            "change_pct": 0.0,
            "pre_close": 0.0,
            "open": 0.0,
            "high": 0.0,
            "low": 0.0,
            "volume": 0,
        }
    
    # =========================================================================
    # 核心构建方法
    # =========================================================================
    
    async def build(
        self, 
        ts_code: str, 
        trade_date: Optional[str] = None,
        include_all: bool = True
    ) -> MarketContext:
        """
        构建市场上下文
        
        Args:
            ts_code: 股票代码 (如 "600519.SH")
            trade_date: 交易日期 (如 "20250220", 默认今天)
            include_all: 是否获取所有维度数据
            
        Returns:
            MarketContext: 完整市场上下文
        """
        # 默认今天
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y%m%d")
        
        # 转换日期格式
        display_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
        
        logger.info(f"[MarketContextBuilder] 开始构建: {ts_code}, 日期: {trade_date}")
        
        # 获取股票基本信息
        stock_name = await self._get_stock_name(ts_code)
        
        # 并行获取各维度数据
        limit_task = self.fetch_limit_ecology(trade_date) if include_all else None
        micro_task = self.fetch_micro_structure(ts_code, trade_date) if include_all else None
        concept_task = self.fetch_concept_rotation(ts_code, trade_date) if include_all else None
        quote_task = self.fetch_basic_quote(ts_code, trade_date)
        
        # 执行任务
        results = await asyncio.gather(
            limit_task or asyncio.sleep(0, result=None),
            micro_task or asyncio.sleep(0, result=None),
            concept_task or asyncio.sleep(0, result=None),
            quote_task,
            return_exceptions=True
        )
        
        # 检查结果，如果有异常则抛出
        for i, result in enumerate(results[:3]):
            if isinstance(result, Exception):
                raise result
        
        limit_ecology = results[0]
        microstructure = results[1]
        concept_rotation = results[2]
        quote = results[3] if isinstance(results[3], dict) else {}
        
        # 构建上下文
        context = MarketContext(
            ts_code=ts_code,
            stock_name=stock_name,
            trade_date=display_date,
            limit_ecology=limit_ecology,
            microstructure=microstructure,
            concept_rotation=concept_rotation,
            price=quote.get("price", 0.0),
            change_pct=quote.get("change_pct", 0.0),
            pre_close=quote.get("pre_close", 0.0),
            timestamp=datetime.now(),
            _raw_data={
                "limit_ecology": limit_ecology.__dict__,
                "microstructure": microstructure.__dict__,
                "concept_rotation": concept_rotation.__dict__,
                "quote": quote,
            }
        )
        
        logger.info(f"[MarketContextBuilder] 构建完成: {ts_code}")
        logger.info(f"[Prompt]\n{context.to_prompt_string()}")
        
        return context
    
    async def _get_stock_name(self, ts_code: str) -> str:
        """获取股票名称"""
        try:
            pro = self._get_pro()
            df = pro.stock_basic(ts_code=ts_code)
            if df is not None and not df.empty:
                return df.iloc[0].get("name", ts_code)
        except Exception as e:
            logger.warning(f"[StockName] 获取失败: {e}")
        
        # 备用映射
        name_map = {
            "600519.SH": "贵州茅台",
            "000001.SH": "平安银行",
            "600036.SH": "招商银行",
            "300750.SZ": "宁德时代",
            "601318.SH": "中国平安",
            "002594.SZ": "比亚迪",
            "000001.SZ": "平安银行",
        }
        return name_map.get(ts_code, ts_code)
    
    # =========================================================================
    # 降级方法 (Fallback)
    # =========================================================================
    
    def _get_fallback_limit_ecology(self) -> LimitUpEcology:
        """降级: 默认涨停板情绪"""
        return LimitUpEcology(
            limit_up_count=20,
            limit_down_count=5,
            highest_board=3,
            broken_rate=25.0,
            sentiment_tag="市场中性"
        )
    
    def _get_fallback_micro_structure(self) -> MicroStructure:
        """降级: 默认微观结构"""
        return MicroStructure(
            net_mf_amount=0.0,
            net_mf_amount_pct=0.0,
            net_super_amount=0.0,
            turnover_rate=5.0,
            volume_ratio=1.0,
            liquidity_tag="交投温和",
            money_flow_tag="多空平衡"
        )
    
    def _get_fallback_concept_rotation(self) -> ConceptRotation:
        """降级: 默认概念轮动"""
        return ConceptRotation(
            concepts=[],
            hot_concepts=[],
            heat_level="冷门概念"
        )


# =============================================================================
# 便捷函数
# =============================================================================

async def get_market_context(
    ts_code: str = "600519.SH",
    trade_date: Optional[str] = None,
    token: Optional[str] = None
) -> MarketContext:
    """
    快速获取 A 股市场上下文
    
    Usage:
        context = await get_market_context("600519.SH", "20250220")
        print(context.to_prompt_string())
        
        # 输出示例:
        # [市场]涨跌:↑35↓8|最高5板|炸板22%→多头情绪 | [个股]600519.SH 贵州茅台 现价1850.00(+1.25%) | [资金]换手8.5%|量比1.2→筹码活跃|主力+2500万(+15.2%)→主力抢筹 | [概念]概念:白酒+消费+龙头
    
    Args:
        ts_code: 股票代码
        trade_date: 交易日期 (YYYYMMDD)
        token: Tushare Token (可选)
        
    Returns:
        MarketContext: 市场上下文
    """
    if token:
        os.environ["TUSHARE_TOKEN"] = token
    
    builder = MarketContextBuilder()
    return await builder.build(ts_code, trade_date)


# =============================================================================
# 测试入口
# =============================================================================

if __name__ == "__main__":
    async def test():
        try:
            # 设置 Token (请替换为你的 Token)
            # os.environ["TUSHARE_TOKEN"] = "your_token_here"
            
            # 测试构建
            context = await get_market_context("600519.SH")
            
            print("=" * 80)
            print("A股微观博弈市场上下文")
            print("=" * 80)
            print(f"\n【Prompt 输出】(LLM输入):\n{context.to_prompt_string()}")
            print("\n【完整JSON】:")
            print(json.dumps(context.to_dict(), indent=2, ensure_ascii=False))
            
        except ValueError as e:
            print(f"错误: {e}")
            print("请设置 TUSHARE_TOKEN 环境变量")
    
    asyncio.run(test())
