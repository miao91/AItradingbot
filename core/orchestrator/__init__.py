"""
AI TradeBot - GLM-5 核心编排器

一主多专架构：
- GLM-5 作为总指挥，负责核心决策和任务编排
- Kimi 作为长文专家，处理超长PDF
- MiniMax 作为语境专家，辅助分析
- 模型降级：多级容错保护
"""

from core.orchestrator.dependency_injector import DependencyInjector, get_container
from core.orchestrator.glm5_orchestrator import GLM5Orchestrator, get_orchestrator
from core.orchestrator.model_fallback import (
    FallbackResult,
    ModelFallbackManager,
    ModelTier,
    call_with_fallback,
    get_fallback_manager,
)

__all__ = [
    "GLM5Orchestrator",
    "get_orchestrator",
    "DependencyInjector",
    "get_container",
    "ModelFallbackManager",
    "ModelTier",
    "FallbackResult",
    "get_fallback_manager",
    "call_with_fallback",
]
