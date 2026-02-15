"""
AI TradeBot - 新闻感知模块

整合 Tushare 股票哨兵和 CryptoPanic 加密哨兵
提供实时市场快讯监测能力
"""
from .tushare_sentinel import get_tushare_sentinel, start_tushare_monitoring
from .cryptopanic_sentinel import get_cryptopanic_sentinel, start_cryptopanic_monitoring

__all__ = [
    "get_tushare_sentinel",
    "start_tushare_monitoring",
    "get_cryptopanic_sentinel",
    "start_cryptopanic_monitoring",
]
