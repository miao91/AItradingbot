"""
AI TradeBot - Tavily AI 搜索客户端

严格限流与 Token 裁剪策略：
- search_depth="advanced"
- max_results=3
- 强制 content[:1000] 字符截断
- 禁止获取 raw_content
- 仅返回 content 和 score 字段
"""
import os
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import aiohttp

from shared.logging import get_logger


logger = get_logger(__name__)


@dataclass
class TavilySearchResult:
    """Tavily 搜索结果"""
    title: str
    url: str
    content: str
    score: float
    published_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "score": self.score,
            "published_date": self.published_date
        }


@dataclass
class TavilyResponse:
    """Tavily 响应"""
    success: bool
    query: str
    results: List[TavilySearchResult] = field(default_factory=list)
    answer: Optional[str] = None
    error_message: Optional[str] = None
    total_compressed_chars: int = 0  # 压缩后的总字符数


class TavilyClient:
    """
    Tavily AI 搜索客户端

    严格限流配置：
    - API Key: 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
    - search_depth: "advanced"
    - max_results: 3
    - include_raw_content: False
    - content 字符截断: 1000
    """

    # 严格限制配置
    MAX_RESULTS = 3
    CONTENT_TRUNCATE_LENGTH = 1000  # 每个结果最多 1000 字符
    MAX_TOTAL_CHARS = 3000  # 总共最多 3000 字符
    SEARCH_DEPTH = "advanced"  # 使用高级搜索

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        初始化 Tavily 客户端

        Args:
            api_key: Tavily API Key，默认从环境变量读取
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "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")
        self.timeout = timeout
        self.base_url = "https://api.tavily.com/search"

        if not self.api_key:
            logger.warning("Tavily API Key 未设置")

    async def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        search_depth: str = "advanced",
        include_answer: bool = True,
        include_raw_content: bool = False,  # 强制 False
    ) -> TavilyResponse:
        """
        执行搜索（带严格裁剪）

        Args:
            query: 搜索查询
            max_results: 最大结果数（默认使用 MAX_RESULTS）
            search_depth: 搜索深度
            include_answer: 是否包含 AI 生成的答案
            include_raw_content: 是否包含原始内容（强制 False）

        Returns:
            TavilyResponse 搜索结果
        """
        # 强制限制
        max_results = min(max_results or self.MAX_RESULTS, self.MAX_RESULTS)
        include_raw_content = False  # 强制禁止获取原始内容

        start_time = datetime.now()
        total_compressed = 0

        try:
            logger.info(f"[Tavily] 开始搜索: {query[:50]}...")

            async with aiohttp.ClientSession() as session:
                payload = {
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": search_depth,
                    "max_results": max_results,
                    "include_answer": include_answer,
                    "include_raw_content": include_raw_content,
                    "include_images": False,
                    "include_image_descriptions": False,
                }

                async with session.post(
                    self.base_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"[Tavily] API 错误: {response.status} - {error_text}")
                        return TavilyResponse(
                            success=False,
                            query=query,
                            error_message=f"API 错误: {response.status}"
                        )

                    data = await response.json()

            # 解析结果
            results = []
            for item in data.get("results", []):
                # 强制截断 content
                content = item.get("content", "")
                if len(content) > self.CONTENT_TRUNCATE_LENGTH:
                    content = content[:self.CONTENT_TRUNCATE_LENGTH] + "..."

                # 计算字符数
                char_count = len(content)
                total_compressed += char_count

                # 检查是否超过总限制
                if total_compressed > self.MAX_TOTAL_CHARS:
                    logger.warning(f"[Tavily] 达到字符限制 ({self.MAX_TOTAL_CHARS})，停止添加结果")
                    break

                result = TavilySearchResult(
                    title=item.get("title", "")[:200],  # 标题也限制
                    url=item.get("url", ""),
                    content=content,
                    score=item.get("score", 0.0),
                    published_date=item.get("published_date")
                )
                results.append(result)

            duration = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(
                f"[Tavily] 搜索完成: {len(results)} 结果, "
                f"{total_compressed} 字符, {duration:.0f}ms"
            )

            return TavilyResponse(
                success=True,
                query=query,
                results=results,
                answer=data.get("answer"),
                total_compressed_chars=total_compressed
            )

        except asyncio.TimeoutError:
            logger.error(f"[Tavily] 请求超时")
            return TavilyResponse(
                success=False,
                query=query,
                error_message="请求超时"
            )
        except Exception as e:
            logger.error(f"[Tavily] 搜索异常: {e}")
            return TavilyResponse(
                success=False,
                query=query,
                error_message=str(e)
            )

    async def search_for_stock_event(
        self,
        ticker: str,
        event_description: str,
    ) -> TavilyResponse:
        """
        针对股票事件的专门搜索

        Args:
            ticker: 股票代码
            event_description: 事件描述

        Returns:
            TavilyResponse 搜索结果
        """
        # 构建优化的搜索查询
        query = f"{ticker} {event_description[:100]} 新闻 分析"

        logger.info(f"[Tavily] 股票事件搜索: {ticker}")

        return await self.search(
            query=query,
            max_results=self.MAX_RESULTS,
            search_depth=self.SEARCH_DEPTH,
        )

    def format_results_for_ai(self, response: TavilyResponse) -> str:
        """
        格式化搜索结果供 AI 使用

        返回格式：
        ```
        【Tavily AI 搜索结果 - Top 3 深度源】

        1. [标题](url)
           核心内容摘要...

        2. [标题](url)
           核心内容摘要...

        ...
        ```
        """
        if not response.success or not response.results:
            return "【Tavily AI 搜索】未找到相关结果"

        lines = [
            "【Tavily AI 搜索结果 - Top 3 深度源】",
            f"查询: {response.query}",
            f"压缩字符数: {response.total_compressed_chars}/{self.MAX_TOTAL_CHARS}",
            ""
        ]

        for i, result in enumerate(response.results, 1):
            lines.append(f"{i}. {result.title}")
            lines.append(f"   来源: {result.url}")
            lines.append(f"   相关性: {result.score:.2f}")
            lines.append(f"   内容: {result.content}")
            lines.append("")

        if response.answer:
            lines.append(f"【AI 总结】{response.answer}")

        return "\n".join(lines)


# =============================================================================
# 全局单例
# =============================================================================

_tavily_client: Optional[TavilyClient] = None


def get_tavily_client() -> TavilyClient:
    """获取全局 Tavily 客户端实例"""
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient()
    return _tavily_client


# =============================================================================
# 便捷函数
# =============================================================================

async def search_stock_event(
    ticker: str,
    event_description: str,
) -> str:
    """
    搜索股票事件的便捷函数

    Args:
        ticker: 股票代码
        event_description: 事件描述

    Returns:
        格式化的搜索结果字符串
    """
    client = get_tavily_client()
    response = await client.search_for_stock_event(ticker, event_description)
    return client.format_results_for_ai(response)
