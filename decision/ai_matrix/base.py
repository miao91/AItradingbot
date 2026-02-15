"""
AI TradeBot - AI Matrix 基础类

定义所有 AI 客户端的统一接口
"""
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field

from pydantic import BaseModel
from openai import AsyncOpenAI

from shared.logging import get_logger, track_ai_call


logger = get_logger(__name__)


@dataclass
class AIMessage:
    """AI 消息数据类"""
    role: str  # system, user, assistant
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class AIResponse:
    """AI 响应数据类"""
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0
    raw_response: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: Optional[str] = None


class AIClientBase(ABC):
    """
    AI 客户端基类

    所有 AI 模型客户端必须继承此类并实现抽象方法
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ):
        """
        初始化 AI 客户端

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key or os.getenv(self.get_api_key_env())
        self.base_url = base_url or os.getenv(self.get_base_url_env())
        self.model = model or os.getenv(self.get_model_env(), self.get_default_model())
        self.timeout = timeout

        # 验证配置
        if not self.api_key:
            logger.warning(f"{self.__class__.__name__}: API Key 未设置")

        # OpenAI 兼容客户端（大多数 LLM API 都兼容）
        self.client = None
        if self.api_key and self.base_url:
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=timeout,
            )

    @abstractmethod
    def get_api_key_env(self) -> str:
        """获取 API Key 环境变量名"""
        pass

    @abstractmethod
    def get_base_url_env(self) -> str:
        """获取 Base URL 环境变量名"""
        pass

    @abstractmethod
    def get_model_env(self) -> str:
        """获取 Model 环境变量名"""
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """获取默认模型名称"""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        pass

    async def chat(
        self,
        messages: List[AIMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs
    ) -> AIResponse:
        """
        发送聊天请求

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数

        Returns:
            AIResponse 响应对象
        """
        if not self.client:
            return AIResponse(
                content="",
                model=self.model,
                success=False,
                error_message="AI 客户端未初始化（API Key 或 Base URL 缺失）"
            )

        start_time = datetime.now()

        try:
            # 转换消息格式
            api_messages = [
                {"role": "system", "content": self.get_system_prompt()},
                *[msg.to_dict() for msg in messages]
            ]

            # 调用 API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

            # 计算耗时
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            # 提取结果
            content = response.choices[0].message.content
            usage = response.usage

            result = AIResponse(
                content=content,
                model=response.model,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                duration_ms=duration_ms,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
                success=True,
            )

            logger.info(
                f"{self.__class__.__name__} 调用成功: "
                f"{usage.total_tokens if usage else 0} tokens, "
                f"{duration_ms:.0f}ms"
            )

            return result

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"{self.__class__.__name__} 调用失败: {e}")

            return AIResponse(
                content="",
                model=self.model,
                duration_ms=duration_ms,
                success=False,
                error_message=str(e),
            )

    async def chat_with_tracking(
        self,
        messages: List[AIMessage],
        action_name: str,
        **kwargs
    ) -> AIResponse:
        """
        带追踪的聊天请求（自动记录到日志）

        Args:
            messages: 消息列表
            action_name: 操作名称（用于日志）
            **kwargs: 其他参数

        Returns:
            AIResponse 响应对象
        """
        tracker = track_ai_call(self.__class__.__name__, action_name)

        with tracker:
            response = await self.chat(messages, **kwargs)

            if not response.success:
                tracker.success = False
                tracker.error_message = response.error_message

            return response

    def create_user_message(self, content: str) -> AIMessage:
        """创建用户消息"""
        return AIMessage(role="user", content=content)

    def create_system_message(self, content: str) -> AIMessage:
        """创建系统消息"""
        return AIMessage(role="system", content=content)

    def create_assistant_message(self, content: str) -> AIMessage:
        """创建助手消息"""
        return AIMessage(role="assistant", content=content)
