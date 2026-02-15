"""
AI TradeBot - 统一日志系统
支持控制台输出、文件滚动存储、AI 调用追踪
"""
import sys
import logging
import time
import json
from pathlib import Path
from functools import wraps
from contextlib import contextmanager
from typing import Any, Optional, Dict, Callable, TypeVar
from loguru import logger as loguru_logger
from datetime import datetime


# 类型变量
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class InterceptHandler(logging.Handler):
    """
    将标准 logging 重定向到 loguru
    """
    def emit(self, record: logging.LogRecord) -> None:
        # 获取对应的 loguru level
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 查找调用者
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/aitradebot.log",
    rotation: str = "10 MB",
    retention: str = "30 days",
    format_string: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    ai_log_file: str = "logs/ai_calls.log",
) -> None:
    """
    配置日志系统

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 主日志文件路径
        rotation: 日志轮转条件 (如: "10 MB", "00:00", "1 week")
        retention: 日志保留时间 (如: "30 days", "1 year")
        format_string: 日志格式字符串
        ai_log_file: AI 调用专用日志文件路径
    """
    # 确保 logs 目录存在
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    ai_log_path = Path(ai_log_file)
    ai_log_path.parent.mkdir(parents=True, exist_ok=True)

    # 移除默认的 loguru handler
    loguru_logger.remove()

    # 1. 添加控制台输出（带颜色）
    loguru_logger.add(
        sys.stdout,
        format=format_string,
        level=log_level,
        colorize=True,
        filter=lambda record: not record["extra"].get("ai_call", False),
    )

    # 2. 添加主日志文件输出
    loguru_logger.add(
        log_file,
        format=format_string,
        level=log_level,
        rotation=rotation,
        retention=retention,
        compression="zip",
        encoding="utf-8",
        filter=lambda record: not record["extra"].get("ai_call", False),
    )

    # 3. 添加 AI 调用专用日志（JSON 格式，方便解析）
    ai_log_format = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {extra[ai_model]} | {extra[ai_action]} | {extra[duration_ms]}ms | {extra[success]} | {message}"
    loguru_logger.add(
        ai_log_file,
        format=ai_log_format,
        level="DEBUG",
        rotation=rotation,
        retention=retention,
        compression="zip",
        encoding="utf-8",
        filter=lambda record: record["extra"].get("ai_call", False),
    )

    # 拦截标准 logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def get_logger(name: str):
    """
    获取 logger 实例

    Args:
        name: logger 名称，通常使用 __name__

    Returns:
        logger 实例
    """
    return loguru_logger.bind(name=name)


class AICallTracker:
    """
    AI 调用追踪器

    用法 1 - 装饰器:
        @track_ai_call("kimi", "长文处理")
        async def process_with_kimi(text: str):
            ...

    用法 2 - 上下文管理器:
        with track_ai_call("glm4", "逻辑推演"):
            result = await glm4_client.generate(...)
    """

    def __init__(
        self,
        ai_model: str,
        action: str,
        logger_instance: Optional[loguru_logger] = None,
    ):
        """
        初始化追踪器

        Args:
            ai_model: AI 模型名称 (kimi, glm4, minimax, tavily)
            action: 操作描述 (如: 长文处理, 逻辑推演)
            logger_instance: 自定义 logger 实例
        """
        self.ai_model = ai_model
        self.action = action
        self.logger = logger_instance or loguru_logger
        self.start_time: Optional[float] = None
        self.success: bool = True
        self.error_message: Optional[str] = None
        self.metadata: Dict[str, Any] = {}

    def __enter__(self):
        """上下文管理器入口"""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        duration_ms = (time.perf_counter() - self.start_time) * 1000 if self.start_time else 0
        self.success = exc_type is None
        self.error_message = str(exc_val) if exc_val else None

        # 记录日志
        self._log_result(duration_ms)
        return False  # 不抑制异常

    def __call__(self, func: F) -> F:
        """装饰器模式"""

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            self.start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                self.success = True
                return result
            except Exception as e:
                self.success = False
                self.error_message = str(e)
                self.metadata["exception_type"] = type(e).__name__
                raise
            finally:
                duration_ms = (time.perf_counter() - self.start_time) * 1000
                self._log_result(duration_ms)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            self.start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                self.success = True
                return result
            except Exception as e:
                self.success = False
                self.error_message = str(e)
                self.metadata["exception_type"] = type(e).__name__
                raise
            finally:
                duration_ms = (time.perf_counter() - self.start_time) * 1000
                self._log_result(duration_ms)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    def _log_result(self, duration_ms: float) -> None:
        """
        记录 AI 调用结果到日志

        Args:
            duration_ms: 耗时（毫秒）
        """
        status_icon = "✅" if self.success else "❌"
        status_text = "SUCCESS" if self.success else "FAILED"

        # 构建消息
        message_parts = [
            f"{status_icon} [{self.ai_model}] {self.action}",
            f"Duration: {duration_ms:.2f}ms",
        ]

        if self.error_message:
            message_parts.append(f"Error: {self.error_message}")

        if self.metadata:
            message_parts.append(f"Metadata: {json.dumps(self.metadata, ensure_ascii=False)}")

        message = " | ".join(message_parts)

        # 绑定额外的上下文信息
        bound_logger = self.logger.bind(
            ai_call=True,
            ai_model=self.ai_model,
            ai_action=self.action,
            duration_ms=round(duration_ms, 2),
            success=status_text,
        )

        if self.success:
            bound_logger.info(message)
        else:
            bound_logger.error(message)

    def add_metadata(self, key: str, value: Any) -> "AICallTracker":
        """
        添加元数据

        Args:
            key: 元数据键
            value: 元数据值

        Returns:
            self，支持链式调用
        """
        self.metadata[key] = value
        return self


def track_ai_call(ai_model: str, action: str) -> AICallTracker:
    """
    追踪 AI 调用的便捷函数

    Args:
        ai_model: AI 模型名称
        action: 操作描述

    Returns:
        AICallTracker 实例

    Example:
        @track_ai_call("kimi", "公告清洗")
        async def clean_announcement(text: str):
            ...
    """
    return AICallTracker(ai_model, action)


@contextmanager
def track_operation(operation_name: str, log_level: str = "INFO"):
    """
    通用操作追踪器

    Args:
        operation_name: 操作名称
        log_level: 日志级别

    Example:
        with track_operation("数据库初始化"):
            await init_database()
    """
    logger_instance = get_logger("operation")
    start = time.perf_counter()

    logger_instance.log(
        log_level,
        f"🚀 开始: {operation_name}"
    )

    try:
        yield
        duration = (time.perf_counter() - start) * 1000
        logger_instance.log(
            log_level,
            f"✅ 完成: {operation_name} (耗时: {duration:.2f}ms)"
        )
    except Exception as e:
        duration = (time.perf_counter() - start) * 1000
        logger_instance.error(
            f"❌ 失败: {operation_name} (耗时: {duration:.2f}ms, 错误: {e})"
        )
        raise


# 性能统计
class PerformanceMetrics:
    """性能指标统计"""

    def __init__(self):
        self.ai_calls: Dict[str, list] = {}
        self.operation_times: Dict[str, list] = {}

    def record_ai_call(
        self,
        model: str,
        action: str,
        duration_ms: float,
        success: bool,
    ) -> None:
        """记录 AI 调用"""
        key = f"{model}:{action}"
        if key not in self.ai_calls:
            self.ai_calls[key] = []
        self.ai_calls[key].append({
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        })

    def get_stats(self, model: Optional[str] = None) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {}
        for key, calls in self.ai_calls.items():
            if model and not key.startswith(model):
                continue

            successful = [c for c in calls if c["success"]]
            failed = [c for c in calls if not c["success"]]

            durations = [c["duration_ms"] for c in calls]

            stats[key] = {
                "total_calls": len(calls),
                "successful": len(successful),
                "failed": len(failed),
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
                "min_duration_ms": min(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
            }

        return stats


# 全局性能指标实例
performance_metrics = PerformanceMetrics()


# 导出
__all__ = [
    "setup_logging",
    "get_logger",
    "logger",
    "AICallTracker",
    "track_ai_call",
    "track_operation",
    "performance_metrics",
]

logger = loguru_logger
