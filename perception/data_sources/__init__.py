"""
AI TradeBot - 数据源模块

包含：
- Tushare Pro 全能客户端
- 数据模型
"""
from .tushare_pro import (
    TushareProClient,
    get_tushare_pro,
    MinuteBar,
    NewsItem,
    Announcement,
    ChipData,
    BrokerPick,
    get_minute_bars,
    get_news,
    get_major_news,
    get_realtime_daily,
    get_chip_data,
    get_broker_picks,
)

__all__ = [
    "TushareProClient",
    "get_tushare_pro",
    "MinuteBar",
    "NewsItem",
    "Announcement",
    "ChipData",
    "BrokerPick",
    "get_minute_bars",
    "get_news",
    "get_major_news",
    "get_realtime_daily",
    "get_chip_data",
    "get_broker_picks",
]
