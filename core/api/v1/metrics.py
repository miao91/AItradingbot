"""
AI TradeBot - 监控指标 API

提供 Prometheus 格式的指标暴露
"""
from fastapi import APIRouter
from typing import Dict, Any
import time

from shared.logging import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


# =============================================================================
# 指标收集
# =============================================================================

_metrics = {
    # 计数器
    "ai_requests_total": 0,
    "ai_requests_success": 0,
    "ai_requests_failed": 0,

    # 直方图（简化版）
    "ai_latency_sum": 0.0,
    "ai_latency_count": 0,

    # 仪表盘
    "current_position_pnl": 0.0,
    "gpu_memory_used_mb": 0,
    "gpu_memory_total_mb": 0,

    # 系统
    "events_processed": 0,
    "trades_executed": 0,
    "circuit_breaker_trips": 0,
}


def record_ai_request(success: bool, latency_ms: float) -> None:
    """记录 AI 请求"""
    _metrics["ai_requests_total"] += 1
    if success:
        _metrics["ai_requests_success"] += 1
    else:
        _metrics["ai_requests_failed"] += 1

    _metrics["ai_latency_sum"] += latency_ms
    _metrics["ai_latency_count"] += 1


def update_gpu_memory(used_mb: int, total_mb: int) -> None:
    """更新 GPU 内存指标"""
    _metrics["gpu_memory_used_mb"] = used_mb
    _metrics["gpu_memory_total_mb"] = total_mb


def record_circuit_breaker_trip() -> None:
    """记录熔断器触发"""
    _metrics["circuit_breaker_trips"] += 1


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("")
async def get_metrics() -> str:
    """
    获取 Prometheus 格式指标

    格式：
    ```
    # HELP ai_requests_total AI 请求总数
    # TYPE ai_requests_total counter
    ai_requests_total 123

    # HELP ai_latency_avg AI 请求平均延迟(ms)
    # TYPE ai_latency_avg gauge
    ai_latency_avg 250.5
    ```
    """
    lines = []

    # AI 请求指标
    lines.append("# HELP ai_requests_total AI 请求总数")
    lines.append("# TYPE ai_requests_total counter")
    lines.append(f"ai_requests_total {_metrics['ai_requests_total']}")

    lines.append("# HELP ai_requests_success AI 请求成功数")
    lines.append("# TYPE ai_requests_success counter")
    lines.append(f"ai_requests_success {_metrics['ai_requests_success']}")

    lines.append("# HELP ai_requests_failed AI 请求失败数")
    lines.append("# TYPE ai_requests_failed counter")
    lines.append(f"ai_requests_failed {_metrics['ai_requests_failed']}")

    # 延迟
    if _metrics["ai_latency_count"] > 0:
        avg_latency = _metrics["ai_latency_sum"] / _metrics["ai_latency_count"]
    else:
        avg_latency = 0

    lines.append("# HELP ai_latency_avg_ms AI 请求平均延迟(ms)")
    lines.append("# TYPE ai_latency_avg_ms gauge")
    lines.append(f"ai_latency_avg_ms {avg_latency:.2f}")

    # GPU
    lines.append("# HELP gpu_memory_used_mb GPU 内存使用(MB)")
    lines.append("# TYPE gpu_memory_used_mb gauge")
    lines.append(f"gpu_memory_used_mb {_metrics['gpu_memory_used_mb']}")

    lines.append("# HELP gpu_memory_total_mb GPU 内存总量(MB)")
    lines.append("# TYPE gpu_memory_total_mb gauge")
    lines.append(f"gpu_memory_total_mb {_metrics['gpu_memory_total_mb']}")

    # 系统
    lines.append("# HELP events_processed 处理事件数")
    lines.append("# TYPE events_processed counter")
    lines.append(f"events_processed {_metrics['events_processed']}")

    lines.append("# HELP circuit_breaker_trips 熔断器触发次数")
    lines.append("# TYPE circuit_breaker_trips counter")
    lines.append(f"circuit_breaker_trips {_metrics['circuit_breaker_trips']}")

    return "\n".join(lines)


@router.get("/json")
async def get_metrics_json() -> Dict[str, Any]:
    """获取 JSON 格式指标"""
    # 计算平均延迟
    if _metrics["ai_latency_count"] > 0:
        avg_latency = _metrics["ai_latency_sum"] / _metrics["ai_latency_count"]
    else:
        avg_latency = 0

    # 计算成功率
    if _metrics["ai_requests_total"] > 0:
        success_rate = _metrics["ai_requests_success"] / _metrics["ai_requests_total"]
    else:
        success_rate = 1.0

    return {
        "success": True,
        "data": {
            "ai": {
                "requests_total": _metrics["ai_requests_total"],
                "requests_success": _metrics["ai_requests_success"],
                "requests_failed": _metrics["ai_requests_failed"],
                "success_rate": f"{success_rate*100:.1f}%",
                "avg_latency_ms": round(avg_latency, 2),
            },
            "gpu": {
                "memory_used_mb": _metrics["gpu_memory_used_mb"],
                "memory_total_mb": _metrics["gpu_memory_total_mb"],
                "memory_usage_percent": (
                    _metrics["gpu_memory_used_mb"] / _metrics["gpu_memory_total_mb"] * 100
                    if _metrics["gpu_memory_total_mb"] > 0 else 0
                ),
            },
            "system": {
                "events_processed": _metrics["events_processed"],
                "trades_executed": _metrics["trades_executed"],
                "circuit_breaker_trips": _metrics["circuit_breaker_trips"],
            },
            "timestamp": time.time(),
        }
    }


@router.get("/valuation-drift")
async def get_valuation_drift() -> Dict[str, Any]:
    """
    获取估值漂移率

    AI 估值 vs 实际市场波动
    """
    # 简化实现 - 返回模拟数据
    return {
        "success": True,
        "data": {
            "drift_rate": 0.02,  # 2% 漂移
            "ai_valuation": 100.0,
            "market_price": 98.0,
            "status": "normal",
            "message": "估值与市场价格基本一致",
        }
    }


@router.get("/model-fallback")
async def get_model_fallback_stats() -> Dict[str, Any]:
    """
    获取模型降级状态

    显示各模型的健康状态和降级统计
    """
    try:
        from core.orchestrator import get_fallback_manager

        manager = get_fallback_manager()
        stats = manager.get_stats()

        return {
            "success": True,
            "data": {
                "total_requests": stats["total_requests"],
                "successful_requests": stats["successful_requests"],
                "fallback_requests": stats["fallback_requests"],
                "local_fallbacks": stats["local_fallbacks"],
                "success_rate": f"{stats['success_rate']:.1f}%",
                "model_status": stats["model_status"],
            },
        }
    except Exception as e:
        logger.error(f"[指标] 获取模型降级状态失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": None,
        }


@router.get("/dxy")
async def get_dxy_status() -> Dict[str, Any]:
    """
    获取美元指数 (DXY) 监控状态

    显示 DXY 值、变动百分比、熔断器状态
    """
    try:
        from core.risk import check_dxy_and_update_circuit

        status = await check_dxy_and_update_circuit()

        return {
            "success": True,
            "data": {
                "dxy_value": status["dxy_value"],
                "change_pct": status["change_pct"],
                "circuit_state": status["circuit_state"],
                "is_tripped": status["is_tripped"],
                "threshold_pct": 0.5,  # 熔断阈值
                "status": "danger" if status["is_tripped"] else "stable",
            },
        }
    except Exception as e:
        logger.error(f"[指标] 获取 DXY 状态失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": None,
        }


__all__ = ["router", "record_ai_request", "update_gpu_memory", "record_circuit_breaker_trip"]
