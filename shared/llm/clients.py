"""
AI TradeBot - 统一 LLM 客户端

提供所有 AI 模型的统一接口，支持：
1. Token 计数与预检
2. 自动压缩超长输入
3. 错误处理与重试
4. 1210 错误特殊处理
"""
import os
import re
import asyncio
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime

from openai import AsyncOpenAI

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# Token 计数器（粗略估算）
# =============================================================================

class TokenCounter:
    """
    Token 计数器

    使用粗略估算：1 token ≈ 0.75 个中文字符，或 0.25 个英文单词
    对于精确计数，需要使用 tiktoken，但这需要额外依赖
    """

    @staticmethod
    def count_tokens(text: str) -> int:
        """
        粗略估算 token 数量

        中文字符：1 char ≈ 1.3 tokens
        英文字符：1 word ≈ 0.25 tokens
        """
        if not text:
            return 0

        # 分离中英文
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        non_chinese_chars = len(text) - chinese_chars

        # 粗略估算
        chinese_tokens = chinese_chars * 1.3
        # 非中文字符按单词估算（假设平均单词长度为 4）
        english_words = non_chinese_chars / 4
        english_tokens = english_words * 0.25

        return int(chinese_tokens + english_tokens)

    @staticmethod
    def count_messages_tokens(messages: List[Dict[str, str]]) -> int:
        """计算消息列表的 token 数量"""
        total = 0
        for msg in messages:
            total += TokenCounter.count_tokens(msg.get("content", ""))
        return total

    @staticmethod
    def format_token_count(tokens: int) -> str:
        """格式化 token 数量显示"""
        if tokens >= 1000:
            return f"{tokens / 1000:.1f}k"
        return str(tokens)


# =============================================================================
# 通用 LLM 客户端
# =============================================================================

@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0
    success: bool = True
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMClient:
    """
    基础 LLM 客户端

    所有 AI 模型客户端的基类
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 60,
        max_input_tokens: int = 8000,  # 输入 token 上限
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_input_tokens = max_input_tokens

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        compress_if_needed: bool = True,  # 自动压缩
    ) -> LLMResponse:
        """
        调用 LLM API

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数
            max_tokens: 最大输出 token
            compress_if_needed: 是否自动压缩超长输入

        Returns:
            LLMResponse 响应
        """
        start_time = datetime.now()

        # 构建消息
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Token 预检
        estimated_tokens = TokenCounter.count_messages_tokens(messages)

        if compress_if_needed and estimated_tokens > self.max_input_tokens:
            logger.warning(
                f"[Token预检] 输入过长: {TokenCounter.format_token_count(estimated_tokens)} tokens, "
                f"自动启动极简摘要模式"
            )
            prompt = self._compress_content(prompt)
            messages[-1]["content"] = prompt
            estimated_tokens = TokenCounter.count_messages_tokens(messages)

        logger.info(
            f"[LLM] 调用 {self.model}: "
            f"输入 ~{TokenCounter.format_token_count(estimated_tokens)} tokens"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            usage = response.usage

            result = LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                duration_ms=duration_ms,
                success=True,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
            )

            logger.info(
                f"[LLM] 响应成功: "
                f"{TokenCounter.format_token_count(result.total_tokens)} tokens, "
                f"{duration_ms:.0f}ms"
            )

            return result

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = str(e)

            # 检查是否是 1210 错误（token 超限）
            if "1210" in error_msg or "token" in error_msg.lower():
                logger.error(f"[LLM] 1210 错误: Token 超限")
                result = LLMResponse(
                    content="",
                    model=self.model,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=f"1210: Token 超限 ({estimated_tokens} tokens)"
                )
            else:
                logger.error(f"[LLM] 调用失败: {e}")
                result = LLMResponse(
                    content="",
                    model=self.model,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=error_msg
                )

            return result

    def _compress_content(self, content: str, target_ratio: float = 0.3) -> str:
        """
        压缩内容

        Args:
            content: 原始内容
            target_ratio: 目标压缩比例（保留 30%）

        Returns:
            压缩后的内容
        """
        # 方法1：按段落压缩，保留关键段落
        paragraphs = content.split('\n\n')
        target_paragraphs = max(1, int(len(paragraphs) * target_ratio))

        # 保留前、中、后的关键段落
        if len(paragraphs) <= target_paragraphs:
            compressed = '\n\n'.join(paragraphs)
        else:
            # 保留前 20%、中间 60%（均匀采样）、后 20%
            front = int(target_paragraphs * 0.2)
            back = int(target_paragraphs * 0.2)
            middle = target_paragraphs - front - back

            selected = (
                paragraphs[:front] +
                paragraphs[front:len(paragraphs)-back:max(1, len(paragraphs)//middle)] +
                paragraphs[-back:] if back > 0 else []
            )
            compressed = '\n\n'.join(selected)

        # 如果还是太长，直接字符截断
        if len(compressed) > len(content) * target_ratio * 1.5:
            compressed = content[:int(len(content) * target_ratio)]

        return compressed + "\n\n[注：内容已自动压缩以适应 Token 限制]"


# =============================================================================
# 智谱 GLM 客户端
# =============================================================================

class ZhipuClient(BaseLLMClient):
    """智谱 GLM-4 客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "glm-4",
        timeout: int = 60,
    ):
        api_key = api_key or os.getenv(
            "ZHIPU_API_KEY",
            "e6a66c1745bf4def9c3418634ac17d43.rbulTfwptgJ7KHf"
        )
        base_url = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            max_input_tokens=8000,  # GLM-4 输入上限
        )


class GLM5Client(BaseLLMClient):
    """智谱 GLM-5 客户端 (最新旗舰模型)"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "glm-5",
        timeout: int = 90,  # GLM-5 可能需要更长响应时间
    ):
        api_key = api_key or os.getenv(
            "ZHIPU_API_KEY",
            "e6a66c1745bf4def9c3418634ac17d43.rbulTfwptgJ7KHf"
        )
        base_url = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            max_input_tokens=32000,  # GLM-5 支持 128k 上下文
        )


# =============================================================================
# Kimi 客户端
# =============================================================================

class KimiClient(BaseLLMClient):
    """Kimi (Moonshot AI) 客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "moonshot-v1-128k",
        timeout: int = 60,
    ):
        api_key = api_key or os.getenv("KIMI_API_KEY", "")
        base_url = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")

        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            max_input_tokens=10000,  # Kimi 支持 128k
        )


# =============================================================================
# 全局单例
# =============================================================================

_zhipu_client: Optional[ZhipuClient] = None
_glm5_client: Optional[GLM5Client] = None
_kimi_client: Optional[KimiClient] = None


def get_zhipu_client() -> ZhipuClient:
    """获取智谱 GLM-4 客户端单例"""
    global _zhipu_client
    if _zhipu_client is None:
        _zhipu_client = ZhipuClient()
    return _zhipu_client


def get_glm5_client() -> GLM5Client:
    """获取智谱 GLM-5 客户端单例 (最新旗舰模型)"""
    global _glm5_client
    if _glm5_client is None:
        _glm5_client = GLM5Client()
    return _glm5_client


def get_kimi_client() -> KimiClient:
    """获取 Kimi 客户端单例"""
    global _kimi_client
    if _kimi_client is None:
        _kimi_client = KimiClient()
    return _kimi_client


# =============================================================================
# DeepSeek 客户端
# =============================================================================

class DeepSeekClient(BaseLLMClient):
    """DeepSeek AI 客户端"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "deepseek-chat",
        timeout: int = 60,
    ):
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            max_input_tokens=32000,  # DeepSeek 支持 32k 上下文
        )


_deepseek_client: Optional[DeepSeekClient] = None


def get_deepseek_client() -> DeepSeekClient:
    """获取 DeepSeek 客户端单例"""
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = DeepSeekClient()
    return _deepseek_client
