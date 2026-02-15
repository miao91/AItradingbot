"""
AI TradeBot - 风控熔断器

功能：
1. 美元指数 (DXY) 波动监控
2. 自动熔断触发
3. 降级模式支持
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, List, Optional

from shared.logging import get_logger


logger = get_logger(__name__)


class CircuitState(Enum):
    """熔断状态"""

    CLOSED = "closed"  # 正常
    OPEN = "open"  # 熔断
    HALF_OPEN = "half_open"  # 半开（恢复中）


@dataclass
class CircuitEvent:
    """熔断事件"""

    timestamp: str
    trigger: str
    old_state: CircuitState
    new_state: CircuitState
    detail: str


class CircuitBreaker:
    """
    风控熔断器

    触发条件：
    1. 美元指数 (DXY) 波动 > 0.5%
    2. AI 服务连续失败
    3. 系统异常

    熔断效果：
    - 禁止 AI 自动生成买入建议
    - 显示红色警告
    - 降级到保守模式
    """

    def __init__(
        self,
        dxy_threshold: float = 0.5,  # DXY 波动阈值 0.5%
        failure_threshold: int = 3,
        recovery_timeout: int = 300,  # 5分钟恢复
    ):
        self.dxy_threshold = dxy_threshold
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._events: List[CircuitEvent] = []

        # DXY 监控
        self._last_dxy_value: Optional[float] = None
        self._last_dxy_change: float = 0.0

        logger.info(f"[熔断器] 初始化完成, DXY阈值={dxy_threshold}%")

    @property
    def state(self) -> CircuitState:
        """当前状态"""
        # 检查是否可以恢复
        if self._state == CircuitState.OPEN:
            if self._should_attempt_recovery():
                self._transition(CircuitState.HALF_OPEN, "恢复超时")
        return self._state

    @property
    def is_tripped(self) -> bool:
        """是否已熔断"""
        return self.state in (CircuitState.OPEN, CircuitState.HALF_OPEN)

    def check_dxy(self, dxy_value: float, change_pct: float) -> bool:
        """
        检查美元指数波动

        Args:
            dxy_value: 当前 DXY 值
            change_pct: 变动百分比

        Returns:
            True = 正常, False = 触发熔断
        """
        self._last_dxy_value = dxy_value
        self._last_dxy_change = change_pct

        abs_change = abs(change_pct)

        if abs_change > self.dxy_threshold:
            logger.warning(
                f"[熔断器] DXY 波动 {change_pct:.3f}% > 阈值 {self.dxy_threshold}%"
            )
            self._transition(CircuitState.OPEN, f"DXY 波动 {change_pct:.3f}%")
            return False

        return True

    def check_forex_rate(self, current_rate: float) -> bool:
        """
        检查汇率波动（向后兼容）

        已废弃，建议使用 check_dxy()
        """
        logger.warning("[熔断器] check_forex_rate 已废弃，请使用 check_dxy()")
        return True

    def get_dxy_status(self) -> dict:
        """获取 DXY 监控状态"""
        return {
            "last_value": self._last_dxy_value,
            "last_change_pct": self._last_dxy_change,
            "threshold": self.dxy_threshold,
            "status": "danger" if abs(self._last_dxy_change) > self.dxy_threshold else "stable",
        }

    def record_success(self) -> None:
        """记录成功"""
        if self._state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.CLOSED, "恢复正常")
        self._failure_count = 0

    def record_failure(self) -> None:
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._failure_count >= self.failure_threshold:
            self._transition(CircuitState.OPEN, f"连续失败 {self._failure_count} 次")

    def _should_attempt_recovery(self) -> bool:
        """是否应该尝试恢复"""
        if self._last_failure_time is None:
            return True

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _transition(self, new_state: CircuitState, reason: str) -> None:
        """状态转换"""
        old_state = self._state
        self._state = new_state

        event = CircuitEvent(
            timestamp=datetime.now().isoformat(),
            trigger=reason,
            old_state=old_state,
            new_state=new_state,
            detail=f"从 {old_state.value} 转换到 {new_state.value}",
        )
        self._events.append(event)

        logger.warning(f"[熔断器] {old_state.value} → {new_state.value}, 原因: {reason}")

    def get_events(self, limit: int = 10) -> List[CircuitEvent]:
        """获取最近事件"""
        return self._events[-limit:]

    def reset(self) -> None:
        """重置熔断器"""
        self._transition(CircuitState.CLOSED, "手动重置")
        self._failure_count = 0
        self._last_failure_time = None


# =============================================================================
# 全局熔断器
# =============================================================================

_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """获取全局熔断器"""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker


async def check_circuit_breaker() -> bool:
    """
    检查熔断器状态（异步便捷函数）

    Returns:
        True = 可以继续, False = 已熔断
    """
    cb = get_circuit_breaker()
    return not cb.is_tripped


async def check_dxy_and_update_circuit() -> dict:
    """
    获取 DXY 数据并更新熔断器状态

    Returns:
        DXY 状态信息
    """
    try:
        from core.api.v1.external import get_dxy

        dxy_data = await get_dxy()
        cb = get_circuit_breaker()

        # 检查并更新熔断状态
        is_ok = cb.check_dxy(dxy_data["dxy_value"], dxy_data["change_pct"])

        return {
            "dxy_value": dxy_data["dxy_value"],
            "change_pct": dxy_data["change_pct"],
            "circuit_state": cb.state.value,
            "is_tripped": cb.is_tripped,
            "is_ok": is_ok,
        }
    except Exception as e:
        logger.error(f"[熔断器] DXY 检查失败: {e}")
        return {
            "dxy_value": None,
            "change_pct": 0,
            "circuit_state": "closed",
            "is_tripped": False,
            "is_ok": True,
            "error": str(e),
        }
