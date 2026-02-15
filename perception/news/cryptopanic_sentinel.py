"""
AI TradeBot - CryptoPanic 加密哨兵（冷处理版）

实时监测全球加密货币市场快讯
基于 CryptoPanic API

⚠️ 冷处理模式：
- 默认 is_active=False，不启动加密货币监测
- 保留完整代码，等需要时在 .env 设置 ENABLE_CRYPTO=true 即可激活
- 总工决策："代码先行，模块挂起"，确保内置 AI 引擎全功率运行
"""
import asyncio
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import aiohttp

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

CRYPTOPANIC_CONFIG = {
    # API 密钥（需在 .env 中配置 CRYPTOPANIC_API_KEY）
    "api_key": "",

    # 冷处理开关（默认 False）
    "is_active": os.getenv("ENABLE_CRYPTO", "false").lower() == "true",

    # 轮询配置
    "poll_interval": 30,  # 秒，加密市场变化更快
    "max_results_per_call": 50,

    # 增量过滤关键词
    "keywords": {
        "core": [
            # 价格相关
            "pump", "dump", "moon", "crash", "pump", "surge",
            "突破", "跌破", "暴涨", "暴跌",

            # 事件相关
            "halving", "减半", "fork", "升级",
            "regulation", "监管", "ban", "禁用", "批准",
            "etf", "ETF", "fund", "基金", "融资", "investment",
            "partnership", "合作", "listing", "上币", "launch",

            # 技术相关
            "mainnet", "主网", "upgrade", "hardfork",
            "hack", "攻击", "漏洞", "exploit",

            # 公司相关
            "财报", "收益", "营收", "利润", "回购",
            "audit", "审计", "security", "安全",

            # 币种名称（主流币）
            "BTC", "ETH", "bitcoin", "ethereum",
            "SOL", "solana", "ADA", "cardano",
        ],
        "ignore": [
            "analysis", "分析", "预测", "观点",
            "recipe", "教程", "guide", "指南",
            "meme", "梗图", "表情", "emoji",
            "fud", "fomo", "hodl", "diamond hands",
        ]
    },
}


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class CryptoNewsItem:
    """加密新闻项"""
    title: str
    content: str
    source: str
    publish_time: datetime
    url: Optional[str] = None
    related_coins: List[str] = field(default_factory=list)

    # 过滤标记
    is_core_keyword: bool = False
    is_ignore_keyword: bool = False

    def __hash__(self):
        return hash((self.title, self.publish_time, self.url))


# =============================================================================
# CryptoPanic 哨兵
# =============================================================================

class CryptoPanicSentinel:
    """
    CryptoPanic 加密哨兵（冷处理版）

    实时监测全球加密货币市场快讯

    ⚠️ 冷处理模式：
    - 默认不启动加密货币监测
    - 在 .env 设置 ENABLE_CRYPTO=true 激活
    """

    def __init__(self, api_key: str, config: Optional[Dict] = None):
        """初始化哨兵"""
        self.api_key = api_key
        self.config = config or CRYPTOPANIC_CONFIG
        self.running = False
        self.is_active = self.config.get("is_active", False)
        self.processed_hashes: Set[str] = set()

        # 冷处理模式日志
        if not self.is_active:
            logger.info(
                "[CryptoPanic哨兵] 🌙 冷处理模式: Crypto Stream (Offline) - "
                "代码保留但未激活加密货币监测，内置 AI 引擎全功率运行"
            )
            logger.info(
                "[CryptoPanic哨兵] 💡 提示: 在 .env 设置 ENABLE_CRYPTO=true 即可激活"
            )
        else:
            logger.info(
                f"[CryptoPanic哨兵] 初始化完成: "
                f"轮询间隔={self.config['poll_interval']}s, "
                f"关键词={len(self.config['keywords']['core'])}"
            )

    async def start(self, callback=None):
        """启动哨兵（冷处理：如果 is_active=False 则不启动）"""
        # 冷处理检查
        if not self.is_active:
            logger.info(
                "[CryptoPanic哨兵] 🌙 Crypto Stream 处于静默模式 - "
                "跳过加密货币监测初始化"
            )
            return False

        if self.running:
            logger.warning("[CryptoPanic哨兵] 已在运行中")
            return False

        self.running = True
        self.callback = callback

        logger.info("[CryptoPanic哨兵] 启动实时监测...")

        while self.running:
            try:
                # 获取最新新闻
                news = await self._fetch_latest_news()

                # 过滤和处理
                if news:
                    # 去重
                    new_items = [
                        item for item in news
                        if hash(item) not in self.processed_hashes
                    ]

                    # 增量过滤：仅处理包含核心关键词的
                    core_items = [
                        item for item in new_items
                        if item.is_core_keyword
                    ]

                    # 记录已处理
                    for item in new_items:
                        self.processed_hashes.add(hash(item))

                    logger.info(
                        f"[CryptoPanic哨兵] 获取 {len(news)} 条, "
                        f"新增 {len(new_items)} 条, "
                        f"核心 {len(core_items)} 条"
                    )

                    # 触发回调
                    if core_items and self.callback:
                        for item in core_items:
                            await self.callback(item)

                # 等待下次轮询
                await asyncio.sleep(self.config["poll_interval"])

            except Exception as e:
                logger.error(f"[CryptoPanic哨兵] 轮询异常: {e}")
                await asyncio.sleep(10)  # 异常后等待 10 秒

    async def _fetch_latest_news(self) -> List[CryptoNewsItem]:
        """获取最新新闻"""
        if not self.api_key:
            logger.warning("[CryptoPanic哨兵] API Key 未设置")
            return []

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                params = {
                    "limit": self.config["max_results_per_call"],
                    "sort": "published_at.desc",
                }

                async with session.get(
                    "https://api.cryptopanic.com/v1/news",
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        logger.error(f"[CryptoPanic] API 错误: {response.status}")
                        return []

                    data = await response.json()

                    if not data.get("data"):
                        return []

                    items = []
                    for article in data["data"]:
                        # 解析相关币种
                        related_coins = self._extract_coins(article)

                        # 创建新闻项
                        item = CryptoNewsItem(
                            title=article.get("title", "")[:100],
                            content=article.get("body", "")[:200],
                            source="CryptoPanic",
                            publish_time=datetime.fromisoformat(
                                article.get("published_at", "")
                                .replace("Z", "+00:00")
                            ),
                            url=article.get("url", ""),
                            related_coins=related_coins,
                        )

                        # 关键词检测
                        item.is_core_keyword = self._check_keywords(item)
                        item.is_ignore_keyword = self._check_ignore_keywords(item)

                        items.append(item)

                    return items

        except Exception as e:
            logger.error(f"[CryptoPanic哨兵] 获取新闻失败: {e}")
            return []

    def _extract_coins(self, article: Dict) -> List[str]:
        """从文章中提取相关币种"""
        coins = []

        # 从标题中提取
        title = article.get("title", "")
        for coin in ["BTC", "ETH", "SOL", "ADA", "DOGE", "MATIC", "AVAX"]:
            if coin.upper() in title.upper():
                coins.append(coin)

        # 从标签中提取（如果有）
        # CryptoPanic API 可能提供 coins 字段
        if "coins" in article and isinstance(article["coins"], list):
            coins.extend(article["coins"])

        return list(set(coins))  # 去重

    def _check_keywords(self, item: CryptoNewsItem) -> bool:
        """检查是否包含核心关键词"""
        text = (item.title + " " + item.content).lower()

        # 检查核心关键词
        for keyword in self.config["keywords"]["core"]:
            if keyword.lower() in text:
                return True

        return False

    def _check_ignore_keywords(self, item: CryptoNewsItem) -> bool:
        """检查是否包含忽略关键词"""
        text = (item.title + " " + item.content).lower()

        # 检查忽略关键词
        for keyword in self.config["keywords"]["ignore"]:
            if keyword.lower() in text:
                return True

        return False

    def stop(self):
        """停止哨兵"""
        self.running = False
        logger.info("[CryptoPanic哨兵] 已停止")


# =============================================================================
# 全局单例
# =============================================================================

_cryptopanic_sentinel: Optional[CryptoPanicSentinel] = None


def get_cryptopanic_sentinel() -> CryptoPanicSentinel:
    """获取全局哨兵实例"""
    global _cryptopanic_sentinel
    if _cryptopanic_sentinel is None:
        api_key = __import__("os").getenv("CRYPTOPANIC_API_KEY", "")
        _cryptopanic_sentinel = CryptoPanicSentinel(api_key)
    return _cryptopanic_sentinel


# =============================================================================
# 便捷函数
# =============================================================================

async def start_cryptopanic_monitoring(callback=None):
    """
    启动 CryptoPanic 监测（冷处理：如果未激活则跳过）

    Returns:
        bool: 是否成功启动（False 表示冷处理模式）
    """
    sentinel = get_cryptopanic_sentinel()

    # 检查是否激活
    if not sentinel.is_active:
        logger.info("[CryptoPanic哨兵] 🌙 Crypto Stream 静默中 (ENABLE_CRYPTO=false)")
        return False

    await sentinel.start(callback=callback)
    return True


def is_cryptopanic_active() -> bool:
    """
    检查 CryptoPanic 监测是否处于激活状态

    Returns:
        bool: True=已激活，False=冷处理模式
    """
    sentinel = get_cryptopanic_sentinel()
    return sentinel.is_active
