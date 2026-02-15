"""
AI TradeBot - 系统健康检查 API
"""
from fastapi import APIRouter
from datetime import datetime

from shared.logging import get_logger
from decision.engine.health_checker import run_system_health_check


logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/check")
async def full_health_check():
    """
    执行完整的系统健康检查

    检查项目：
    1. 汇率预警联动
    2. 语言隔离
    3. 异步非阻塞
    4. 幻觉防护
    5. 行业适配
    """
    try:
        report = await run_system_health_check()
        return report.to_dict()
    except Exception as e:
        logger.error(f"[健康检查 API] 检查失败: {e}")
        return {
            "overall_status": "fail",
            "is_healthy": False,
            "error": str(e),
            "checked_at": datetime.now().isoformat(),
        }


@router.get("/quick")
async def quick_health():
    """
    快速健康检查

    返回系统基本状态
    """
    import os

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2026 Flagship",
        "environment": os.getenv("ENVIRONMENT", "development"),
    }


@router.get("/gpu")
async def gpu_status():
    """
    GPU 状态检查

    返回 GPU 计算后端信息
    """
    try:
        from decision.engine.monte_carlo_engine import detect_gpu_backend

        backend_type, message = detect_gpu_backend()

        return {
            "success": True,
            "data": {
                "backend": backend_type.value,
                "message": message,
                "gpu_available": backend_type.value in ["cupy", "pytorch"],
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


__all__ = ["router"]
