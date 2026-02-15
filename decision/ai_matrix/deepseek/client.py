"""
AI TradeBot - DeepSeek AI 客户端

DeepSeek API 客户端，用于快速新闻分类、评分和推理
"""
import os
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from shared.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

DEEPSEEK_CONFIG = {
    "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
    "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    "max_tokens": int(os.getenv("DEEPSEEK_MAX_TOKENS", "4000")),
    "temperature": float(os.getenv("DEEPSEEK_TEMPERATURE", "0.3")),
}


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class NewsClassificationResult:
    """新闻分类结果"""
    ticker: Optional[str]  # 股票代码
    score: float  # 评分 0-10
    category: str  # 分类
    valuation_level: str  # 估值级别: none, low, medium, high, extreme
    duration_estimate: str  # 影响时长估计
    reasoning: str  # 推理过程
    sentiment: str  # 情感: positive, negative, neutral


# =============================================================================
# DeepSeek 客户端
# =============================================================================

class DeepSeekClient:
    """
    DeepSeek AI 客户端

    专用于快速新闻分类和评分
    """

    def __init__(self, config: Optional[Dict] = None):
        """初始化客户端"""
        self.config = config or DEEPSEEK_CONFIG
        self.session: Optional[aiohttp.ClientSession] = None

        if not self.config["api_key"]:
            logger.warning("[DeepSeek] API Key 未设置")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()

    async def classify_news(
        self,
        title: str,
        content: str,
        source: str = "",
    ) -> NewsClassificationResult:
        """
        分类新闻并评分

        Args:
            title: 新闻标题
            content: 新闻内容
            source: 新闻来源

        Returns:
            NewsClassificationResult 分类结果
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        if not self.config["api_key"]:
            # 返回默认结果
            return NewsClassificationResult(
                ticker=None,
                score=0.0,
                category="unknown",
                valuation_level="none",
                duration_estimate="unknown",
                reasoning="API Key 未配置",
                sentiment="neutral"
            )

        # 构建提示词
        prompt = self._build_classification_prompt(title, content, source)

        try:
            headers = {
                "Authorization": f"Bearer {self.config['api_key']}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.config["model"],
                "messages": [
                    {
                        "role": "system",
                        "content": "你是AI TradeBot的新闻分析专家。请严格按照JSON格式输出分类结果。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": self.config["max_tokens"],
                "temperature": self.config["temperature"],
                "response_format": {"type": "json_object"}
            }

            async with self.session.post(
                f"{self.config['base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"[DeepSeek] API 错误: {response.status} - {error_text}")
                    return self._default_result()

                data = await response.json()

                # 解析响应
                content = data["choices"][0]["message"]["content"]
                result = self._parse_classification_result(content)

                logger.info(
                    f"[DeepSeek] 新闻分类完成: "
                    f"评分={result.score}/10, "
                    f"级别={result.valuation_level}, "
                    f"分类={result.category}"
                )

                return result

        except asyncio.TimeoutError:
            logger.error("[DeepSeek] 请求超时")
            return self._default_result()
        except Exception as e:
            logger.error(f"[DeepSeek] 分类失败: {e}")
            return self._default_result()

    def _build_classification_prompt(
        self,
        title: str,
        content: str,
        source: str
    ) -> str:
        """构建分类提示词"""
        return f"""请分析以下新闻并返回JSON格式的分类结果：

新闻标题：{title}
新闻内容：{content[:500]}...
新闻来源：{source}

请按以下JSON格式返回（严格按此格式，不要添加其他内容）：
{{
    "ticker": "提取的股票代码（如600000.SH），如无则为null",
    "score": 评分（0-10的浮点数，仅对重大事件给7分以上），
    "category": "分类（以下之一：policy, earnings, m_and_a, technical, market, other）",
    "valuation_level": "估值级别（以下之一：none, low, medium, high, extreme）",
    "duration_estimate": "影响时长估计（如：1-3天，1周，1个月等）",
    "reasoning": "简短的评分理由（1-2句话）",
    "sentiment": "情感倾向（positive, negative, neutral）
}}

评分标准：
- 0-3分：常规新闻、无实质影响
- 4-6分：有一定影响的中等新闻
- 7-8分：重要新闻，可能引发显著价格波动
- 9-10分：重大突发事件，具有重塑性影响

请立即返回JSON结果："""

    def _parse_classification_result(self, content: str) -> NewsClassificationResult:
        """解析分类结果"""
        import json

        try:
            data = json.loads(content)
            return NewsClassificationResult(
                ticker=data.get("ticker"),
                score=float(data.get("score", 0)),
                category=data.get("category", "other"),
                valuation_level=data.get("valuation_level", "none"),
                duration_estimate=data.get("duration_estimate", "unknown"),
                reasoning=data.get("reasoning", ""),
                sentiment=data.get("sentiment", "neutral")
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"[DeepSeek] 解析结果失败: {e}")
            return self._default_result()

    def _default_result(self) -> NewsClassificationResult:
        """返回默认结果"""
        return NewsClassificationResult(
            ticker=None,
            score=0.0,
            category="other",
            valuation_level="none",
            duration_estimate="unknown",
            reasoning="分类失败",
            sentiment="neutral"
        )

    async def quick_score(self, text: str) -> float:
        """
        快速评分（仅返回分数）

        Args:
            text: 待评分文本

        Returns:
            float 评分 (0-10)
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        if not self.config["api_key"]:
            return 0.0

        try:
            headers = {
                "Authorization": f"Bearer {self.config['api_key']}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.config["model"],
                "messages": [
                    {
                        "role": "system",
                        "content": "你是新闻评分专家。请仅返回一个0-10的数字。"
                    },
                    {
                        "role": "user",
                        "content": f"请给以下新闻打分（0-10），仅返回数字：\n\n{text[:300]}"
                    }
                ],
                "max_tokens": 10,
                "temperature": 0.1
            }

            async with self.session.post(
                f"{self.config['base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    return 0.0

                data = await response.json()
                content = data["choices"][0]["message"]["content"].strip()

                # 尝试解析数字
                import re
                match = re.search(r'(\d+\.?\d*)', content)
                if match:
                    score = float(match.group(1))
                    return min(max(score, 0), 10)

                return 0.0

        except Exception as e:
            logger.error(f"[DeepSeek] 快速评分失败: {e}")
            return 0.0


# =============================================================================
# 全局单例
# =============================================================================

_deepseek_client: Optional[DeepSeekClient] = None


async def get_deepseek_client() -> DeepSeekClient:
    """获取全局 DeepSeek 客户端实例"""
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = DeepSeekClient()
        await _deepseek_client.__aenter__()
    return _deepseek_client


async def close_deepseek_client():
    """关闭 DeepSeek 客户端"""
    global _deepseek_client
    if _deepseek_client:
        await _deepseek_client.__aexit__(None, None, None)
        _deepseek_client = None
