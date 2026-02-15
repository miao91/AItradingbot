"""
AI TradeBot - 风控模块

监控美元指数 (DXY) 波动，触发熔断保护
"""

from core.risk.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    check_circuit_breaker,
    check_dxy_and_update_circuit,
    get_circuit_breaker,
)

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "get_circuit_breaker",
    "check_circuit_breaker",
    "check_dxy_and_update_circuit",
]
