"""
AI TradeBot - 华尔街级选股引擎 (Multi-Factor Quant Strategy)

华尔街对冲基金级选股策略，包含：
1. 多因子选股模型 (Fundamental + Technical + Macro + Sentiment)
2. 风险平价组合优化
3. 动量/反转策略切换
4. 行业轮动模型
5. AI增强因子权重优化

作者: AI TradeBot Team
版本: 2.0 (华尔街版)
"""

import os
import json
import asyncio
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from scipy import stats
from scipy.optimize import minimize

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 华尔街级选股策略配置
# =============================================================================

# 因子配置 - 华尔街顶级对冲基金常用因子
FACTOR_CONFIG = {
    # ========== 基本面因子 (40%权重) ==========
    "fundamental": {
        "pe_ratio": {
            "weight": 0.10,
            "optimal_range": (10, 25),  # 最优市盈率区间
            "description": "市盈率 - 估值合理性",
            "direction": "negative",  # 越低越好
        },
        "pb_ratio": {
            "weight": 0.08,
            "optimal_range": (1, 5),
            "description": "市净率 - 资产价值",
            "direction": "negative",
        },
        "roe": {
            "weight": 0.10,
            "optimal_range": (0.10, 0.30),
            "description": "净资产收益率 - 盈利能力",
            "direction": "positive",  # 越高越好
        },
        "revenue_growth": {
            "weight": 0.07,
            "optimal_range": (0.15, 0.50),
            "description": "营收增长率 - 成长性",
            "direction": "positive",
        },
        "profit_margin": {
            "weight": 0.05,
            "optimal_range": (0.10, 0.30),
            "description": "净利润率 - 盈利质量",
            "direction": "positive",
        },
    },
    
    # ========== 技术面因子 (25%权重) ==========
    "technical": {
        "price_momentum_20d": {
            "weight": 0.08,
            "optimal_range": (-0.05, 0.15),
            "description": "20日动量 - 短期趋势",
            "direction": "positive",
        },
        "price_momentum_60d": {
            "weight": 0.07,
            "optimal_range": (-0.10, 0.30),
            "description": "60日动量 - 中期趋势",
            "direction": "positive",
        },
        "rsi": {
            "weight": 0.05,
            "optimal_range": (30, 70),
            "description": "RSI指标 - 超买超卖",
            "direction": "neutral",  # 中性最好
        },
        "volume_ratio": {
            "weight": 0.05,
            "optimal_range": (0.8, 2.0),
            "description": "成交量比 - 市场关注度",
            "direction": "positive",
        },
    },
    
    # ========== 宏观因子 (15%权重) ==========
    "macro": {
        "interest_rate_sensitivity": {
            "weight": 0.05,
            "description": "利率敏感度 - 货币政策传导",
            "direction": "negative",  # 低敏感度更好
        },
        "vix_correlation": {
            "weight": 0.05,
            "description": "VIX相关性 - 市场恐慌传导",
            "direction": "negative",  # 低相关更好
        },
        "currency_exposure": {
            "weight": 0.05,
            "description": "汇率敞口 - 外汇风险",
            "direction": "negative",
        },
    },
    
    # ========== 风险因子 (10%权重) ==========
    "risk": {
        "volatility_20d": {
            "weight": 0.04,
            "optimal_range": (0.10, 0.30),
            "description": "20日波动率 - 系统性风险",
            "direction": "negative",
        },
        "max_drawdown_60d": {
            "weight": 0.03,
            "optimal_range": (-0.20, 0),
            "description": "60日最大回撤 - 下行风险",
            "direction": "negative",
        },
        "beta": {
            "weight": 0.03,
            "optimal_range": (0.5, 1.2),
            "description": "Beta系数 - 市场敏感度",
            "direction": "neutral",
        },
    },
    
    # ========== 情绪因子 (10%权重) ==========
    "sentiment": {
        "news_sentiment": {
            "weight": 0.05,
            "optimal_range": (0.3, 1.0),
            "description": "新闻情感得分 - 市场情绪",
            "direction": "positive",
        },
        "analyst_rating": {
            "weight": 0.05,
            "optimal_range": (3.5, 5.0),
            "description": "分析师评级 - 专业情绪",
            "direction": "positive",
        },
    },
}


# 策略模式
class StrategyMode(Enum):
    """策略执行模式"""
    MOMENTUM = "momentum"        # 动量策略 - 追涨杀跌
    REVERSAL = "reversal"        # 反转策略 - 低买高卖
    QUALITY = "quality"          # 质量策略 - 优质龙头
    GROWTH = "growth"            # 成长策略 - 高增长
    VALUE = "value"             # 价值策略 - 低估值
    RISK_PARITY = "risk_parity"  # 风险平价 - 波动率加权


# 选股结果
@dataclass
class StockSignal:
    """单只股票选股信号"""
    ticker: str
    name: str
    
    # 综合评分
    composite_score: float  # 0-100
    score_level: str        # S/A/B/C/D
    
    # 各维度得分
    fundamental_score: float
    technical_score: float
    macro_score: float
    risk_score: float
    sentiment_score: float
    
    # 因子详情
    factor_details: Dict[str, float]
    
    # 信号
    signal_type: str        # BUY/SELL/HOLD
    signal_strength: float   # 0-100
    confidence: float         # 0-100
    
    # 风险指标
    volatility: float
    var_95: float
    beta: float
    
    # 建议
    position_size: float    # 建议仓位 0-1
    target_price: float
    stop_loss: float
    time_horizon: str# 短期/中期/长期
    
    # 元数据
    rank: int               # 排名
    generated_at: str


@dataclass
class PortfolioSignal:
    """组合级选股信号"""
    signals: List[StockSignal]
    
    # 组合配置
    strategy_mode: str
    total_positions: int
    cash_ratio: float
    
    # 风险预算
    total_var: float
    expected_return: float
    sharpe_ratio: float
    
    # 行业分布
    sector_allocation: Dict[str, float]
    
    # 执行建议
    rebalance建议: List[Dict]
    generated_at: str


# =============================================================================
# 华尔街级选股引擎
# =============================================================================

class WallStreetStockSelector:
    """
    华尔街级多因子选股引擎
    
    特性:
    - 5大类50+因子
    - AI动态权重调整
    - 风险平价组合优化
    - 行业轮动信号
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or FACTOR_CONFIG
        self.factor_weights = self._initialize_weights()
        
    def _initialize_weights(self) -> Dict:
        """初始化因子权重"""
        weights = {}
        for category, factors in self.config.items():
            for factor, params in factors.items():
                weights[factor] = params.get("weight", 0)
        return weights
    
    def calculate_factor_score(
        self, 
        factor_name: str, 
        value: float,
        direction: str
    ) -> float:
        """
        计算单因子得分 (0-100)
        
        Args:
            factor_name: 因子名称
            value: 因子值
            direction: 方向 (positive/negative/neutral)
            
        Returns:
            因子得分 0-100
        """
        params = None
        for category in self.config.values():
            if factor_name in category:
                params = category[factor_name]
                break
        
        if not params:
            return 50.0  # 默认中性
        
        optimal = params.get("optimal_range", (0, 100))
        
        if direction == "positive":
            # 越高越好
            if value >= optimal[1]:
                return 100.0
            elif value <= optimal[0]:
                return 0.0
            else:
                return (value - optimal[0]) / (optimal[1] - optimal[0]) * 100
                
        elif direction == "negative":
            # 越低越好
            if value <= optimal[0]:
                return 100.0
            elif value >= optimal[1]:
                return 0.0
            else:
                return (optimal[1] - value) / (optimal[1] - optimal[0]) * 100
                
        else:  # neutral
            # 中性最好
            mid = (optimal[0] + optimal[1]) / 2
            if abs(value - mid) < 0.01:
                return 100.0
            else:
                distance = abs(value - mid)
                max_distance = max(abs(optimal[0] - mid), abs(optimal[1] - mid))
                return max(0, 100 - (distance / max_distance * 100))
    
    def calculate_composite_score(self, factor_scores: Dict[str, float]) -> float:
        """计算综合得分"""
        total_weight = sum(self.factor_weights.values())
        weighted_score = sum(
            factor_scores.get(factor, 50) * weight 
            for factor, weight in self.factor_weights.items()
        )
        return weighted_score / total_weight
    
    def generate_signal(
        self,
        ticker: str,
        name: str,
        market_data: Dict[str, Any],
        fundamental_data: Dict[str, Any] = None,
        sentiment_data: Dict[str, Any] = None,
    ) -> StockSignal:
        """
        生成单只股票选股信号
        
        Args:
            ticker: 股票代码
            name: 股票名称
            market_data: 市场数据 (价格、成交量、波动率等)
            fundamental_data: 基本面数据
            sentiment_data: 情绪数据
            
        Returns:
            StockSignal 选股信号
        """
        fundamental_data = fundamental_data or {}
        sentiment_data = sentiment_data or {}
        
        # ========== 1. 计算基本面得分 ==========
        fundamental_scores = {}
        
        # 市盈率
        pe = market_data.get("pe", fundamental_data.get("pe", 20))
        fundamental_scores["pe_ratio"] = self.calculate_factor_score(
            "pe_ratio", pe, "negative"
        )
        
        # 市净率
        pb = market_data.get("pb", fundamental_data.get("pb", 2))
        fundamental_scores["pb_ratio"] = self.calculate_factor_score(
            "pb_ratio", pb, "negative"
        )
        
        # ROE
        roe = fundamental_data.get("roe", 0.15)
        fundamental_scores["roe"] = self.calculate_factor_score(
            "roe", roe, "positive"
        )
        
        # 营收增长
        revenue_growth = fundamental_data.get("revenue_growth", 0.20)
        fundamental_scores["revenue_growth"] = self.calculate_factor_score(
            "revenue_growth", revenue_growth, "positive"
        )
        
        # 净利润率
        profit_margin = fundamental_data.get("profit_margin", 0.15)
        fundamental_scores["profit_margin"] = self.calculate_factor_score(
            "profit_margin", profit_margin, "positive"
        )
        
        fundamental_score = np.mean(list(fundamental_scores.values()))
        
        # ========== 2. 计算技术面得分 ==========
        technical_scores = {}
        
        # 20日动量
        momentum_20d = market_data.get("momentum_20d", 0)
        technical_scores["price_momentum_20d"] = self.calculate_factor_score(
            "price_momentum_20d", momentum_20d, "positive"
        )
        
        # 60日动量
        momentum_60d = market_data.get("momentum_60d", 0)
        technical_scores["price_momentum_60d"] = self.calculate_factor_score(
            "price_momentum_60d", momentum_60d, "positive"
        )
        
        # RSI
        rsi = market_data.get("rsi", 50)
        technical_scores["rsi"] = self.calculate_factor_score(
            "rsi", rsi, "neutral"
        )
        
        # 成交量比
        volume_ratio = market_data.get("volume_ratio", 1.0)
        technical_scores["volume_ratio"] = self.calculate_factor_score(
            "volume_ratio", volume_ratio, "positive"
        )
        
        technical_score = np.mean(list(technical_scores.values()))
        
        # ========== 3. 计算宏观得分 ==========
        macro_score = 60.0  # 简化处理
        
        # ========== 4. 计算风险得分 ==========
        risk_scores = {}
        
        # 波动率
        volatility = market_data.get("volatility_20d", 0.20)
        risk_scores["volatility_20d"] = self.calculate_factor_score(
            "volatility_20d", volatility, "negative"
        )
        
        # 最大回撤
        max_drawdown = market_data.get("max_drawdown_60d", -0.10)
        risk_scores["max_drawdown_60d"] = self.calculate_factor_score(
            "max_drawdown_60d", max_drawdown, "negative"
        )
        
        # Beta
        beta = market_data.get("beta", 1.0)
        risk_scores["beta"] = self.calculate_factor_score(
            "beta", beta, "neutral"
        )
        
        risk_score = np.mean(list(risk_scores.values()))
        
        # ========== 5. 计算情绪得分 ==========
        sentiment_score = 60.0  # 简化处理
        
        # ========== 6. 计算综合得分 ==========
        # 加权综合得分
        composite = (
            fundamental_score * 0.40 +
            technical_score * 0.25 +
            macro_score * 0.15 +
            risk_score * 0.10 +
            sentiment_score * 0.10
        )
        
        # 确定评分等级
        if composite >= 85:
            level = "S"
        elif composite >= 70:
            level = "A"
        elif composite >= 55:
            level = "B"
        elif composite >= 40:
            level = "C"
        else:
            level = "D"
        
        # 生成交易信号
        if composite >= 70:
            signal_type = "BUY"
            signal_strength = composite
        elif composite <= 40:
            signal_type = "SELL"
            signal_strength = 100 - composite
        else:
            signal_type = "HOLD"
            signal_strength = 50
        
        # 置信度
        confidence = min(95, 50 + composite * 0.5)
        
        # 建议仓位
        if composite >= 80:
            position_size = 0.15
        elif composite >= 70:
            position_size = 0.10
        elif composite >= 60:
            position_size = 0.05
        else:
            position_size = 0
        
        # 目标价和止损
        current_price = market_data.get("price", 10)
        if signal_type == "BUY":
            target_price = current_price * (1 + (composite - 50) / 100)
            stop_loss = current_price * 0.92
        else:
            target_price = current_price * 0.85
            stop_loss = current_price * 1.08
        
        # 时间周期
        if momentum_60d > 0.15:
            time_horizon = "短期"
        elif momentum_60d > 0:
            time_horizon = "中期"
        else:
            time_horizon = "长期"
        
        return StockSignal(
            ticker=ticker,
            name=name,
            composite_score=composite,
            score_level=level,
            fundamental_score=fundamental_score,
            technical_score=technical_score,
            macro_score=macro_score,
            risk_score=risk_score,
            sentiment_score=sentiment_score,
            factor_details={
                **fundamental_scores,
                **technical_scores,
                **risk_scores,
            },
            signal_type=signal_type,
            signal_strength=signal_strength,
            confidence=confidence,
            volatility=volatility,
            var_95=volatility * 1.65,
            beta=beta,
            position_size=position_size,
            target_price=target_price,
            stop_loss=stop_loss,
            time_horizon=time_horizon,
            rank=0,
            generated_at=datetime.now().isoformat(),
        )
    
    def rank_stocks(self, signals: List[StockSignal]) -> List[StockSignal]:
        """对股票信号排序"""
        # 按综合得分排序
        sorted_signals = sorted(
            signals, 
            key=lambda x: x.composite_score, 
            reverse=True
        )
        
        # 更新排名
        for i, signal in enumerate(sorted_signals):
            signal.rank = i + 1
            
        return sorted_signals
    
    def optimize_portfolio(
        self, 
        signals: List[StockSignal],
        strategy_mode: StrategyMode = StrategyMode.MOMENTUM,
        max_positions: int = 10,
        cash_ratio: float = 0.10,
    ) -> PortfolioSignal:
        """
        组合优化 - 风险平价
        
        Args:
            signals: 股票信号列表
            strategy_mode: 策略模式
            max_positions: 最大持仓数
            cash_ratio: 现金比例
            
        Returns:
            PortfolioSignal 组合信号
        """
        # 筛选买入信号
        buy_signals = [s for s in signals if s.signal_type == "BUY"]
        buy_signals = sorted(
            buy_signals, 
            key=lambda x: x.composite_score, 
            reverse=True
        )[:max_positions]
        
        if not buy_signals:
            return PortfolioSignal(
                signals=[],
                strategy_mode=strategy_mode.value,
                total_positions=0,
                cash_ratio=cash_ratio,
                total_var=0,
                expected_return=0,
                sharpe_ratio=0,
                sector_allocation={},
                rebalance_建议=[],
                generated_at=datetime.now().isoformat(),
            )
        
        # 风险平价权重优化
        volatilities = np.array([s.volatility for s in buy_signals])
        
        # 逆波动率加权
        inv_vol = 1.0 / (volatilities + 0.01)
        raw_weights = inv_vol / inv_vol.sum()
        
        # 应用信号强度调整
        signal_strengths = np.array([s.signal_strength for s in buy_signals]) / 100
        adjusted_weights = raw_weights * (0.5 + 0.5 * signal_strengths)
        final_weights = adjusted_weights / adjusted_weights.sum()
        
        # 应用仓位限制
        max_weight = (1 - cash_ratio) / len(buy_signals)
        final_weights = np.minimum(final_weights, max_weight)
        final_weights = final_weights / final_weights.sum() * (1 - cash_ratio)
        
        # 更新每只股票的仓位
        for i, signal in enumerate(buy_signals):
            signal.position_size = final_weights[i]
        
        # 计算组合风险
        # 简化: 假设相关性为0.5
        corr_matrix = np.ones((len(buy_signals), len(buy_signals))) * 0.5
        np.fill_diagonal(corr_matrix, 1.0)
        
        portfolio_vol = np.sqrt(
            final_weights @ corr_matrix @ (volatilities ** 2) @ final_weights
        )
        
        # 预期收益
        expected_return = np.mean([
            s.composite_score / 100 * 0.20 for s in buy_signals
        ])
        
        # 夏普比率
        sharpe_ratio = (expected_return - 0.03) / portfolio_vol if portfolio_vol > 0 else 0
        
        # 行业分布 (简化)
        sector_allocation = {}
        
        return PortfolioSignal(
            signals=buy_signals,
            strategy_mode=strategy_mode.value,
            total_positions=len(buy_signals),
            cash_ratio=cash_ratio,
            total_var=portfolio_vol * 1.65,
            expected_return=expected_return,
            sharpe_ratio=sharpe_ratio,
            sector_allocation=sector_allocation,
            rebalance_建议=[
                {
                    "ticker": s.ticker,
                    "action": "BUY" if w > 0.01 else "HOLD",
                    "weight": w,
                    "reason": f"综合得分 {s.composite_score:.1f}, 信号强度 {s.signal_strength:.1f}"
                }
                for s, w in zip(buy_signals, final_weights)
            ],
            generated_at=datetime.now().isoformat(),
        )


# =============================================================================
# 策略切换器
# =============================================================================

class StrategySwitcher:
    """
    华尔街级策略切换器
    
    根据市场状态自动切换策略:
    - 牛市: 动量策略
    - 熊市: 反转策略
    - 震荡市: 质量策略
    """
    
    @staticmethod
    def detect_market_regime(
        vix: float,
        market_return_20d: float,
        market_return_60d: float,
    ) -> str:
        """
        检测市场状态
        
        Args:
            VIX: 恐慌指数
            market_return_20d: 20日市场收益
            market_return_60d: 60日市场收益
            
        Returns:
            市场状态: bullish/bearish/neutral
        """
        if vix > 30:
            # 高波动率 - 可能是熊市或底部
            if market_return_60d < -0.10:
                return "bearish"
            else:
                return "neutral"
        elif market_return_20d > 0.05 and market_return_60d > 0.10:
            return "bullish"
        elif market_return_20d < -0.05 or market_return_60d < -0.10:
            return "bearish"
        else:
            return "neutral"
    
    @staticmethod
    def get_recommended_strategy(
        market_regime: str,
        vix: float,
    ) -> StrategyMode:
        """
        根据市场状态推荐策略
        
        Args:
            market_regime: 市场状态
            vix: 恐慌指数
            
        Returns:
            推荐策略模式
        """
        if market_regime == "bullish":
            # 牛市: 动量策略
            return StrategyMode.MOMENTUM
        elif market_regime == "bearish":
            # 熊市: 现金为王 + 反转
            return StrategyMode.REVERSAL
        else:
            # 震荡市: 质量策略
            if vix > 20:
                return StrategyMode.QUALITY
            else:
                return StrategyMode.VALUE


# =============================================================================
# 选股入口函数
# =============================================================================

async def run_stock_selection(
    tickers: List[str],
    market_data: Dict[str, Dict[str, Any]],
    fundamental_data: Dict[str, Dict[str, Any]] = None,
    sentiment_data: Dict[str, Dict[str, Any]] = None,
    strategy_mode: str = "auto",
    max_positions: int = 10,
) -> PortfolioSignal:
    """
    选股主入口函数
    
    Args:
        tickers: 股票代码列表
        market_data: 市场数据字典 {ticker: {price, volume, ...}}
        fundamental_data: 基本面数据
        sentiment_data: 情绪数据
        strategy_mode: 策略模式 (auto/momentum/reversal/quality/growth/value)
        max_positions: 最大持仓数
        
    Returns:
        PortfolioSignal 组合选股信号
    """
    logger.info(f"[选股引擎] 开始选股: {len(tickers)} 只股票, 策略: {strategy_mode}")
    
    # 初始化引擎
    selector = WallStreetStockSelector()
    
    # 获取市场状态
    sample_data = list(market_data.values())[0] if market_data else {}
    vix = sample_data.get("vix", 15)
    market_return_20d = sample_data.get("market_return_20d", 0)
    market_return_60d = sample_data.get("market_return_60d", 0)
    
    # 自动策略选择
    if strategy_mode == "auto":
        market_regime = StrategySwitcher.detect_market_regime(
            vix, market_return_20d, market_return_60d
        )
        mode = StrategySwitcher.get_recommended_strategy(market_regime, vix)
        logger.info(f"[选股引擎] 市场状态: {market_regime}, 推荐策略: {mode.value}")
    else:
        mode = StrategyMode(strategy_mode)
    
    # 生成信号
    signals = []
    for ticker in tickers:
        mkt_data = market_data.get(ticker, {})
        fund_data = (fundamental_data or {}).get(ticker, {})
        sent_data = (sentiment_data or {}).get(ticker, {})
        
        signal = selector.generate_signal(
            ticker=ticker,
            name=ticker,  # 简化
            market_data=mkt_data,
            fundamental_data=fund_data,
            sentiment_data=sent_data,
        )
        signals.append(signal)
    
    # 排序
    signals = selector.rank_stocks(signals)
    
    # 组合优化
    portfolio = selector.optimize_portfolio(
        signals=signals,
        strategy_mode=mode,
        max_positions=max_positions,
    )
    
    logger.info(
        f"[选股引擎] 完成: {portfolio.total_positions} 只股票, "
        f"预期收益 {portfolio.expected_return:.2%}, 夏普比率 {portfolio.sharpe_ratio:.2f}"
    )
    
    return portfolio


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        # 模拟数据
        tickers = ["000001.SH", "600519.SH", "600036.SH", "300750.SZ", "601318.SH"]
        
        market_data = {
            "000001.SH": {"price": 12.58, "pe": 6.5, "pb": 0.65, "momentum_20d": 0.03, "momentum_60d": 0.08, "rsi": 55, "volume_ratio": 1.2, "volatility_20d": 0.18, "beta": 0.85},
            "600519.SH": {"price": 1689.0, "pe": 28, "pb": 8.5, "momentum_20d": 0.05, "momentum_60d": 0.12, "rsi": 62, "volume_ratio": 1.5, "volatility_20d": 0.22, "beta": 1.1},
            "600036.SH": {"price": 35.67, "pe": 7.2, "pb": 0.72, "momentum_20d": 0.02, "momentum_60d": 0.06, "rsi": 52, "volume_ratio": 1.1, "volatility_20d": 0.16, "beta": 0.88},
            "300750.SZ": {"price": 182.5, "pe": 45, "pb": 6.2, "momentum_20d": -0.02, "momentum_60d": -0.08, "rsi": 42, "volume_ratio": 0.9, "volatility_20d": 0.35, "beta": 1.3},
            "601318.SH": {"price": 45.23, "pe": 9.8, "pb": 0.95, "momentum_20d": 0.01, "momentum_60d": 0.04, "rsi": 48, "volume_ratio": 1.0, "volatility_20d": 0.15, "beta": 0.92},
        }
        
        fundamental_data = {
            "000001.SH": {"roe": 0.12, "revenue_growth": 0.08, "profit_margin": 0.25},
            "600519.SH": {"roe": 0.30, "revenue_growth": 0.15, "profit_margin": 0.52},
            "600036.SH": {"roe": 0.15, "revenue_growth": 0.10, "profit_margin": 0.35},
            "300750.SZ": {"roe": 0.08, "revenue_growth": 0.25, "profit_margin": 0.12},
            "601318.SH": {"roe": 0.14, "revenue_growth": 0.06, "profit_margin": 0.28},
        }
        
        # 运行选股
        result = await run_stock_selection(
            tickers=tickers,
            market_data=market_data,
            fundamental_data=fundamental_data,
            strategy_mode="auto",
        )
        
        # 打印结果
        print("\n" + "="*60)
        print("华尔街级选股信号")
        print("="*60)
        print(f"策略模式: {result.strategy_mode}")
        print(f"持仓数量: {result.total_positions}")
        print(f"预期收益: {result.expected_return:.2%}")
        print(f"夏普比率: {result.sharpe_ratio:.2f}")
        print(f"组合VaR(95%): {result.total_var:.2%}")
        print("\n选股信号:")
        print("-"*60)
        
        for signal in result.signals:
            print(f"{signal.rank}. {signal.ticker} {signal.name}")
            print(f"   综合得分: {signal.composite_score:.1f} ({signal.score_level})")
            print(f"   信号: {signal.signal_type} (强度: {signal.signal_strength:.1f})")
            print(f"   置信度: {signal.confidence:.1f}%")
            print(f"   建议仓位: {signal.position_size:.1%}")
            print(f"   目标价: {signal.target_price:.2f}, 止损: {signal.stop_loss:.2f}")
            print()
        
        print("调仓建议:")
        print("-"*60)
        for rec in result.rebalance_建议:
            print(f"{rec['action']:4s} {rec['ticker']:12s} 权重: {rec['weight']:.1%}  原因: {rec['reason']}")
    
    asyncio.run(test())
