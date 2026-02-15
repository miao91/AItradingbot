"""
AI TradeBot - 搜索感知模块

提供 Tavily AI 搜索功能，带严格的 Token 裁剪策略
"""
from .tavily_client import (
    TavilyClient,
    TavilySearchResult,
    TavilyResponse,
    get_tavily_client,
    search_stock_event,
)

__all__ = [
    "TavilyClient",
    "TavilySearchResult",
    "TavilyResponse",
    "get_tavily_client",
    "search_stock_event",
]
