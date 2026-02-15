"""
AI TradeBot - Tushare 快讯流集成

集成 Tushare Pro API，使用 news_classifier.py 进行实时价值评估
对高分新闻自动触发 Discord 协作
"""
import asyncio
import time
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional, Set
from dataclasses import dataclass, field

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

TUSHARE_FEED_CONFIG = {
    # Tushare Token
    "token": "",  # 从环境变量读取

    # 轮询配置
    "poll_interval": 60,  # 秒
    "max_results_per_call": 100,

    # 关键词过滤
    "core_keywords": [
        "涨停", "异动", "大涨", "暴跌",
        "减半", "分红", "回购", "增持",
        "监管", "政策", "法案", "批准",
        "融资", "定增", "重组", "并购",
        "业绩", "财报", "快讯"
    ],

    # Discord 触发阈值
    "discord_trigger_score": 7.0,  # >=7分触发 Discord
}


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class NewsItem:
    """Tushare 新闻项"""
    title: str
    content: str
    source: str
    publish_time: datetime
    ticker: Optional[str] = None
    url: Optional[str] = None

    def __hash__(self):
        return hash((self.title, self.publish_time, self.url))


@dataclass
class FeedResult:
    """快讯流结果"""
    total_fetched: int = 0
    new_items: int = 0
    core_items: int = 0  # 包含核心关键词的
    processed_hashes: Set[str] = field(default_factory=set)
    items: List[NewsItem] = field(default_factory=list)


# =============================================================================
# Tushare 快讯流
# =============================================================================

class TushareNewsFeed:
    """
    Tushare 快讯流

    使用 Tushare Pro API 获取实时快讯
    并集 news_classifier 进行价值评分
    """

    def __init__(self, token: str, config: Optional[Dict] = None):
        """初始化"""
        self.token = token or __import__("os").getenv("TUSHARE_TOKEN", "")
        self.config = config or TUSHARE_FEED_CONFIG
        self.running = False
        self.processed_hashes: Set[str] = set()
        self.classifier = None  # 延迟加载

    async def load_dependencies(self):
        """延迟加载依赖"""
        from perception.news.news_classifier import get_news_classifier
        if self.classifier is None:
            self.classifier = get_news_classifier()

    async def start(self, callback: Optional[Callable] = None):
        """启动快讯流"""
        if self.running:
            logger.warning("[Tushare流] 已在运行中")
            return

        self.running = True
        self.callback = callback

        logger.info(
            f"[Tushare流] 启动实时监测: "
            f"轮询间隔={self.config['poll_interval']}s, "
            f"关键词={len(self.config['core_keywords'])}"
        )

        await self.load_dependencies()

        while self.running:
            try:
                # 获取最新快讯
                feed_result = await self._fetch_latest_news()

                # 去重和过滤
                new_items = [
                    item for item in feed_result.items
                    if hash(item) not in self.processed_hashes
                ]

                # 关键词过滤
                core_items = [
                    item for item in new_items
                    if any(keyword in item.title.lower() or keyword in (item.content or "").lower()
                       for keyword in self.config["core_keywords"])
                ]

                # 记录已处理
                for item in new_items:
                    self.processed_hashes.add(hash(item))

                logger.info(
                    f"[Tushare流] 获取 {len(feed_result.total_fetched)} 条, "
                    f"新增 {len(new_items)} 条, "
                    f"核心 {len(core_items)} 条"
                )

                # 更新统计
                feed_result.total_fetched = len(new_items)
                feed_result.new_items = len(new_items)
                feed_result.core_items = len(core_items)

                # 触发回调
                if self.callback and core_items:
                    for item in core_items:
                        await self.callback(item)

                # 等待下次轮询
                await asyncio.sleep(self.config["poll_interval"])

            except Exception as e:
                logger.error(f"[Tushare流] 轮询异常: {e}")
                await asyncio.sleep(10)  # 异常后等待 10 秒

    async def _fetch_latest_news(self) -> FeedResult:
        """获取最新快讯"""
        import tushare as ts

        if not self.token:
            logger.warning("[Tushare流] Token 未设置")
            return FeedResult()

        try:
            # 调用 pro_bar 接口
            pro = ts.pro_api()

            # 获取最新数据
            df = pro.bar(
                pro_api=ts.ProAPI.PRO_BAR,
                fields="datetime,title,content,src",
                num=self.config["max_results_per_call"],
            )

            if df is None or df.empty:
                return FeedResult()

            items = []
            for _, row in df.iterrows():
                # 解析日期时间
                datetime_str = str(row.get("datetime", ""))
                publish_time = self._parse_datetime(datetime_str)

                # 创建新闻项
                item = NewsItem(
                    title=str(row.get("title", ""))[:100],  # 标题截断
                    content=str(row.get("content", ""))[:300],  # 内容截断
                    source="Tushare",
                    publish_time=publish_time,
                    ticker=self._extract_ticker(row.get("title", "")),  # 尝试提取股票代码
                    url=str(row.get("url", "")) if row.get("url") else None,
                )

                items.append(item)

            return FeedResult(
                total_fetched=len(items),
                new_items=len(items),
                core_items=0,  # 稍后由关键词过滤更新
                items=items,
            )

        except Exception as e:
            logger.error(f"[Tushare流] 获取快讯失败: {e}")
            return FeedResult()

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """解析日期时间字符串"""
        try:
            # Tushare 返回格式：20240227 15:04:53
            if len(datetime_str) >= 12:
                dt = datetime.strptime(datetime_str, "%Y%m%d %H:%M:%S")
                return dt
            return datetime.now()
        except Exception:
            return datetime.now()

    def _extract_ticker(self, title: str) -> Optional[str]:
        """从标题中提取股票代码"""
        import re
        # 匹配常见的股票代码模式
        patterns = [
            r'(\d{6}[\u4e00-\u9fa5]',  # 6位数字
            r'([6]\d{5}\.\d+',          # 600XXX
            r'([0]\d{6}\.\d+',          # 000XXX
            r'(?:[A-Z]+)(\d{6})',    # 英文缩写代码
        ]

        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return match.group(1) if len(match.groups()) > 1 else match.group(2)
        return None

    def stop(self):
        """停止快讯流"""
        self.running = False
        logger.info("[Tushare流] 已停止")


# =============================================================================
# 全局单例
# =============================================================================

_tushare_feed: Optional[TushareNewsFeed] = None


def get_tushare_feed() -> TushareNewsFeed:
    """获取全局快讯流实例"""
    global _tushare_feed
    if _tushare_feed is None:
        token = __import__("os").getenv("TUSHARE_TOKEN", "")
        _tushare_feed = TushareNewsFeed(token)
    return _tushare_feed


# =============================================================================
# 便捷函数
# =============================================================================

async def start_tushare_feed(callback=None):
    """启动 Tushare 快讯监测"""
    feed = get_tushare_feed()
    if feed:
        await feed.start(callback=callback)
    else:
        logger.warning("[Tushare流] 未配置")


async def stop_tushare_feed():
    """停止 Tushare 快讯监测"""
    feed = get_tushare_feed()
    if feed:
        feed.stop()
