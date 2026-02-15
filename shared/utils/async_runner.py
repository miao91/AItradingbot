"""
AI TradeBot - 异步运行工具

统一异步处理：
1. 标准化 asyncio.run() 模式
2. 优雅退出机制（信号处理）
3. 异步上下文管理器支持
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Awaitable, Callable, List, Optional

from shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ShutdownState:
    """关闭状态"""

    is_shutting_down: bool = False
    shutdown_reason: str = ""
    cleanup_tasks: List[Callable[[], Awaitable[None]]] = field(default_factory=list)


_shutdown_state = ShutdownState()


def is_shutting_down() -> bool:
    """检查是否正在关闭"""
    return _shutdown_state.is_shutting_down


def register_cleanup(cleanup_func: Callable[[], Awaitable[None]]) -> None:
    """注册清理函数"""
    _shutdown_state.cleanup_tasks.append(cleanup_func)


async def _run_cleanup() -> None:
    """运行所有清理函数"""
    logger.info("[异步工具] 开始清理...")

    for cleanup_func in _shutdown_state.cleanup_tasks:
        try:
            await cleanup_func()
        except Exception as e:
            logger.error(f"[异步工具] 清理函数失败: {e}")

    logger.info("[异步工具] 清理完成")


def _signal_handler(signum, frame) -> None:
    """信号处理器"""
    signal_name = signal.Signals(signum).name
    logger.warning(f"[异步工具] 收到信号 {signal_name}，准备退出...")

    _shutdown_state.is_shutting_down = True
    _shutdown_state.shutdown_reason = signal_name


def setup_signal_handlers() -> None:
    """设置信号处理器（Windows/Linux 兼容）"""
    # Windows 只支持 SIGINT
    signal.signal(signal.SIGINT, _signal_handler)

    # Unix 还支持 SIGTERM
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal_handler)

    logger.info("[异步工具] 信号处理器已设置")


def run_async(
    main_func: Callable[[], Awaitable[None]],
    *,
    setup_signals: bool = True,
    debug: bool = False,
) -> None:
    """
    统一异步入口

    用法：
    ```python
    async def main():
        # 你的异步代码
        pass

    if __name__ == "__main__":
        run_async(main)
    ```

    Args:
        main_func: 主异步函数
        setup_signals: 是否设置信号处理器
        debug: 是否启用调试模式
    """
    if setup_signals:
        setup_signal_handlers()

    async def wrapped_main():
        try:
            await main_func()
        except asyncio.CancelledError:
            logger.info("[异步工具] 任务被取消")
        finally:
            await _run_cleanup()

    try:
        asyncio.run(wrapped_main(), debug=debug)
    except KeyboardInterrupt:
        logger.info("[异步工具] 用户中断")


@asynccontextmanager
async def graceful_shutdown_context():
    """
    优雅退出上下文管理器

    用法：
    ```python
    async with graceful_shutdown_context():
        # 你的代码
        while not is_shutting_down():
            await do_work()
    """
    try:
        yield
    except asyncio.CancelledError:
        logger.info("[上下文] 收到取消请求")
    finally:
        await _run_cleanup()


async def wait_with_shutdown(timeout: float = 1.0) -> bool:
    """
    可中断的等待

    Args:
        timeout: 等待时间（秒）

    Returns:
        True = 正常完成, False = 被中断
    """
    try:
        await asyncio.wait_for(asyncio.sleep(timeout), timeout=timeout + 0.1)
        return not is_shutting_down()
    except asyncio.CancelledError:
        return False


async def run_with_timeout(
    coro: Awaitable,
    timeout: float,
    default=None,
):
    """
    带超时执行协程

    Args:
        coro: 协程
        timeout: 超时时间（秒）
        default: 超时时返回的默认值

    Returns:
        协程结果或默认值
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"[异步工具] 超时 ({timeout}s)")
        return default


async def gather_with_concurrency(
    *tasks: Awaitable,
    concurrency: int = 10,
) -> List:
    """
    限制并发数的 gather

    Args:
        tasks: 任务列表
        concurrency: 最大并发数

    Returns:
        结果列表
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def limited_task(task):
        async with semaphore:
            return await task

    return await asyncio.gather(*[limited_task(t) for t in tasks])


# =============================================================================
# 便捷函数
# =============================================================================


def create_task(coro: Awaitable, name: Optional[str] = None) -> asyncio.Task:
    """创建带名称的任务"""
    task = asyncio.create_task(coro)
    if name:
        try:
            task.set_name(name)
        except AttributeError:
            pass  # Python < 3.8
    return task


async def sleep_until_shutdown(check_interval: float = 1.0) -> None:
    """睡眠直到收到关闭信号"""
    while not is_shutting_down():
        await asyncio.sleep(check_interval)


__all__ = [
    "run_async",
    "setup_signal_handlers",
    "is_shutting_down",
    "register_cleanup",
    "graceful_shutdown_context",
    "wait_with_shutdown",
    "run_with_timeout",
    "gather_with_concurrency",
    "create_task",
    "sleep_until_shutdown",
]
