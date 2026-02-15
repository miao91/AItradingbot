"""
AI TradeBot - OpenClaw 实时监测引擎

常驻监控服务，实时抓取财经新闻并触发决策工作流
"""
import asyncio
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
from loguru import logger

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright 未安装，实时监测功能将不可用")


# =============================================================================
# 配置
# =============================================================================

MONITOR_CONFIG = {
    # 信息源配置
    "sources": [
        {
            "name": "eastmoney_announcement",
            "url": "http://data.eastmoney.com/notices/stock.html",
            "refresh_interval": 30,  # 秒
            "selector": ".list-content tbody tr",
            "enabled": True
        },
        {
            "name": "cls_telegraph",
            "url": "https://www.cls.cn/telegraph",
            "refresh_interval": 20,
            "selector": ".telegraph-list-item",
            "enabled": True
        }
    ],

    # 浏览器配置
    "browser": {
        "headless": True,  # 无头模式（静默运行）
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    },

    # 本地存储
    "hash_file": "data/seen_news_hashes.json",

    # 心跳检测
    "heartbeat_interval": 60,  # 秒
    "crash_retry_limit": 3,
    "crash_retry_delay": 10,  # 秒
}


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    url: str
    publish_time: str
    source: str
    content: Optional[str] = None
    ticker: Optional[str] = None  # 提取的股票代码

    def to_hash(self) -> str:
        """生成唯一哈希值用于去重"""
        content = f"{self.title}|{self.publish_time}|{self.source}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# 本地存储管理
# =============================================================================

class HashStore:
    """已抓取新闻的哈希存储"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.hashes: Set[str] = self._load()

    def _load(self) -> Set[str]:
        """从文件加载已见哈希"""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get('hashes', []))
            except Exception as e:
                logger.warning(f"加载哈希文件失败: {e}")
                return set()
        return set()

    def _save(self):
        """保存哈希到文件"""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'hashes': list(self.hashes),
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存哈希文件失败: {e}")

    def add(self, hash_value: str):
        """添加新哈希"""
        if hash_value not in self.hashes:
            self.hashes.add(hash_value)
            self._save()

    def contains(self, hash_value: str) -> bool:
        """检查是否已存在"""
        return hash_value in self.hashes

    def cleanup_old(self, keep_days: int = 7):
        """清理旧哈希（防止文件过大）"""
        # 简化实现：保留最近的 N 条
        if len(self.hashes) > 10000:
            # 保留最近 10000 条
            self.hashes = set(list(self.hashes)[-10000:])
            self._save()
            logger.info(f"清理旧哈希，当前保留 {len(self.hashes)} 条")


# =============================================================================
# 实时监测引擎
# =============================================================================

class LiveMonitor:
    """实时新闻监测引擎"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or MONITOR_CONFIG
        self.hash_store = HashStore(self.config["hash_file"])
        self.running = False
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.pages: Dict[str, Page] = {}
        self.new_news_callback = None  # 回调函数

    def set_callback(self, callback):
        """设置新消息回调"""
        self.new_news_callback = callback

    async def start(self):
        """启动监测"""
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright 未安装，无法启动实时监测")
            return False

        logger.info("=" * 60)
        logger.info("OpenClaw 实时监测引擎启动中...")
        logger.info("=" * 60)

        self.running = True

        # 启动浏览器
        if not await self._launch_browser():
            return False

        # 启动监测任务
        tasks = [
            self._monitor_sources(),
            self._heartbeat_check(),
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"监测任务异常: {e}")
            await self.stop()
            return False

        return True

    async def stop(self):
        """停止监测"""
        logger.info("正在停止实时监测...")
        self.running = False

        if self.browser:
            await self.browser.close()
            logger.info("浏览器已关闭")

    async def _launch_browser(self) -> bool:
        """启动浏览器"""
        retry_count = 0
        max_retries = self.config["crash_retry_limit"]

        while retry_count < max_retries:
            try:
                playwright = await async_playwright().start()

                browser_config = self.config["browser"]
                self.browser = await playwright.chromium.launch(
                    headless=browser_config.get("headless", True),
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                    ] if browser_config.get("headless") else []
                )

                # 创建上下文
                self.context = await self.browser.new_context(
                    user_agent=browser_config.get("user_agent"),
                    viewport={"width": 1920, "height": 1080}
                )

                logger.info(f"浏览器启动成功 (headless={browser_config.get('headless')})")

                # 初始化监控页面
                await self._init_pages()

                return True

            except Exception as e:
                retry_count += 1
                logger.error(f"浏览器启动失败 (尝试 {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(self.config["crash_retry_delay"])

        return False

    async def _init_pages(self):
        """初始化监控页面"""
        for source in self.config["sources"]:
            if not source.get("enabled", True):
                continue

            try:
                page = await self.context.new_page()
                await page.goto(source["url"], wait_until="domcontentloaded", timeout=30000)
                self.pages[source["name"]] = page
                logger.info(f"监控页面已加载: {source['name']} -> {source['url']}")
            except Exception as e:
                logger.error(f"加载页面失败 {source['name']}: {e}")

    async def _monitor_sources(self):
        """监控所有信息源"""
        logger.info("开始监控信息源...")

        while self.running:
            try:
                for source in self.config["sources"]:
                    if not source.get("enabled", True):
                        continue

                    page = self.pages.get(source["name"])
                    if not page:
                        continue

                    # 抓取新闻
                    news_items = await self._fetch_news(page, source)

                    # 处理新消息
                    new_count = 0
                    for news in news_items:
                        if not self.hash_store.contains(news.to_hash()):
                            self.hash_store.add(news.to_hash())
                            new_count += 1

                            # 触发回调
                            if self.new_news_callback:
                                await self._trigger_callback(news)

                    if new_count > 0:
                        logger.info(f"[{source['name']}] 发现 {new_count} 条新消息")

                # 等待下一次轮询
                await asyncio.sleep(min(s.get("refresh_interval", 30) for s in self.config["sources"]))

            except Exception as e:
                logger.error(f"监控过程异常: {e}")
                await asyncio.sleep(10)  # 异常后等待

    async def _fetch_news(self, page: Page, source: Dict) -> List[NewsItem]:
        """从页面抓取新闻"""
        news_items = []

        try:
            # 刷新页面
            await page.reload(wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # 等待动态内容加载

            # 根据不同来源使用不同解析逻辑
            if source["name"] == "eastmoney_announcement":
                news_items = await self._parse_eastmoney(page)
            elif source["name"] == "cls_telegraph":
                news_items = await self._parse_cls(page)
            else:
                news_items = await self._parse_generic(page, source)

        except Exception as e:
            logger.error(f"抓取 {source['name']} 失败: {e}")

        return news_items

    async def _parse_eastmoney(self, page: Page) -> List[NewsItem]:
        """解析东方财富公告"""
        items = []

        try:
            # 等待表格加载
            await page.wait_for_selector(".list-content tbody tr", timeout=10000)

            rows = await page.query_selector_all(".list-content tbody tr")

            for row in rows[:20]:  # 只取最新 20 条
                try:
                    # 提取标题和链接
                    title_el = await row.query_selector("a")
                    if not title_el:
                        continue

                    title = await title_el.inner_text()
                    url = await title_el.get_attribute("href")

                    # 提取时间
                    time_el = await row.query_selector(".time")
                    time_str = await time_el.inner_text() if time_el else datetime.now().strftime("%H:%M:%S")

                    # 提取股票代码（从标题中匹配）
                    import re
                    code_match = re.search(r'(\d{6})', title)
                    ticker = code_match.group(1) + ".SH" if code_match else None

                    items.append(NewsItem(
                        title=title.strip(),
                        url=url or "",
                        publish_time=time_str.strip(),
                        source="eastmoney",
                        ticker=ticker
                    ))

                except Exception as e:
                    logger.debug(f"解析单行失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"解析东方财富页面失败: {e}")

        return items

    async def _parse_cls(self, page: Page) -> List[NewsItem]:
        """解析财联社电报"""
        items = []

        try:
            # 等待电报列表加载
            await page.wait_for_selector(".telegraph-list-item", timeout=10000)

            telegraphs = await page.query_selector_all(".telegraph-list-item")

            for tele in telegraphs[:20]:
                try:
                    # 提取内容
                    content_el = await tele.query_selector(".text")
                    content = await content_el.inner_text() if content_el else ""

                    # 提取时间
                    time_el = await tele.query_selector(".time")
                    time_str = await time_el.inner_text() if time_el else datetime.now().strftime("%H:%M")

                    # 获取链接
                    link_el = await tele.query_selector("a")
                    url = await link_el.get_attribute("href") if link_el else ""

                    items.append(NewsItem(
                        title=content.strip()[:100],  # 截取前100字作为标题
                        url=url or "https://www.cls.cn",
                        publish_time=time_str.strip(),
                        source="cls",
                        content=content.strip()
                    ))

                except Exception as e:
                    logger.debug(f"解析单条电报失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"解析财联社页面失败: {e}")

        return items

    async def _parse_generic(self, page: Page, source: Dict) -> List[NewsItem]:
        """通用解析器"""
        items = []

        try:
            selector = source.get("selector", "a")
            elements = await page.query_selector_all(selector)

            for el in elements[:10]:
                try:
                    title = await el.inner_text()
                    href = await el.get_attribute("href")

                    if title and href:
                        items.append(NewsItem(
                            title=title.strip()[:100],
                            url=href,
                            publish_time=datetime.now().strftime("%H:%M:%S"),
                            source=source["name"]
                        ))

                except Exception:
                    continue

        except Exception as e:
            logger.error(f"通用解析失败: {e}")

        return items

    async def _trigger_callback(self, news: NewsItem):
        """触发新消息回调"""
        if self.new_news_callback:
            try:
                # 在后台任务中执行，避免阻塞监控
                asyncio.create_task(self.new_news_callback(news))
            except Exception as e:
                logger.error(f"回调执行失败: {e}")

    async def _heartbeat_check(self):
        """浏览器心跳检测"""
        logger.info("心跳检测已启动")

        while self.running:
            try:
                await asyncio.sleep(self.config["heartbeat_interval"])

                # 检查浏览器是否存活
                if self.browser:
                    # 尝试获取版本信息
                    if not self.context.pages:
                        logger.warning("浏览器页面丢失，尝试恢复...")
                        await self._init_pages()

            except Exception as e:
                logger.error(f"心跳检测异常: {e}")
                # 尝试重启浏览器
                if self.running:
                    logger.info("尝试重启浏览器...")
                    await self._launch_browser()


# =============================================================================
# 全局单例
# =============================================================================

_live_monitor: Optional[LiveMonitor] = None


def get_live_monitor() -> LiveMonitor:
    """获取全局 LiveMonitor 实例"""
    global _live_monitor
    if _live_monitor is None:
        _live_monitor = LiveMonitor()
    return _live_monitor


# =============================================================================
# 独立运行入口
# =============================================================================

async def main():
    """独立运行监测"""
    monitor = LiveMonitor()

    # 示例回调
    async def on_news(news: NewsItem):
        logger.info(f"🔔 新消息: {news.title[:50]}...")

    monitor.set_callback(on_news)

    try:
        await monitor.start()
    except KeyboardInterrupt:
        logger.info("收到停止信号")
        await monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
