"""
AI TradeBot - 模型降级管理器

多级容错策略：
1. 主模型失败 → 备用模型
2. 备用模型失败 → 本地规则
3. 全部失败 → 安全默认值

模型优先级：
- GLM-5 (主力) → GLM-4 (备用) → DeepSeek (经济) → 规则引擎
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from shared.logging import get_logger

logger = get_logger(__name__)


class ModelTier(Enum):
    """模型层级"""

    PRIMARY = "primary"  # 主力模型
    BACKUP = "backup"  # 备用模型
    ECONOMY = "economy"  # 经济模型
    LOCAL = "local"  # 本地规则


@dataclass
class ModelConfig:
    """模型配置"""

    name: str
    tier: ModelTier
    max_retries: int = 2
    timeout_seconds: float = 30.0
    enabled: bool = True
    failure_count: int = 0
    last_failure: Optional[datetime] = None


@dataclass
class FallbackResult:
    """降级结果"""

    success: bool
    content: str
    model_used: str
    tier: ModelTier
    fallback_chain: List[str] = field(default_factory=list)
    error: Optional[str] = None


class ModelFallbackManager:
    """
    模型降级管理器

    功能：
    1. 自动模型降级
    2. 故障熔断（连续失败自动禁用）
    3. 健康检查
    4. 请求重试
    """

    # 默认模型链
    DEFAULT_MODEL_CHAIN = [
        ModelConfig("glm-5", ModelTier.PRIMARY, max_retries=2, timeout_seconds=30),
        ModelConfig("glm-4", ModelTier.BACKUP, max_retries=2, timeout_seconds=25),
        ModelConfig("deepseek", ModelTier.ECONOMY, max_retries=1, timeout_seconds=20),
        ModelConfig("rule-engine", ModelTier.LOCAL, max_retries=0, timeout_seconds=5),
    ]

    def __init__(self, model_chain: Optional[List[ModelConfig]] = None):
        self.model_chain = model_chain or self.DEFAULT_MODEL_CHAIN.copy()
        self._circuit_threshold = 3  # 连续失败3次触发熔断
        self._recovery_seconds = 300  # 5分钟后尝试恢复

        # 统计
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "fallback_requests": 0,
            "local_fallbacks": 0,
        }

        logger.info(f"[降级管理器] 初始化完成，模型链: {[m.name for m in self.model_chain]}")

    async def call_with_fallback(
        self,
        prompt: str,
        *,
        max_tokens: int = 500,
        temperature: float = 0.7,
        preferred_model: Optional[str] = None,
    ) -> FallbackResult:
        """
        带降级保护的模型调用

        Args:
            prompt: 输入提示
            max_tokens: 最大 token 数
            temperature: 温度参数
            preferred_model: 指定首选模型

        Returns:
            FallbackResult 降级结果
        """
        self._stats["total_requests"] += 1
        fallback_chain = []

        for model_config in self._get_available_models(preferred_model):
            if not model_config.enabled:
                continue

            # 检查熔断状态
            if self._is_circuit_open(model_config):
                logger.warning(f"[降级] 模型 {model_config.name} 熔断中，跳过")
                continue

            fallback_chain.append(model_config.name)

            try:
                result = await self._call_model(
                    model_config,
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                if result.success:
                    self._stats["successful_requests"] += 1
                    if len(fallback_chain) > 1:
                        self._stats["fallback_requests"] += 1

                    # 重置失败计数
                    model_config.failure_count = 0

                    return FallbackResult(
                        success=True,
                        content=result.content,
                        model_used=model_config.name,
                        tier=model_config.tier,
                        fallback_chain=fallback_chain,
                    )

            except Exception as e:
                logger.warning(f"[降级] 模型 {model_config.name} 调用失败: {e}")
                self._record_failure(model_config)

        # 所有模型都失败，使用本地规则
        self._stats["local_fallbacks"] += 1
        return self._get_local_fallback(prompt, fallback_chain)

    def _get_available_models(self, preferred: Optional[str] = None) -> List[ModelConfig]:
        """获取可用模型列表（按优先级排序）"""
        models = [m for m in self.model_chain if m.enabled]

        if preferred:
            # 将首选模型移到最前面
            preferred_idx = next((i for i, m in enumerate(models) if m.name == preferred), None)
            if preferred_idx is not None and preferred_idx > 0:
                models.insert(0, models.pop(preferred_idx))

        return models

    def _is_circuit_open(self, config: ModelConfig) -> bool:
        """检查熔断器是否打开"""
        if config.failure_count < self._circuit_threshold:
            return False

        # 检查恢复时间
        if config.last_failure:
            elapsed = (datetime.now() - config.last_failure).total_seconds()
            if elapsed > self._recovery_seconds:
                logger.info(f"[降级] 模型 {config.name} 熔断恢复尝试")
                config.failure_count = 0
                return False

        return True

    def _record_failure(self, config: ModelConfig) -> None:
        """记录失败"""
        config.failure_count += 1
        config.last_failure = datetime.now()

        if config.failure_count >= self._circuit_threshold:
            logger.error(
                f"[降级] 模型 {config.name} 触发熔断 " f"(连续失败 {config.failure_count} 次)"
            )

    async def _call_model(
        self,
        config: ModelConfig,
        prompt: str,
        **kwargs,
    ) -> Any:
        """调用具体模型"""
        if config.tier == ModelTier.LOCAL:
            # 本地规则引擎
            return await self._call_local_engine(prompt)

        # 获取对应的客户端
        client = await self._get_model_client(config.name)
        if client is None:
            raise RuntimeError(f"无法获取 {config.name} 客户端")

        # 带超时和重试的调用
        for attempt in range(config.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    client.call(prompt=prompt, **kwargs),
                    timeout=config.timeout_seconds,
                )
                return result
            except asyncio.TimeoutError:
                logger.warning(f"[降级] {config.name} 超时 (尝试 {attempt + 1})")
                if attempt == config.max_retries:
                    raise

    async def _get_model_client(self, model_name: str) -> Optional[Any]:
        """获取模型客户端"""
        try:
            if model_name.startswith("glm"):
                from decision.ai_matrix.glm5.client import GLM5Client

                return GLM5Client()
            elif model_name == "deepseek":
                from decision.ai_matrix.deepseek.client import DeepSeekClient

                return DeepSeekClient()
            else:
                logger.warning(f"[降级] 未知模型: {model_name}")
                return None
        except Exception as e:
            logger.error(f"[降级] 获取客户端失败 {model_name}: {e}")
            return None

    async def _call_local_engine(self, prompt: str) -> Any:
        """本地规则引擎"""
        from dataclasses import dataclass

        @dataclass
        class LocalResult:
            success: bool = True
            content: str = ""

        # 简单的规则匹配
        prompt_lower = prompt.lower()

        if "分析" in prompt or "analyze" in prompt_lower:
            content = "【本地分析】由于AI服务暂时不可用，使用规则引擎进行基础分析。建议保守观望。"
        elif "评分" in prompt or "score" in prompt_lower:
            content = "【本地评分】评分: 5.0/10.0 (中性，AI服务降级)"
        else:
            content = "【本地响应】AI服务暂时降级，建议稍后重试。"

        return LocalResult(success=True, content=content)

    def _get_local_fallback(self, prompt: str, fallback_chain: List[str]) -> FallbackResult:
        """获取本地降级响应"""
        return FallbackResult(
            success=False,
            content="【安全模式】所有AI模型暂时不可用，建议人工介入或稍后重试。",
            model_used="safety-default",
            tier=ModelTier.LOCAL,
            fallback_chain=fallback_chain,
            error="所有模型调用失败",
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "success_rate": (
                self._stats["successful_requests"] / self._stats["total_requests"] * 100
                if self._stats["total_requests"] > 0
                else 0
            ),
            "model_status": [
                {
                    "name": m.name,
                    "tier": m.tier.value,
                    "enabled": m.enabled,
                    "failure_count": m.failure_count,
                }
                for m in self.model_chain
            ],
        }

    def reset_circuit(self, model_name: str) -> None:
        """重置指定模型的熔断器"""
        for model in self.model_chain:
            if model.name == model_name:
                model.failure_count = 0
                model.enabled = True
                logger.info(f"[降级] 已重置模型 {model_name} 熔断器")
                break


# =============================================================================
# 全局单例
# =============================================================================

_fallback_manager: Optional[ModelFallbackManager] = None


def get_fallback_manager() -> ModelFallbackManager:
    """获取全局降级管理器"""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = ModelFallbackManager()
    return _fallback_manager


async def call_with_fallback(prompt: str, **kwargs) -> FallbackResult:
    """便捷函数：带降级保护的模型调用"""
    return await get_fallback_manager().call_with_fallback(prompt, **kwargs)
