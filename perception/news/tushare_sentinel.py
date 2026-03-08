"""
AI TradeBot - Tushare 股票哨兵（升级版）

实时监测 A 股市场快讯，基于 Tushare Pro API
集成 DeepSeek 快速打分系统
"""
import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

import tushare as ts
from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

TUSHARE_SENTINEL_CONFIG = {
    "token": "",  # 需在 .env 中配置 TUSHARE_TOKEN
    "poll_interval": 60,  # 秒
    "max_results_per_call": 100,
    "classification_threshold": float(os.getenv("NEWS_CLASSIFICATION_THRESHOLD", "7.0")),
    "sources": {
        "sina": "新浪财经",
        "cls": "财联社",
    },
    "keywords": {
        "core": [
            "涨停", "异动", "大涨", "暴跌",
            "减半", "分红", "回购", "增持",
            "监管", "政策", "法案", "批准",
            "融资", "定增", "重组", "并购",
            "业绩", "财报", "预告", "快讯"
        ],
        "ignore": [
            "博主", "观点", "认为", "看好",
            "减肥", "美容", "健康", "娱乐",
            "体育", "游戏", "汽车", "房产",
            "天气", "教育", "旅游"
        ]
    },
}


# =============================================================================
# 数据类
# =============================================================================

class SourceType(Enum):
    """数据源类型"""
    SINA = "sina"
    CLS = "cls"


@dataclass
class NewsItem:
    """新闻项"""
    title: str
    content: str
    source: str
    source_type: SourceType
    publish_time: datetime
    url: Optional[str] = None
    ticker: Optional[str] = None

    # 分类标记
    is_core_keyword: bool = False
    is_ignore_keyword: bool = False

    # AI 分类结果
    score: float = 0.0
    category: str = "unknown"
    valuation_level: str = "none"
    duration_estimate: str = "unknown"
    sentiment: str = "neutral"

    def __hash__(self):
        return hash((self.title, self.publish_time, self.url))


# =============================================================================
# Tushare 哨兵（升级版）
# =============================================================================

class TushareSentinel:
    """
    Tushare 股票哨兵（升级版）

    实时监测 A 股市场快讯，集成 DeepSeek 快速打分
    """

    def __init__(self, token: str, config: Optional[Dict] = None):
        """初始化哨兵"""
        self.token = token
        self.config = config or TUSHARE_SENTINEL_CONFIG
        self.running = False
        self.processed_hashes: Set[str] = set()
        self.classification_enabled = True

        # DeepSeek 客户端
        self._deepseek_client = None

        # 设置 Tushare token
        if token:
            ts.set_token(token)

        logger.info(
            f"[Tushare哨兵] 初始化完成: "
            f"轮询间隔={self.config['poll_interval']}s, "
            f"评分阈值={self.config['classification_threshold']}"
        )

    async def start(self, callback: Optional[Callable[[NewsItem], Awaitable[None]]] = None):
        """启动哨兵"""
        if self.running:
            logger.warning("[Tushare哨兵] 已在运行中")
            return

        self.running = True
        self.callback = callback

        logger.info("[Tushare哨兵] 启动实时监测...")

        while self.running:
            try:
                # 获取新闻
                all_news = []

                cls_news = await self._fetch_cls_news()
                all_news.extend(cls_news)

                sina_news = await self._fetch_sina_news()
                all_news.extend(sina_news)

                # 过滤和处理
                if all_news:
                    new_items = [
                        item for item in all_news
                        if hash(item) not in self.processed_hashes
                    ]

                    # AI 分类评分
                    if self.classification_enabled:
                        await self._classify_items(new_items)

                    # 过滤高分新闻
                    high_score_items = [
                        item for item in new_items
                        if item.score >= self.config["classification_threshold"]
                    ]

                    # 标记已处理
                    for item in high_score_items:
                        self.processed_hashes.add(hash(item))

                    logger.info(
                        f"[Tushare哨兵] 获取 {len(all_news)} 条, "
                        f"新增 {len(new_items)} 条, "
                        f"高分 ({self.config['classification_threshold']}+) {len(high_score_items)} 条"
                    )

                    # 触发回调
                    if high_score_items and self.callback:
                        for item in high_score_items:
                            await self.callback(item)

                await asyncio.sleep(self.config["poll_interval"])

            except Exception as e:
                logger.error(f"[Tushare哨兵] 轮询异常: {e}")
                await asyncio.sleep(10)

    async def _fetch_cls_news(self) -> List[NewsItem]:
        """获取财联社快讯"""
        try:
            pro = ts.pro_api()

            # 使用 major_news 接口获取长篇通讯
            df = pro.major_news(fields="title,pub_time,src,url")

            if df is None or df.empty:
                return []

            items = []
            for _, row in df.iterrows():
                # 解析时间格式 "2026-02-28 22:43:30"
                pub_time = str(row.get("pub_time", ""))
                try:
                    publish_time = datetime.strptime(pub_time, "%Y-%m-%d %H:%M:%S")
                except:
                    publish_time = datetime.now()

                item = NewsItem(
                    title=str(row.get("title", ""))[:100],
                    content="",  # major_news 没有 content 字段
                    source=str(row.get("src", "财联社")),
                    source_type=SourceType.CLS,
                    publish_time=publish_time,
                    url=str(row.get("url", "")) if row.get("url") else None,
                )

                item.is_core_keyword = self._check_keywords(item)
                item.is_ignore_keyword = self._check_ignore_keywords(item)

                items.append(item)

            logger.info(f"[Tushare] major_news 获取 {len(items)} 条新闻")
            return items[:self.config["max_results_per_call"]]

        except Exception as e:
            logger.error(f"[Tushare] 财联社获取失败: {e}")
            return []

    async def _fetch_sina_news(self) -> List[NewsItem]:
        """获取新浪财经快讯"""
        try:
            pro = ts.pro_api()

            # 使用 news 接口获取新闻
            df = pro.news(fields="datetime,content,title")

            if df is None or df.empty:
                return []

            items = []
            for _, row in df.iterrows():
                # 解析时间格式 "2026-02-28 22:43:30"
                dt_str = str(row.get("datetime", ""))
                try:
                    publish_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                except:
                    publish_time = datetime.now()

                # news 接口的 title 通常是 None，使用 content 作为标题
                title = str(row.get("title", ""))[:100] if row.get("title") else ""
                content = str(row.get("content", ""))[:200] if row.get("content") else ""

                # 如果 title 为空，使用 content 的前100个字符作为标题
                if not title and content:
                    title = content[:100]

                item = NewsItem(
                    title=title,
                    content=content,
                    source="新浪财经",
                    source_type=SourceType.SINA,
                    publish_time=publish_time,
                )

                item.is_core_keyword = self._check_keywords(item)
                item.is_ignore_keyword = self._check_ignore_keywords(item)

                items.append(item)

            logger.info(f"[Tushare] news 获取 {len(items)} 条新闻")
            return items[:self.config["max_results_per_call"]]

        except Exception as e:
            logger.error(f"[Tushare] 新浪获取失败: {e}")
            return []

    async def _classify_items(self, items: List[NewsItem]):
        """使用 DeepSeek 对新闻进行分类评分"""
        if not self._deepseek_client:
            try:
                from decision.ai_matrix.deepseek.client import get_deepseek_client
                self._deepseek_client = await get_deepseek_client()
            except Exception as e:
                logger.warning(f"[Tushare哨兵] DeepSeek 客户端初始化失败: {e}")
                self.classification_enabled = False
                return

        for item in items:
            try:
                from decision.ai_matrix.deepseek.client import NewsClassificationResult
                result: NewsClassificationResult = await self._deepseek_client.classify_news(
                    title=item.title,
                    content=item.content,
                    source=item.source
                )

                # 更新新闻项
                item.ticker = result.ticker
                item.score = result.score
                item.category = result.category
                item.valuation_level = result.valuation_level
                item.duration_estimate = result.duration_estimate
                item.sentiment = result.sentiment

                logger.debug(
                    f"[Tushare哨兵] 新闻评分: {item.title[:30]}... "
                    f"= {item.score}/10 ({item.valuation_level})"
                )

            except Exception as e:
                logger.error(f"[Tushare哨兵] 分类失败: {e}")
                # 保持默认值

    def _parse_datetime(self, datetime_str: str) -> datetime:
        """解析日期时间字符串"""
        try:
            if len(datetime_str) >= 12:
                dt = datetime.strptime(datetime_str, "%Y%m%d %H:%M:%S")
                return dt
            return datetime.now()
        except Exception:
            return datetime.now()

    def _check_keywords(self, item: NewsItem) -> bool:
        """检查是否包含核心关键词"""
        text = (item.title + " " + item.content).lower()

        for keyword in self.config["keywords"]["core"]:
            if keyword in text:
                return True

        return False

    def _check_ignore_keywords(self, item: NewsItem) -> bool:
        """检查是否包含忽略关键词"""
        text = (item.title + " " + item.content).lower()

        for keyword in self.config["keywords"]["ignore"]:
            if keyword in text:
                return True

        return False

    def stop(self):
        """停止哨兵"""
        self.running = False
        logger.info("[Tushare哨兵] 已停止")


# =============================================================================
# 全局单例
# =============================================================================

_tushare_sentinel: Optional[TushareSentinel] = None


def get_tushare_sentinel() -> TushareSentinel:
    """获取全局哨兵实例"""
    global _tushare_sentinel
    if _tushare_sentinel is None:
        token = os.getenv("TUSHARE_TOKEN", "")
        _tushare_sentinel = TushareSentinel(token)
    return _tushare_sentinel


# =============================================================================
# 便捷函数
# =============================================================================

async def start_tushare_monitoring(callback=None):
    """启动 Tushare 监测"""
    sentinel = get_tushare_sentinel()
    await sentinel.start(callback=callback)
