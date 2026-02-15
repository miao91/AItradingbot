"""API v1 module"""
from fastapi import APIRouter
from core.api.v1.public import router as public_router
from core.api.v1 import showcase as showcase_router
from core.api.v1.external import router as external_router
from core.api.v1.reasoning import router as reasoning_router
from core.api.v1.monte_carlo import router as monte_carlo_router
from core.api.v1.health import router as health_router
from core.api.v1.news import router as news_router
from core.api.v1.newspapers import router as papers_router
from core.api.v1.metrics import router as metrics_router
try:
    from decision.workflows.realtime_router import router as realtime_router
    REALTIME_AVAILABLE = True
except ImportError:
    REALTIME_AVAILABLE = False

# 创建统一的 v1 路由器
router = APIRouter(prefix="/api/v1", tags=["v1"])

# 包含子路由
router.include_router(public_router)

# Showcase 控制面板路由
router.include_router(showcase_router.router)

# 外部数据路由（FunHub 汇率等）
router.include_router(external_router)

# 推理链路由（AI 思维链展示）
router.include_router(reasoning_router)

# 蒙特卡洛模拟路由（GPU 加速概率分布估值）
router.include_router(monte_carlo_router)

# 系统健康检查路由
router.include_router(health_router)

# 新闻快讯路由
router.include_router(news_router)

# 报纸订阅路由
router.include_router(papers_router)

# 监控指标路由
router.include_router(metrics_router)

if REALTIME_AVAILABLE:
    router.include_router(realtime_router)

__all__ = ["router"]
