"""
AI TradeBot - OpenClaw 浏览器引擎

功能：
1. 使用 Playwright 实现 headless 浏览器自动化
2. deep_fetch(url) 深度抓取网页内容
3. Anti-Bot 策略（User-Agent、反爬虫）
4. 异常处理（验证码、403等）
"""
import asyncio
import os
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from pydantic import BaseModel
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

# playwright-stealth 是可选依赖
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
    logger = None  # 临时设置，后面会重新初始化

from shared.logging import get_logger
from shared.constants import TIMEZONE


logger = get_logger(__name__)


# =============================================================================
# 数据模型
# =============================================================================

class FetchResult(BaseModel):
    """网页抓取结果"""
    url: str
    success: bool
    title: Optional[str] = None
    content: str = ""
    html: Optional[str] = None
    status_code: int = 0
    error_message: Optional[str] = None
    fetch_time: float = 0  # 抓取耗时（秒）
    timestamp: datetime = None
    metadata: Dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed = True


class CrawlStatus(str):
    """爬取状态枚举"""
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"  # 被反爬虫拦截
    CAPTCHA = "captcha"  # 需要验证码
    TIMEOUT = "timeout"
    ERROR = "error"


# =============================================================================
# 配置
# =============================================================================

class BrowserConfig:
    """浏览器配置"""

    # 默认 User-Agent
    DEFAULT_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    # 反爬虫配置
    HEADLESS: bool = True
    TIMEOUT: int = 30000  # 毫秒
    WAIT_FOR_SELECTOR: str = "body"  # 默认等待body加载
    WAIT_TIMEOUT: int = 5000

    # 浏览器窗口大小
    VIEWPORT_WIDTH = 1920
    VIEWPORT_HEIGHT = 1080

    # 是否启用 stealth 模式
    ENABLE_STEALTH = True


# =============================================================================
# OpenClaw 引擎
# =============================================================================

class OpenClawEngine:
    """
    OpenClaw 浏览器引擎

    功能：
    1. 异步 Playwright 浏览器管理
    2. 深度网页抓取
    3. 反爬虫策略
    4. 异常处理和状态检测
    """

    def __init__(
        self,
        headless: Optional[bool] = None,
        user_agent: Optional[str] = None,
        timeout: Optional[int] = None,
        enable_stealth: bool = True,
    ):
        """
        初始化 OpenClaw 引擎

        Args:
            headless: 是否无头模式，默认从环境变量读取
            user_agent: 自定义 User-Agent
            timeout: 超时时间（毫秒）
            enable_stealth: 是否启用反检测模式
        """
        # 从环境变量读取配置
        self.headless = headless if headless is not None else os.getenv("OPENCLAW_HEADLESS", "true").lower() == "true"
        self.timeout = timeout or int(os.getenv("OPENCLAW_TIMEOUT", "30000"))
        self.enable_stealth = enable_stealth and os.getenv("OPENCLAW_ENABLE_STEALTH", "true").lower() == "true"

        # User-Agent 配置
        if user_agent:
            self.user_agent = user_agent
        else:
            import random
            self.user_agent = random.choice(BrowserConfig.DEFAULT_USER_AGENTS)

        # 浏览器实例
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

        logger.info(f"OpenClaw Engine initialized: headless={self.headless}, stealth={self.enable_stealth}")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()

    async def start(self) -> None:
        """启动浏览器"""
        if self.browser is not None:
            logger.warning("Browser already started")
            return

        try:
            self.playwright = await async_playwright().start()

            # 启动浏览器
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            # 创建上下文
            self.context = await self.browser.new_context(
                viewport={'width': BrowserConfig.VIEWPORT_WIDTH, 'height': BrowserConfig.VIEWPORT_HEIGHT},
                user_agent=self.user_agent,
                locale='zh-CN',
                timezone_id=TIMEZONE,
            )

            # 设置额外的反检测头
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en']
                });
            """)

            logger.info("Browser started successfully")

        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            raise

    async def close(self) -> None:
        """关闭浏览器"""
        try:
            if self.context:
                await self.context.close()
                self.context = None

            if self.browser:
                await self.browser.close()
                self.browser = None

            if self.playwright:
                await self.playwright.stop()
                self.playwright = None

            logger.info("Browser closed")

        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    async def _create_page(self) -> Page:
        """创建新页面"""
        if not self.context:
            await self.start()

        page = await self.context.new_page()

        # 应用 stealth 插件（如果可用）
        if self.enable_stealth and STEALTH_AVAILABLE:
            try:
                await stealth_async(page)
            except Exception as e:
                logger.debug(f"Stealth plugin failed (non-critical): {e}")
        elif self.enable_stealth and not STEALTH_AVAILABLE:
            logger.debug("Stealth plugin not installed, skipping anti-detection")

        return page

    async def deep_fetch(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        wait_timeout: Optional[int] = None,
        extract_text: bool = True,
        screenshot: bool = False,
    ) -> FetchResult:
        """
        深度抓取网页内容

        Args:
            url: 目标 URL
            wait_for_selector: 等待的 CSS 选择器
            wait_timeout: 等待超时时间（毫秒）
            extract_text: 是否提取文本内容
            screenshot: 是否保存截图

        Returns:
            FetchResult 抓取结果
        """
        start_time = asyncio.get_event_loop().time()

        result = FetchResult(
            url=url,
            success=False,
            timestamp=datetime.now(),
        )

        page = None

        try:
            logger.info(f"Fetching: {url}")

            # 创建页面
            page = await self._create_page()

            # 导航到目标 URL
            response = await page.goto(
                url,
                wait_until="networkidle",
                timeout=self.timeout,
            )

            # 检查响应状态
            if response:
                result.status_code = response.status

                # 检测是否被拦截
                if response.status == 403:
                    result.error_message = "Access forbidden (403)"
                    result.metadata["status"] = CrawlStatus.BLOCKED
                    logger.warning(f"Blocked by server: {url}")
                    return result

                elif response.status == 404:
                    result.error_message = "Not found (404)"
                    result.metadata["status"] = CrawlStatus.ERROR
                    logger.warning(f"Page not found: {url}")
                    return result

            # 获取页面标题
            result.title = await page.title()

            # 等待特定元素（如果指定）
            if wait_for_selector:
                try:
                    await page.wait_for_selector(
                        wait_for_selector,
                        timeout=wait_timeout or self.WAIT_TIMEOUT
                    )
                    logger.debug(f"Selector found: {wait_for_selector}")
                except Exception as e:
                    logger.warning(f"Selector not found: {wait_for_selector}, {e}")

            # 检测验证码
            if await self._detect_captcha(page):
                result.error_message = "CAPTCHA detected"
                result.metadata["status"] = CrawlStatus.CAPTCHA
                logger.warning(f"CAPTCHA detected: {url}")

                # 保存截图用于调试
                if screenshot:
                    screenshot_path = Path("data/temp") / f"captcha_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=str(screenshot_path))
                    result.metadata["screenshot"] = str(screenshot_path)

                return result

            # 提取内容
            if extract_text:
                result.content = await page.inner_text("body")
                logger.debug(f"Content extracted: {len(result.content)} characters")

            # 获取 HTML（如果需要）
            result.html = await page.content()

            # 保存截图（如果需要）
            if screenshot:
                screenshot_path = Path("data/temp") / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(screenshot_path), full_page=True)
                result.metadata["screenshot"] = str(screenshot_path)

            # 标记成功
            result.success = True
            result.metadata["status"] = CrawlStatus.SUCCESS

            # 计算耗时
            result.fetch_time = asyncio.get_event_loop().time() - start_time

            logger.info(f"Fetch successful: {url} ({result.fetch_time:.2f}s)")
            return result

        except asyncio.TimeoutError:
            result.error_message = f"Timeout after {self.timeout}ms"
            result.metadata["status"] = CrawlStatus.TIMEOUT
            logger.error(f"Fetch timeout: {url}")
            return result

        except Exception as e:
            result.error_message = str(e)
            result.metadata["status"] = CrawlStatus.ERROR
            logger.error(f"Fetch error: {url}, {e}")
            return result

        finally:
            # 关闭页面
            if page:
                try:
                    await page.close()
                except:
                    pass

            # 计算总耗时
            result.fetch_time = asyncio.get_event_loop().time() - start_time

    async def _detect_captcha(self, page: Page) -> bool:
        """
        检测页面是否包含验证码

        Args:
            page: Playwright 页面对象

        Returns:
            是否检测到验证码
        """
        captcha_keywords = [
            "captcha",
            "验证码",
            "人机验证",
            "recaptcha",
            "hcaptcha",
            "geetest",
            "滑块验证",
        ]

        try:
            # 检查页面标题
            title = await page.title()
            title_lower = title.lower()

            for keyword in captcha_keywords:
                if keyword in title_lower:
                    return True

            # 检查页面内容
            body_text = await page.inner_text("body")
            body_text_lower = body_text.lower()

            for keyword in captcha_keywords:
                if keyword in body_text_lower:
                    return True

            # 检查常见的验证码 iframe
            captchas = await page.query_selector_all("iframe[src*='recaptcha'], iframe[src*='hcaptcha']")
            if captchas:
                return True

            return False

        except Exception as e:
            logger.debug(f"Error detecting captcha: {e}")
            return False

    async def fetch_multiple(
        self,
        urls: List[str],
        concurrent_limit: int = 3,
        **kwargs
    ) -> List[FetchResult]:
        """
        并发抓取多个 URL

        Args:
            urls: URL 列表
            concurrent_limit: 并发限制
            **kwargs: 传递给 deep_fetch 的参数

        Returns:
            FetchResult 列表
        """
        semaphore = asyncio.Semaphore(concurrent_limit)

        async def fetch_with_semaphore(url: str) -> FetchResult:
            async with semaphore:
                return await self.deep_fetch(url, **kwargs)

        tasks = [fetch_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(FetchResult(
                    url=urls[i],
                    success=False,
                    error_message=str(result),
                    metadata={"status": CrawlStatus.ERROR},
                    timestamp=datetime.now(),
                ))
            else:
                final_results.append(result)

        return final_results


# =============================================================================
# 便捷函数
# =============================================================================

async def deep_fetch(
    url: str,
    headless: bool = True,
    **kwargs
) -> FetchResult:
    """
    深度抓取网页的便捷函数

    Args:
        url: 目标 URL
        headless: 是否无头模式
        **kwargs: 其他参数

    Returns:
        FetchResult 抓取结果
    """
    async with OpenClawEngine(headless=headless) as engine:
        return await engine.deep_fetch(url, **kwargs)


async def quick_fetch(url: str, timeout: int = 10000) -> str:
    """
    快速抓取网页文本内容

    Args:
        url: 目标 URL
        timeout: 超时时间（毫秒）

    Returns:
        页面文本内容
    """
    result = await deep_fetch(url, wait_timeout=timeout)
    return result.content if result.success else ""
