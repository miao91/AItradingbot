"""
AI TradeBot - 行情数据管理器

功能：
1. 封装 Tushare 获取历史 K 线
2. 封装 AkShare 获取实时行情（含五档）
3. JSON 缓存机制避免重复调用
"""
import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from functools import wraps
import time

import akshare as ak
import pandas as pd
from pydantic import BaseModel, Field

from shared.logging import get_logger, track_ai_call
from shared.constants import TIMEZONE


logger = get_logger(__name__)


# =============================================================================
# 数据模型
# =============================================================================

class RealtimeQuote(BaseModel):
    """实时行情数据模型"""
    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    current_price: float = Field(..., description="最新价")
    open_price: float = Field(..., description="开盘价")
    high_price: float = Field(..., description="最高价")
    low_price: float = Field(..., description="最低价")
    prev_close: float = Field(..., description="昨收价")
    volume: int = Field(..., description="成交量")
    amount: float = Field(..., description="成交额")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")

    # 五档盘口
    bid1: Optional[float] = Field(default=None, description="买一价")
    bid1_volume: Optional[int] = Field(default=None, description="买一量")
    bid2: Optional[float] = Field(default=None)
    bid2_volume: Optional[int] = Field(default=None)
    bid3: Optional[float] = Field(default=None)
    bid3_volume: Optional[int] = Field(default=None)
    bid4: Optional[float] = Field(default=None)
    bid4_volume: Optional[int] = Field(default=None)
    bid5: Optional[float] = Field(default=None)
    bid5_volume: Optional[int] = Field(default=None)

    ask1: Optional[float] = Field(default=None, description="卖一价")
    ask1_volume: Optional[int] = Field(default=None, description="卖一量")
    ask2: Optional[float] = Field(default=None)
    ask2_volume: Optional[int] = Field(default=None)
    ask3: Optional[float] = Field(default=None)
    ask3_volume: Optional[int] = Field(default=None)
    ask4: Optional[float] = Field(default=None)
    ask4_volume: Optional[int] = Field(default=None)
    ask5: Optional[float] = Field(default=None)
    ask5_volume: Optional[int] = Field(default=None)


class DailyBar(BaseModel):
    """日K线数据模型"""
    trade_date: str = Field(..., description="交易日期 YYYYMMDD")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    close: float = Field(..., description="收盘价")
    volume: int = Field(..., description="成交量")
    amount: float = Field(..., description="成交额")


# =============================================================================
# 重试装饰器
# =============================================================================

def retry_on_error(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    重试装饰器

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 退避系数
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}"
                        )

            raise last_exception

        return wrapper
    return decorator


def retry_sync(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """同步版本的重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {e}"
                        )

            raise last_exception

        return wrapper
    return decorator


# =============================================================================
# 缓存管理器
# =============================================================================

class CacheManager:
    """简单的 JSON 文件缓存管理器"""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, prefix: str, **kwargs) -> str:
        """生成缓存键"""
        # 将参数序列化为字符串并计算哈希
        params_str = json.dumps(kwargs, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]
        return f"{prefix}_{params_hash}"

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.json"

    def get(self, prefix: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        从缓存获取数据

        Args:
            prefix: 缓存前缀
            **kwargs: 缓存键参数

        Returns:
            缓存的数据，如果不存在或过期则返回 None
        """
        key = self._get_cache_key(prefix, **kwargs)
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查是否过期（默认1小时）
            cached_time = datetime.fromisoformat(data.get('cached_at', ''))
            if datetime.now() - cached_time > timedelta(hours=1):
                logger.debug(f"Cache expired: {key}")
                cache_path.unlink()
                return None

            logger.debug(f"Cache hit: {key}")
            return data.get('result')

        except Exception as e:
            logger.warning(f"Failed to read cache {key}: {e}")
            return None

    def set(self, prefix: str, result: Any, **kwargs) -> None:
        """
        保存数据到缓存

        Args:
            prefix: 缓存前缀
            result: 要缓存的数据
            **kwargs: 缓存键参数
        """
        key = self._get_cache_key(prefix, **kwargs)
        cache_path = self._get_cache_path(key)

        try:
            cache_data = {
                'cached_at': datetime.now().isoformat(),
                'result': result
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Cache saved: {key}")

        except Exception as e:
            logger.warning(f"Failed to save cache {key}: {e}")

    def clear(self, prefix: Optional[str] = None) -> None:
        """
        清理缓存

        Args:
            prefix: 如果指定，只清理该前缀的缓存；否则清理全部
        """
        if prefix:
            for cache_file in self.cache_dir.glob(f"{prefix}_*.json"):
                cache_file.unlink()
                logger.debug(f"Cache cleared: {cache_file.name}")
        else:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("All cache cleared")


# 全局缓存实例
cache_manager = CacheManager()


# =============================================================================
# Tushare 接口封装
# =============================================================================

class TushareClient:
    """Tushare 客户端封装"""

    def __init__(self, token: Optional[str] = None):
        """
        初始化 Tushare 客户端

        Args:
            token: Tushare Token，如果不提供则从环境变量读取
        """
        import os
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            logger.warning("TUSHARE_TOKEN not set, Tushare features will be limited")

        # 延迟导入，避免未安装时出错
        try:
            import tushare as ts
            ts.set_token(self.token)
            self.pro = ts.pro_api()
        except Exception as e:
            logger.error(f"Failed to initialize Tushare: {e}")
            self.pro = None

    @retry_sync(max_retries=3, delay=1.0)
    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_cache: bool = True,
    ) -> List[DailyBar]:
        """
        获取日K线数据

        Args:
            symbol: 股票代码 (如: 600000.SH)
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            use_cache: 是否使用缓存

        Returns:
            日K线数据列表
        """
        if not self.pro:
            raise RuntimeError("Tushare client not initialized")

        # 检查缓存
        if use_cache:
            cached = cache_manager.get(
                "daily_bars",
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )
            if cached:
                return [DailyBar(**bar) for bar in cached]

        # 默认日期范围：最近3个月
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")

        logger.info(f"Fetching daily bars from Tushare: {symbol} ({start_date} ~ {end_date})")

        try:
            # 调用 Tushare API
            df = self.pro.daily(
                ts_code=symbol,
                start_date=start_date,
                end_date=end_date
            )

            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return []

            # 转换为模型列表
            bars = []
            for _, row in df.iterrows():
                bars.append(DailyBar(
                    trade_date=row['trade_date'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=int(row['vol']),
                    amount=float(row['amount']) * 1000,  # Tushare 单位是千元
                ))

            # 缓存结果
            if use_cache:
                cache_manager.set(
                    "daily_bars",
                    [bar.model_dump() for bar in bars],
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date
                )

            logger.info(f"Retrieved {len(bars)} daily bars for {symbol}")
            return bars

        except Exception as e:
            logger.error(f"Failed to get daily bars from Tushare: {e}")
            raise

    @retry_sync(max_retries=3, delay=1.0)
    def get_basic_info(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取股票基本信息

        Args:
            symbol: 股票代码
            use_cache: 是否使用缓存

        Returns:
            股票基本信息字典
        """
        if not self.pro:
            return None

        # 检查缓存
        if use_cache:
            cached = cache_manager.get("basic_info", symbol=symbol)
            if cached:
                return cached

        try:
            df = self.pro.stock_basic(ts_code=symbol, fields='ts_code,name,industry,list_date')

            if df.empty:
                return None

            info = {
                'symbol': df.iloc[0]['ts_code'],
                'name': df.iloc[0]['name'],
                'industry': df.iloc[0]['industry'],
                'list_date': df.iloc[0]['list_date'],
            }

            # 缓存
            if use_cache:
                cache_manager.set("basic_info", info, symbol=symbol)

            return info

        except Exception as e:
            logger.error(f"Failed to get basic info: {e}")
            return None


# =============================================================================
# AkShare 接口封装
# =============================================================================

class AkShareClient:
    """AkShare 客户端封装"""

    def __init__(self):
        """初始化 AkShare 客户端"""
        self.timeout = 10  # 默认超时10秒

    @retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
    async def get_realtime_quote(self, symbol: str) -> RealtimeQuote:
        """
        获取实时行情（含五档盘口）

        Args:
            symbol: 股票代码，支持多种格式：
                    - 600000 (上海)
                    - 000001 (深圳)
                    - 600000.SH (Tushare 格式)
                    - sh600000 (东方财富格式)

        Returns:
            实时行情数据

        Raises:
            RuntimeError: 获取失败时
        """
        logger.info(f"Fetching realtime quote: {symbol}")

        try:
            # 转换代码格式
            ak_symbol = self._convert_symbol(symbol)

            # 方法1: 使用 stock_zh_a_spot_em (东方财富)
            df = await asyncio.to_thread(
                ak.stock_zh_a_spot_em
            )

            # 查找目标股票
            row = df[df['代码'] == ak_symbol]

            if row.empty:
                # 尝试另一种格式
                alt_symbol = ak_symbol.replace('sh', '').replace('sz', '')
                row = df[df['代码'] == alt_symbol]

            if row.empty:
                raise ValueError(f"Stock {symbol} not found in market data")

            row = row.iloc[0]

            # 构建返回数据
            quote = RealtimeQuote(
                symbol=symbol,
                name=str(row.get('名称', '')),
                current_price=float(row.get('最新价', 0)),
                open_price=float(row.get('今开', 0)),
                high_price=float(row.get('最高', 0)),
                low_price=float(row.get('最低', 0)),
                prev_close=float(row.get('昨收', 0)),
                volume=int(row.get('成交量', 0)),
                amount=float(row.get('成交额', 0)),
                timestamp=datetime.now(),
            )

            logger.debug(f"Quote retrieved: {quote.symbol} = {quote.current_price}")
            return quote

        except Exception as e:
            logger.error(f"Failed to get realtime quote for {symbol}: {e}")
            raise RuntimeError(f"AkShare quote fetch failed: {e}") from e

    @retry_on_error(max_retries=3, delay=1.0, backoff=2.0)
    async def get_realtime_quote_with_depth(self, symbol: str) -> RealtimeQuote:
        """
        获取实时行情（含五档深度）

        Args:
            symbol: 股票代码

        Returns:
            含五档盘口的实时行情
        """
        logger.info(f"Fetching realtime quote with depth: {symbol}")

        try:
            # 转换代码格式
            ak_symbol = self._convert_symbol(symbol)

            # 使用 stock_individual_spot_em (东方财富单股实时行情)
            try:
                df = await asyncio.to_thread(
                    ak.stock_individual_spot_em,
                    symbol=ak_symbol
                )

                if df.empty:
                    raise ValueError("Empty response from AkShare")

                row = df.iloc[0] if len(df) == 1 else df

                quote = RealtimeQuote(
                    symbol=symbol,
                    name=str(row.get('名称', symbol)),
                    current_price=float(row.get('最新价', 0)),
                    open_price=float(row.get('今开', 0)),
                    high_price=float(row.get('最高', 0)),
                    low_price=float(row.get('最低', 0)),
                    prev_close=float(row.get('昨收', 0)),
                    volume=int(row.get('成交量', 0)),
                    amount=float(row.get('成交额', 0)),
                    timestamp=datetime.now(),
                    # 五档数据（如果有的话）
                    bid1=float(row.get('买一价', 0)) if '买一价' in row else None,
                    bid1_volume=int(row.get('买一量', 0)) if '买一量' in row else None,
                    ask1=float(row.get('卖一价', 0)) if '卖一价' in row else None,
                    ask1_volume=int(row.get('卖一量', 0)) if '卖一量' in row else None,
                )

                logger.info(f"Quote with depth retrieved: {quote.symbol} = {quote.current_price}")
                return quote

            except Exception as e:
                logger.warning(f"Failed to get depth quote, falling back to basic quote: {e}")
                return await self.get_realtime_quote(symbol)

        except Exception as e:
            logger.error(f"Failed to get quote with depth for {symbol}: {e}")
            raise

    def _convert_symbol(self, symbol: str) -> str:
        """
        转换股票代码格式为 AkShare 格式

        Args:
            symbol: 输入的股票代码

        Returns:
            AkShare 格式的股票代码
        """
        symbol = symbol.upper().replace('.', '')

        # 判断市场
        if symbol.startswith('6'):
            # 上海市场
            if not symbol.startswith('SH'):
                return f"sh{symbol}"
        elif symbol.startswith(('0', '3')):
            # 深圳市场
            if not symbol.startswith('SZ'):
                return f"sz{symbol}"

        return symbol.lower()


# =============================================================================
# 行情管理器（统一接口）
# =============================================================================

class MarketDataManager:
    """行情数据管理器 - 统一对外接口"""

    def __init__(
        self,
        tushare_token: Optional[str] = None,
        cache_enabled: bool = True,
    ):
        """
        初始化行情管理器

        Args:
            tushare_token: Tushare Token
            cache_enabled: 是否启用缓存
        """
        self.tushare = TushareClient(token=tushare_token)
        self.akshare = AkShareClient()
        self.cache_enabled = cache_enabled

    async def get_realtime_price(self, symbol: str) -> float:
        """
        获取实时价格（便捷方法）

        Args:
            symbol: 股票代码

        Returns:
            最新价格
        """
        quote = await self.akshare.get_realtime_quote(symbol)
        return quote.current_price

    async def get_realtime_quote(self, symbol: str) -> RealtimeQuote:
        """
        获取实时行情

        Args:
            symbol: 股票代码

        Returns:
            实时行情数据
        """
        return await self.akshare.get_realtime_quote_with_depth(symbol)

    def get_daily_bars(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[DailyBar]:
        """
        获取历史K线

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            K线数据列表
        """
        return self.tushare.get_daily_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            use_cache=self.cache_enabled,
        )

    def get_stock_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取股票基本信息

        Args:
            symbol: 股票代码

        Returns:
            股票信息字典
        """
        return self.tushare.get_basic_info(
            symbol=symbol,
            use_cache=self.cache_enabled,
        )

    def clear_cache(self, prefix: Optional[str] = None) -> None:
        """清理缓存"""
        if self.cache_enabled:
            cache_manager.clear(prefix)


# =============================================================================
# 便捷函数
# =============================================================================

# 全局行情管理器实例
_market_manager: Optional[MarketDataManager] = None


def get_market_manager() -> MarketDataManager:
    """获取全局行情管理器实例"""
    global _market_manager
    if _market_manager is None:
        _market_manager = MarketDataManager()
    return _market_manager


async def get_realtime_price(symbol: str) -> float:
    """获取实时价格的便捷函数"""
    return await get_market_manager().get_realtime_price(symbol)


async def get_realtime_quote(symbol: str) -> RealtimeQuote:
    """获取实时行情的便捷函数"""
    return await get_market_manager().get_realtime_quote(symbol)


def get_daily_bars(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[DailyBar]:
    """获取历史K线的便捷函数"""
    return get_market_manager().get_daily_bars(symbol, start_date, end_date)
