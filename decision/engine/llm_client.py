"""
AI TradeBot - 统一 LLM 客户端

提供支持重试、超时控制和异步调用的通用 LLM 请求函数。

功能特性：
1. 异步 API 调用
2. 指数退避重试机制
3. 超时控制
4. 结构化输出解析 (JSON 清洗)
5. OpenAI 兼容格式

作者: Matrix Agent
"""

import os
import json
import asyncio
import re
from typing import Optional, Dict, Any, Type, Union, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 配置与常量
# =============================================================================

class LLMProvider(Enum):
    """LLM 提供商"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """LLM 配置"""
    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-coder"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout: int = 60
    max_retries: int = 3
    
    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量加载配置"""
        return cls(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.getenv("LLM_MODEL", "deepseek-coder"),
            temperature=0.3,
            max_tokens=4096,
            timeout=int(os.getenv("LLM_TIMEOUT", "60")),
            max_retries=3,
        )


# =============================================================================
# 自定义异常
# =============================================================================

class LLMError(Exception):
    """LLM 调用基础异常"""
    def __init__(self, message: str, code: str = "UNKNOWN"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class LLMTimeoutError(LLMError):
    """超时异常"""
    def __init__(self, message: str = "LLM 调用超时"):
        super().__init__(message, "TIMEOUT")


class LLMRateLimitError(LLMError):
    """限流异常"""
    def __init__(self, message: str = "LLM API 限流"):
        super().__init__(message, "RATE_LIMIT")


class LLMJSONParseError(LLMError):
    """JSON 解析异常"""
    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message, "JSON_PARSE")
        self.raw_response = raw_response


# =============================================================================
# 核心类: LLMClient
# =============================================================================

class LLMClient:
    """
    统一 LLM 客户端
    
    提供异步的 LLM 调用接口，支持重试、超时和结构化输出。
    
    Usage:
        client = LLMClient()
        response = await client.chat("你好，请介绍一下自己")
        
        # 结构化输出
        from schemas import StrategyHypothesis
        result = await client.chat_with_schema(
            system_prompt="你是JSON生成器",
            user_prompt="生成一个策略假设",
            schema=StrategyHypothesis
        )
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化 LLM 客户端
        
        Args:
            config: LLM 配置 (默认从环境变量加载)
        """
        self.config = config or LLMConfig.from_env()
        self._client = None
        self._provider = self._detect_provider()
        
        logger.info(f"[LLMClient] 初始化完成: provider={self._provider}, model={self.config.model}")
    
    def _detect_provider(self) -> LLMProvider:
        """检测 LLM 提供商"""
        url = self.config.base_url.lower()
        
        if "deepseek" in url:
            return LLMProvider.DEEPSEEK
        elif "openai" in url:
            return LLMProvider.OPENAI
        elif "anthropic" in url:
            return LLMProvider.ANTHROPIC
        else:
            return LLMProvider.CUSTOM
    
    def _get_async_client(self):
        """获取异步客户端"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url,
                    timeout=self.config.timeout,
                    max_retries=0,  # 我们自己实现重试
                )
            except ImportError:
                raise ImportError("请安装 openai 库: pip install openai")
        
        return self._client
    
    async def chat(
        self,
        user_prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        发送聊天请求
        
        Args:
            user_prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数
            max_tokens: 最大 token 数
            
        Returns:
            LLM 响应文本
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": user_prompt})
        
        return await self._request(
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )
    
    async def chat_with_schema(
        self,
        user_prompt: str,
        system_prompt: str = "",
        schema: Optional[Type[BaseModel]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Union[str, BaseModel]:
        """
        发送聊天请求并解析 JSON 响应
        
        Args:
            user_prompt: 用户提示
            system_prompt: 系统提示
            schema: Pydantic 模型类 (可选)
            temperature: 温度参数
            max_tokens: 最大 token 数
            
        Returns:
            如果提供 schema: 解析后的 Pydantic 模型
            否则: LLM 响应文本
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加 JSON 格式要求
        if schema:
            schema_hint = f"\n\n请以 JSON 格式输出，包含以下字段: {', '.join(schema.model_fields.keys())}"
            user_prompt = user_prompt + schema_hint
        
        messages.append({"role": "user", "content": user_prompt})
        
        response = await self._request(
            messages=messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
        )
        
        # 如果提供了 schema，解析 JSON
        if schema:
            return self._parse_json_response(response, schema)
        
        return response
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((LLMRateLimitError, LLMTimeoutError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def _request(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        发送 API 请求 (带重试)
        
        Args:
            messages: 消息列表
            temperature: 温度
            max_tokens: 最大 token
            
        Returns:
            LLM 响应文本
        """
        client = self._get_async_client()
        
        try:
            logger.info(f"[LLMClient] 发送请求, messages={len(messages)}")
            
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=self.config.timeout,
            )
            
            content = response.choices[0].message.content
            
            if not content:
                raise LLMError("LLM 返回空响应", "EMPTY_RESPONSE")
            
            logger.info(f"[LLMClient] 收到响应, length={len(content)}")
            
            return content
            
        except asyncio.TimeoutError:
            logger.error("[LLMClient] 请求超时")
            raise LLMTimeoutError()
        
        except Exception as e:
            error_msg = str(e)
            
            if "429" in error_msg or "rate_limit" in error_msg.lower():
                logger.warning(f"[LLMClient] 触发限流: {error_msg}")
                raise LLMRateLimitError(error_msg)
            
            logger.error(f"[LLMClient] 请求失败: {error_msg}")
            raise LLMError(error_msg, "REQUEST_FAILED")
    
    def _parse_json_response(
        self,
        response: str,
        schema: Type[BaseModel],
    ) -> BaseModel:
        """
        解析 JSON 响应
        
        Args:
            response: LLM 原始响应
            schema: Pydantic 模型类
            
        Returns:
            解析后的模型实例
        """
        # 步骤1: 提取 JSON
        json_str = self._extract_json_from_text(response)
        
        if not json_str:
            raise LLMJSONParseError(
                "无法从响应中提取 JSON",
                raw_response=response[:500]
            )
        
        # 步骤2: 解析 JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise LLMJSONParseError(
                f"JSON 解析失败: {e}",
                raw_response=json_str[:500]
            )
        
        # 步骤3: 验证 Pydantic 模型
        try:
            return schema.model_validate(data)
        except Exception as e:
            raise LLMJSONParseError(
                f"Pydantic 验证失败: {e}",
                raw_response=json_str[:500]
            )
    
    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """
        从文本中提取 JSON
        
        处理以下情况:
        - Markdown 代码块: ```json ... ```
        - 纯 JSON 文本
        - 带有前缀/后缀的 JSON
        
        Args:
            text: 原始文本
            
        Returns:
            提取的 JSON 字符串
        """
        if not text:
            return None
        
        # 移除多余空白
        text = text.strip()
        
        # 情况1: Markdown 代码块
        if "```json" in text:
            pattern = r"```json\s*\n(.*?)\n```"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        if "```" in text:
            pattern = r"```\s*\n?(.*?)\n?```"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                content = match.group(1).strip()
                # 检查是否是 JSON
                if content.startswith("{") or content.startswith("["):
                    return content
        
        # 情况2: 纯 JSON
        if text.startswith("{") or text.startswith("["):
            # 尝试找到完整的 JSON 对象
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                return json_match.group(0)
            
            json_match = re.search(r"\[[\s\S]*\]", text)
            if json_match:
                return json_match.group(0)
        
        # 情况3: 尝试直接解析
        try:
            json.loads(text)
            return text
        except:
            pass
        
        return None
    
    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.close()
            self._client = None


# =============================================================================
# 便捷函数
# =============================================================================

# 全局客户端实例
_global_client: Optional[LLMClient] = None


def get_llm_client(config: Optional[LLMConfig] = None) -> LLMClient:
    """
    获取全局 LLM 客户端实例
    
    Args:
        config: LLM 配置 (可选)
        
    Returns:
        LLMClient 实例
    """
    global _global_client
    
    if _global_client is None:
        _global_client = LLMClient(config)
    
    return _global_client


def get_llm_client_for_agent(agent_name: str) -> LLMClient:
    """根据Agent名称获取对应的LLM客户端"""
    agent_config_map = {
        "Hunter": {"api_key": os.getenv("ZHIPU_API_KEY", ""), "base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4"},
        "Strategist": {"api_key": os.getenv("DEEPSEEK_API_KEY_1", ""), "base_url": "https://api.deepseek.com/v1", "model": "deepseek-coder"},
        "RiskOfficer": {"api_key": os.getenv("DEEPSEEK_API_KEY_2", ""), "base_url": "https://api.deepseek.com/v1", "model": "deepseek-coder"},
        "Judge": {"api_key": os.getenv("MINIMAX_API_KEY", ""), "base_url": "https://api.minimax.chat/v1", "model": "abab6.5s-chat"},
        "Analyst": {"api_key": os.getenv("GUIJI_API_KEY", ""), "base_url": "https://api.siliconflow.cn/v1", "model": "deepseek-ai/DeepSeek-V2-Chat"},
    }
    config_dict = agent_config_map.get(agent_name, {})
    if not config_dict.get("api_key"):
        logger.warning(f"[LLMClient] Agent {agent_name} 未配置专用API Key，使用默认配置")
        return get_llm_client()
    config = LLMConfig(api_key=config_dict["api_key"], base_url=config_dict.get("base_url", "https://api.deepseek.com/v1"), model=config_dict.get("model", "deepseek-coder"), temperature=0.3, max_tokens=4096, timeout=60)
    logger.info(f"[LLMClient] 为 Agent {agent_name} 创建专用客户端: {config.model}")
    return LLMClient(config)


async def chat(
    user_prompt: str,
    system_prompt: str = "",
) -> str:
    """
    快速发送聊天请求
    
    Usage:
        response = await chat("你好", "你是一个助手")
    """
    client = get_llm_client()
    return await client.chat(user_prompt, system_prompt)


async def chat_with_schema(
    user_prompt: str,
    system_prompt: str = "",
    schema: Optional[Type[BaseModel]] = None,
) -> Union[str, BaseModel]:
    """
    快速发送聊天请求并解析 JSON
    
    Usage:
        from schemas import StrategyHypothesis
        result = await chat_with_schema("生成策略", schema=StrategyHypothesis)
    """
    client = get_llm_client()
    return await client.chat_with_schema(user_prompt, system_prompt, schema)


# =============================================================================
# 测试入口
# =============================================================================

if __name__ == "__main__":
    async def test():
        print("=" * 60)
        print("测试 LLM 客户端")
        print("=" * 60)
        
        # 检查配置
        config = LLMConfig.from_env()
        print(f"\n配置:")
        print(f"  API URL: {config.base_url}")
        print(f"  Model: {config.model}")
        
        if not config.api_key:
            print("\n⚠️ 警告: LLM_API_KEY 未设置")
            print("请设置环境变量 LLM_API_KEY")
            return
        
        # 创建客户端
        client = LLMClient(config)
        
        # 测试1: 简单聊天
        print("\n[测试1] 简单聊天")
        try:
            response = await client.chat(
                user_prompt="用一句话介绍量化交易",
                system_prompt="你是一个专业的量化交易助手"
            )
            print(f"  响应: {response[:100]}...")
        except Exception as e:
            print(f"  错误: {e}")
        
        # 测试2: JSON 解析
        print("\n[测试2] JSON 解析")
        try:
            # 模拟带 JSON 的响应
            test_json = '''```json
{
    "market_insight": "市场放量上涨",
    "trading_direction": "BUY",
    "confidence": 0.8
}
```'''
            
            from schemas import StrategyHypothesis, TradingDirection
            result = client._parse_json_response(test_json, StrategyHypothesis)
            print(f"  解析成功: {result.market_insight}, {result.trading_direction}")
        except Exception as e:
            print(f"  错误: {e}")
        
        # 测试3: 提取 JSON
        print("\n[测试3] JSON 提取")
        test_text = '''
        以下是JSON输出:
        ```json
        {"name": "test", "value": 123}
        ```
        '''
        json_str = client._extract_json_from_text(test_text)
        print(f"  提取结果: {json_str}")
        
        await client.close()
        
        print("\n" + "=" * 60)
        print("✅ 测试完成")
        print("=" * 60)
    
    asyncio.run(test())
