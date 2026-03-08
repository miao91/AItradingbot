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
from core.api.v1.stock_picker import router as stock_picker_router

try:
    from decision.workflows.realtime_router import router as realtime_router
    REALTIME_AVAILABLE = True
except ImportError:
    REALTIME_AVAILABLE = False


# Create unified v1 router
router = APIRouter(prefix="/api/v1", tags=["v1"])


# Include sub-routers
router.include_router(public_router)

# Showcase control panel router
router.include_router(showcase_router.router)

# External data router
router.include_router(external_router)

# Reasoning chain router
router.include_router(reasoning_router)

# Monte Carlo simulation router
router.include_router(monte_carlo_router)

# Health check router
router.include_router(health_router)

# News router
router.include_router(news_router)

# Newspapers router
router.include_router(papers_router)

# Metrics router
router.include_router(metrics_router)

# Stock picker router (Wall Street multi-factor)
router.include_router(stock_picker_router)

if REALTIME_AVAILABLE:
    router.include_router(realtime_router)

__all__ = ["router"]
