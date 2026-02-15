"""
AI TradeBot - 依赖注入框架

替代全局单例模式，支持：
1. 可测试性
2. 多实例并发
3. 优雅的资源管理
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

from shared.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class ServiceDescriptor(Generic[T]):
    """服务描述符"""

    factory: Callable[[], T]
    instance: Optional[T] = None
    singleton: bool = True
    initialized: bool = False


class DependencyInjector:
    """
    依赖注入容器

    使用方式：
    ```python
    container = DependencyInjector()

    # 注册服务
    container.register(GLM5Client, lambda: GLM5Client())
    container.register(ExitPlanner, lambda: ExitPlanner())

    # 获取服务
    glm5 = container.get(GLM5Client)
    planner = container.get(ExitPlanner)
    ```
    """

    def __init__(self):
        self._services: Dict[type, ServiceDescriptor] = {}
        self._async_lock = asyncio.Lock()
        logger.info("[DI] 依赖注入容器初始化完成")

    def register(
        self,
        service_type: type,
        factory: Callable[[], T],
        singleton: bool = True,
    ) -> None:
        """
        注册服务

        Args:
            service_type: 服务类型
            factory: 工厂函数
            singleton: 是否单例
        """
        self._services[service_type] = ServiceDescriptor(
            factory=factory,
            singleton=singleton,
        )
        logger.debug(f"[DI] 注册服务: {service_type.__name__}, 单例={singleton}")

    def get(self, service_type: type[T]) -> T:
        """
        获取服务实例

        Args:
            service_type: 服务类型

        Returns:
            服务实例
        """
        if service_type not in self._services:
            raise KeyError(f"服务未注册: {service_type.__name__}")

        descriptor = self._services[service_type]

        # 非单例模式，每次创建新实例
        if not descriptor.singleton:
            return descriptor.factory()

        # 单例模式，返回已创建的实例或创建新实例
        if not descriptor.initialized:
            descriptor.instance = descriptor.factory()
            descriptor.initialized = True
            logger.debug(f"[DI] 创建单例: {service_type.__name__}")

        return descriptor.instance

    def try_get(self, service_type: type[T]) -> Optional[T]:
        """尝试获取服务，不存在返回 None"""
        try:
            return self.get(service_type)
        except KeyError:
            return None

    def has(self, service_type: type) -> bool:
        """检查服务是否已注册"""
        return service_type in self._services

    def clear(self) -> None:
        """清除所有服务"""
        self._services.clear()
        logger.info("[DI] 清除所有服务")

    @asynccontextmanager
    async def lifespan(self):
        """
        生命周期管理器

        用法：
        ```python
        async with container.lifespan():
            # 应用运行期间
            app.run()
        ```
        """
        logger.info("[DI] 容器启动")
        try:
            yield self
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """关闭容器，清理资源"""
        logger.info("[DI] 容器关闭，清理资源...")

        for service_type, descriptor in self._services.items():
            if descriptor.instance and hasattr(descriptor.instance, "close"):
                try:
                    if asyncio.iscoroutinefunction(descriptor.instance.close):
                        await descriptor.instance.close()
                    else:
                        descriptor.instance.close()
                    logger.debug(f"[DI] 关闭服务: {service_type.__name__}")
                except Exception as e:
                    logger.error(f"[DI] 关闭服务失败 {service_type.__name__}: {e}")

        self._services.clear()


# =============================================================================
# 全局容器（保持向后兼容）
# =============================================================================

_global_container: Optional[DependencyInjector] = None


def get_container() -> DependencyInjector:
    """获取全局容器"""
    global _global_container
    if _global_container is None:
        _global_container = DependencyInjector()
        _register_default_services(_global_container)
    return _global_container


def _register_default_services(container: DependencyInjector) -> None:
    """注册默认服务"""
    # 延迟导入避免循环依赖
    try:
        from decision.ai_matrix.glm5.client import GLM5Client

        container.register(GLM5Client, lambda: GLM5Client())
    except ImportError:
        logger.warning("[DI] GLM5Client 不可用")

    try:
        from decision.engine.exit_planner import ExitPlanner

        container.register(ExitPlanner, lambda: ExitPlanner())
    except ImportError:
        logger.warning("[DI] ExitPlanner 不可用")

    try:
        from decision.engine.monte_carlo_engine import MonteCarloEngine

        container.register(MonteCarloEngine, lambda: MonteCarloEngine())
    except ImportError:
        logger.warning("[DI] MonteCarloEngine 不可用")

    try:
        from decision.engine.reasoning_engine import ReasoningEngine

        container.register(ReasoningEngine, lambda: ReasoningEngine())
    except ImportError:
        logger.warning("[DI] ReasoningEngine 不可用")

    logger.info("[DI] 默认服务注册完成")


def reset_container() -> None:
    """重置全局容器（用于测试）"""
    global _global_container
    if _global_container:
        _global_container.clear()
    _global_container = None
