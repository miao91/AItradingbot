"""
AI TradeBot - Tushare Pro 数据源（全能版）

封装 Tushare 全部接口：
- 股票分钟数据（1/5/15/30/60分钟）
- 实时日线数据
- 新闻资讯
- 公告信息
- 特色数据（筹码、胜率、金股）
- 集合竞价
- 互动数据
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from functools import wraps
import time

import pandas as pd
import tushare as ts
from dotenv import load_dotenv

from shared.logging import get_logger

load_dotenv()
logger = get_logger(__name__)


# =============================================================================
# 重试装饰器
# =============================================================================

def retry_api(max_retries: int = 3, delay: float = 0.5, backoff: float = 2.0):
    """API 调用重试装饰器"""
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
                    error_msg = str(e)

                    # 检查是否是频次限制
                    if "频次" in error_msg or "limit" in error_msg.lower():
                        logger.warning(f"API频次限制，等待 {current_delay}s 后重试...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    elif attempt < max_retries - 1:
                        logger.warning(f"{func.__name__} 失败 (第{attempt + 1}次): {e}")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"{func.__name__} 失败 (已达最大重试次数): {e}")

            raise last_exception
        return wrapper
    return decorator


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class MinuteBar:
    """分钟K线数据"""
    ts_code: str
    trade_time: datetime
    open: float
    high: float
    low: float
    close: float
    vol: float
    amount: float


@dataclass
class NewsItem:
    """新闻数据"""
    title: str
    content: str
    pub_time: datetime
    src: str
    url: Optional[str] = None
    channels: Optional[str] = None
    score: float = 0.0


@dataclass
class Announcement:
    """公告数据"""
    ann_date: str
    ann_type: str
    title: str
    ts_code: str
    url: Optional[str] = None
    pdf_url: Optional[str] = None


@dataclass
class ChipData:
    """筹码数据"""
    trade_date: str
    ts_code: str
    his_low: float  # 获利盘最低价
    his_high: float  # 获利盘最高价
    cost_5pct: float  # 5%成本
    cost_15pct: float  # 15%成本
    cost_50pct: float  # 50%成本
    cost_85pct: float  # 85%成本
    cost_95pct: float  # 95%成本
    weight_avg: float  # 加权平均成本


@dataclass
class BrokerPick:
    """券商金股"""
    trade_date: str
    ts_code: str
    name: str
    broker: str
    rating: str
    target_price: float = 0.0
    reason: str = ""


# =============================================================================
# Tushare Pro 客户端
# =============================================================================

class TushareProClient:
    """
    Tushare Pro 全能客户端

    封装所有 Tushare 接口，包括：
    - 分钟数据（历史+实时）
    - 新闻资讯
    - 公告信息
    - 特色数据
    - 集合竞价
    - 互动数据
    """

    def __init__(self, token: Optional[str] = None):
        """初始化客户端"""
        self.token = token or os.getenv("TUSHARE_TOKEN")
        if not self.token:
            raise ValueError("TUSHARE_TOKEN 未配置")

        ts.set_token(self.token)
        self.pro = ts.pro_api()
        logger.info("[TusharePro] 客户端初始化完成 - 全能API")

    # =========================================================================
    # 分钟数据接口
    # =========================================================================

    @retry_api(max_retries=3)
    def get_minute_bars(
        self,
        ts_code: str,
        freq: str = "1min",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 8000,
    ) -> List[MinuteBar]:
        """
        获取分钟K线数据

        Args:
            ts_code: 股票代码 (如: 600000.SH)
            freq: 分钟频率 (1/5/15/30/60min)
            start_date: 开始日期 (YYYYMMDD HH:MM)
            end_date: 结束日期
            limit: 返回数据条数（最大8000）

        Returns:
            分钟K线列表
        """
        logger.info(f"[分钟数据] 获取 {ts_code} {freq} K线...")

        df = self.pro.query(
            "stk_mins",
            ts_code=ts_code,
            freq=freq,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        if df is None or df.empty:
            return []

        bars = []
        for _, row in df.iterrows():
            try:
                trade_time = datetime.strptime(row["trade_time"], "%Y-%m-%d %H:%M:%S")
            except:
                trade_time = datetime.now()

            bars.append(MinuteBar(
                ts_code=row["ts_code"],
                trade_time=trade_time,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                vol=float(row["vol"]),
                amount=float(row["amount"]),
            ))

        logger.info(f"[分钟数据] 获取 {len(bars)} 条记录")
        return bars

    @retry_api(max_retries=3)
    def get_realtime_minute(self, ts_codes: List[str], freq: str = "1min") -> pd.DataFrame:
        """
        获取实时分钟数据

        Args:
            ts_codes: 股票代码列表（最多300个）
            freq: 分钟频率

        Returns:
            DataFrame
        """
        codes_str = ",".join(ts_codes[:300])
        logger.info(f"[实时分钟] 获取 {len(ts_codes[:300])} 只股票 {freq} 数据...")

        df = self.pro.query(
            "stk_mins_realtime",
            ts_code=codes_str,
            freq=freq,
        )

        return df

    # =========================================================================
    # 实时日线接口
    # =========================================================================

    @retry_api(max_retries=3)
    def get_realtime_daily(self, ts_code: Optional[str] = None) -> pd.DataFrame:
        """
        获取实时日线数据（开盘后可用）

        Args:
            ts_code: 股票代码，None 时获取全市场

        Returns:
            DataFrame
        """
        logger.info(f"[实时日线] 获取数据...")

        df = self.pro.query(
            "daily_realtime",
            ts_code=ts_code,
        )

        return df

    @retry_api(max_retries=3)
    def get_etf_realtime(self) -> pd.DataFrame:
        """获取ETF实时日线数据"""
        logger.info("[ETF实时] 获取数据...")
        return self.pro.query("fund_daily_realtime")

    # =========================================================================
    # 新闻资讯接口
    # =========================================================================

    @retry_api(max_retries=3)
    def get_news(
        self,
        src: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        channels: Optional[str] = None,
    ) -> List[NewsItem]:
        """
        获取快讯新闻

        Args:
            src: 来源 (sina/10jqka/eastmoney/yicai...)
            start_date: 开始时间
            end_date: 结束时间
            channels: 频道

        Returns:
            新闻列表
        """
        logger.info(f"[新闻] 获取快讯 src={src}...")

        df = self.pro.news(
            src=src,
            start_date=start_date,
            end_date=end_date,
            channels=channels,
        )

        if df is None or df.empty:
            return []

        items = []
        for _, row in df.iterrows():
            try:
                pub_time = datetime.strptime(str(row.get("datetime", "")), "%Y-%m-%d %H:%M:%S")
            except:
                pub_time = datetime.now()

            items.append(NewsItem(
                title=str(row.get("title", ""))[:200] if row.get("title") else str(row.get("content", ""))[:200],
                content=str(row.get("content", ""))[:500] if row.get("content") else "",
                pub_time=pub_time,
                src=str(row.get("channels", src or "unknown")),
                channels=str(row.get("channels", "")),
            ))

        logger.info(f"[新闻] 获取 {len(items)} 条快讯")
        return items

    @retry_api(max_retries=3)
    def get_major_news(
        self,
        src: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[NewsItem]:
        """
        获取长篇通讯/重大新闻

        Args:
            src: 来源
            start_date: 开始时间
            end_date: 结束时间

        Returns:
            新闻列表
        """
        logger.info(f"[长篇新闻] 获取数据 src={src}...")

        df = self.pro.major_news(
            src=src,
            start_date=start_date,
            end_date=end_date,
        )

        if df is None or df.empty:
            return []

        items = []
        for _, row in df.iterrows():
            try:
                pub_time = datetime.strptime(str(row.get("pub_time", "")), "%Y-%m-%d %H:%M:%S")
            except:
                pub_time = datetime.now()

            items.append(NewsItem(
                title=str(row.get("title", ""))[:200],
                content="",  # major_news 通常没有 content
                pub_time=pub_time,
                src=str(row.get("src", "unknown")),
                url=str(row.get("url", "")) if row.get("url") else None,
            ))

        logger.info(f"[长篇新闻] 获取 {len(items)} 条")
        return items

    @retry_api(max_retries=3)
    def get_cctv_news(self, date: Optional[str] = None) -> List[NewsItem]:
        """获取新闻联播内容"""
        logger.info(f"[新闻联播] 获取 {date or '最新'} 数据...")

        df = self.pro.cctv_news(date=date)

        if df is None or df.empty:
            return []

        items = []
        for _, row in df.iterrows():
            items.append(NewsItem(
                title=str(row.get("title", "")),
                content=str(row.get("content", ""))[:500] if row.get("content") else "",
                pub_time=datetime.strptime(str(row.get("date", "")), "%Y-%m-%d") if row.get("date") else datetime.now(),
                src="新闻联播",
            ))

        return items

    # =========================================================================
    # 公告信息接口
    # =========================================================================

    @retry_api(max_retries=3)
    def get_announcements(
        self,
        ts_code: Optional[str] = None,
        ann_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Announcement]:
        """
        获取公告信息

        Args:
            ts_code: 股票代码
            ann_type: 公告类型
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            公告列表
        """
        logger.info(f"[公告] 获取 ts_code={ts_code}, type={ann_type}...")

        df = self.pro.anns(
            ts_code=ts_code,
            ann_type=ann_type,
            start_date=start_date,
            end_date=end_date,
        )

        if df is None or df.empty:
            return []

        items = []
        for _, row in df.iterrows():
            items.append(Announcement(
                ann_date=str(row.get("ann_date", "")),
                ann_type=str(row.get("ann_type", "")),
                title=str(row.get("title", "")),
                ts_code=str(row.get("ts_code", "")),
                url=str(row.get("url", "")) if row.get("url") else None,
            ))

        logger.info(f"[公告] 获取 {len(items)} 条")
        return items

    # =========================================================================
    # 特色数据接口
    # =========================================================================

    @retry_api(max_retries=3)
    def get_chip_data(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[ChipData]:
        """
        获取筹码分布数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            筹码数据列表
        """
        logger.info(f"[筹码] 获取 {ts_code} 筹码分布...")

        df = self.pro.cyq_perf(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

        if df is None or df.empty:
            return []

        items = []
        for _, row in df.iterrows():
            items.append(ChipData(
                trade_date=str(row.get("trade_date", "")),
                ts_code=str(row.get("ts_code", "")),
                his_low=float(row.get("his_low", 0)),
                his_high=float(row.get("his_high", 0)),
                cost_5pct=float(row.get("cost_5pct", 0)),
                cost_15pct=float(row.get("cost_15pct", 0)),
                cost_50pct=float(row.get("cost_50pct", 0)),
                cost_85pct=float(row.get("cost_85pct", 0)),
                cost_95pct=float(row.get("cost_95pct", 0)),
                weight_avg=float(row.get("weight_avg", 0)),
            ))

        logger.info(f"[筹码] 获取 {len(items)} 条记录")
        return items

    @retry_api(max_retries=3)
    def get_broker_picks(
        self,
        broker: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[BrokerPick]:
        """
        获取券商金股

        Args:
            broker: 券商名称
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            金股列表
        """
        logger.info(f"[券商金股] 获取 {broker or '全部'} 金股...")

        df = self.pro.broker_recommend(
            broker=broker,
            start_date=start_date,
            end_date=end_date,
        )

        if df is None or df.empty:
            return []

        items = []
        for _, row in df.iterrows():
            items.append(BrokerPick(
                trade_date=str(row.get("trade_date", "")),
                ts_code=str(row.get("ts_code", "")),
                name=str(row.get("name", "")),
                broker=str(row.get("broker", "")),
                rating=str(row.get("rating", "")),
                target_price=float(row.get("target_price", 0) or 0),
                reason=str(row.get("reason", "")),
            ))

        logger.info(f"[券商金股] 获取 {len(items)} 条")
        return items

    @retry_api(max_retries=3)
    def get_daily_winner(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取每日筹码胜率

        Args:
            trade_date: 交易日期

        Returns:
            DataFrame
        """
        logger.info(f"[筹码胜率] 获取 {trade_date or '最新'} 数据...")
        return self.pro.cyq_bulls(trade_date=trade_date)

    # =========================================================================
    # 集合竞价接口
    # =========================================================================

    @retry_api(max_retries=3)
    def get_auction_data(self, trade_date: str, ts_code: Optional[str] = None) -> pd.DataFrame:
        """
        获取集合竞价数据

        Args:
            trade_date: 交易日期
            ts_code: 股票代码

        Returns:
            DataFrame
        """
        logger.info(f"[集合竞价] 获取 {trade_date} 数据...")

        df = self.pro.auction_detail(
            trade_date=trade_date,
            ts_code=ts_code,
        )

        return df

    # =========================================================================
    # 互动数据接口
    # =========================================================================

    @retry_api(max_retries=3)
    def get_interactions(
        self,
        ts_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取互动问答数据（上证e互动、深证互动易）

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame
        """
        logger.info(f"[互动问答] 获取 {ts_code or '全部'} 数据...")

        df = self.pro.news_interact(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

        return df

    # =========================================================================
    # 基础数据接口（积分接口）
    # =========================================================================

    @retry_api(max_retries=3)
    def get_daily(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取日线数据"""
        return self.pro.daily(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

    @retry_api(max_retries=3)
    def get_stock_basic(self, ts_code: Optional[str] = None) -> pd.DataFrame:
        """获取股票基本信息"""
        return self.pro.stock_basic(ts_code=ts_code, list_status="L")

    @retry_api(max_retries=3)
    def get_trade_calendar(self, exchange: str = "SSE", start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """获取交易日历"""
        return self.pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date)

    @retry_api(max_retries=3)
    def get_moneyflow(self, ts_code: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """获取资金流向"""
        return self.pro.moneyflow(ts_code=ts_code, start_date=start_date, end_date=end_date)

    @retry_api(max_retries=3)
    def get_limit_price(self, trade_date: str) -> pd.DataFrame:
        """获取涨跌停价格"""
        return self.pro.stk_limit(trade_date=trade_date)


# =============================================================================
# 全局单例
# =============================================================================

_client: Optional[TushareProClient] = None


def get_tushare_pro() -> TushareProClient:
    """获取全局 Tushare Pro 客户端"""
    global _client
    if _client is None:
        _client = TushareProClient()
    return _client


# =============================================================================
# 便捷函数
# =============================================================================

def get_minute_bars(ts_code: str, freq: str = "1min", limit: int = 1000) -> List[MinuteBar]:
    """获取分钟K线"""
    return get_tushare_pro().get_minute_bars(ts_code, freq=freq, limit=limit)


def get_news(limit: int = 100) -> List[NewsItem]:
    """获取快讯新闻"""
    return get_tushare_pro().get_news()[:limit]


def get_major_news(limit: int = 100) -> List[NewsItem]:
    """获取长篇新闻"""
    return get_tushare_pro().get_major_news()[:limit]


def get_realtime_daily(ts_code: Optional[str] = None) -> pd.DataFrame:
    """获取实时日线"""
    return get_tushare_pro().get_realtime_daily(ts_code)


def get_chip_data(ts_code: str) -> List[ChipData]:
    """获取筹码数据"""
    return get_tushare_pro().get_chip_data(ts_code)


def get_broker_picks() -> List[BrokerPick]:
    """获取券商金股"""
    return get_tushare_pro().get_broker_picks()
