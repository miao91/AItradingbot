"""
AI TradeBot - Showcase 控制面板 API

提供作战室控制面板的后端接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 辅助函数
# =============================================================================

def _get_app_manager():
    """延迟导入 app_manager 以避免循环导入"""
    from core.api.app import manager as app_manager
    return app_manager


# =============================================================================
# Router
# =============================================================================

router = APIRouter(tags=["showcase"])


# =============================================================================
# Request Models
# =============================================================================

class PaperParseRequest(BaseModel):
    """报刊解析请求"""
    date: Optional[str] = None  # YYYY-MM-DD，null 表示今天


class ServiceToggleRequest(BaseModel):
    """服务开关请求"""
    enabled: bool


class ManualAnalysisRequest(BaseModel):
    """手动分析触发请求"""
    trigger: str
    ticker: Optional[str] = None
    event_description: Optional[str] = None


# =============================================================================
# 全局服务状态
# =============================================================================

_service_states = {
    "tushare": {"active": False, "started_at": None},
    "discord": {"active": False, "started_at": None},
    "valuation": {"active": False, "started_at": None},
    "crypto": {"active": False, "started_at": None}
}


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/papers/parse")
async def parse_papers(request: PaperParseRequest):
    """
    解析今日报刊

    触发 ManualPaperReader 解析英文报刊
    提取宏观参数（利率、GDP、通胀等）
    """
    try:
        from perception.papers.manual_reader import trigger_manual_analysis

        logger.info(f"[Showcase API] 触发报刊解析: {request.date or '今日'}")

        # 异步触发解析
        results = await trigger_manual_analysis(date=request.date)

        if not results:
            return {
                "success": False,
                "error": "未找到报刊文件或解析失败"
            }

        # 汇总提取的参数
        all_params = []
        papers_count = 0

        for result in results:
            papers_count += 1
            if result.extracted_params:
                for param_name, param_value in result.extracted_params.items():
                    all_params.append({
                        "paper": result.paper_name,
                        "param_name": param_name,
                        "value": param_value
                    })

        # 广播解析完成
        app_manager = _get_app_manager()
        await app_manager.broadcast({
            "type": "papers_parsed",
            "data": {
                "papers_count": papers_count,
                "extracted_params": all_params,
                "timestamp": datetime.now().isoformat()
            }
        })

        return {
            "success": True,
            "data": {
                "papers_count": papers_count,
                "extracted_params": all_params
            }
        }

    except Exception as e:
        logger.error(f"[Showcase API] 报刊解析失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/discord/toggle")
async def toggle_discord(request: ServiceToggleRequest):
    """
    切换 Discord 协作服务

    启动/停止 Discord Bot 和 Clawdbot 协作
    """
    try:
        logger.info(f"[Showcase API] {'启动' if request.enabled else '停止'} Discord 协作")

        # 更新状态
        _service_states["discord"]["active"] = request.enabled
        _service_states["discord"]["started_at"] = datetime.now().isoformat() if request.enabled else None

        # 广播状态更新
        app_manager = _get_app_manager()
        await app_manager.broadcast({
            "type": "service_status",
            "data": {
                "service": "discord",
                "active": request.enabled,
                "timestamp": datetime.now().isoformat()
            }
        })

        # TODO: 实际启动/停止 Discord Bot
        # from decision.workflows.discord_workflow import start_discord_workflow
        # if request.enabled:
        #     await start_discord_workflow()

        return {
            "success": True,
            "data": {
                "service": "discord",
                "active": request.enabled
            }
        }

    except Exception as e:
        logger.error(f"[Showcase API] Discord 切换失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/crypto/toggle")
async def toggle_crypto(request: ServiceToggleRequest):
    """
    切换 CryptoPanic 加密流

    启用/禁用 CryptoPanic 哨兵
    """
    try:
        logger.info(f"[Showcase API] {'启用' if request.enabled else '禁用'} CryptoPanic 流")

        # 更新状态
        _service_states["crypto"]["active"] = request.enabled
        _service_states["crypto"]["started_at"] = datetime.now().isoformat() if request.enabled else None

        # TODO: 实际启动/停止 CryptoPanic 哨兵
        # from perception.news.cryptopanic_sentinel import start_cryptopanic_monitoring
        # if request.enabled:
        #     await start_cryptopanic_monitoring()

        return {
            "success": True,
            "data": {
                "service": "crypto",
                "active": request.enabled
            }
        }

    except Exception as e:
        logger.error(f"[Showcase API] Crypto 切换失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/analysis/trigger")
async def trigger_manual_analysis(request: ManualAnalysisRequest):
    """
    手动触发分析流程

    立即启动一次完整的事件分析流程
    """
    try:
        logger.info(f"[Showcase API] 手动触发分析: {request.trigger}")

        # TODO: 实际触发分析流程
        # from decision.workflows.event_analyzer import analyze_event
        # result = await analyze_event(...)

        return {
            "success": True,
            "data": {
                "message": "分析已加入队列",
                "trigger": request.trigger
            }
        }

    except Exception as e:
        logger.error(f"[Showcase API] 手动分析失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/services/status")
async def get_services_status():
    """
    获取所有服务状态

    返回各服务的当前运行状态
    """
    return {
        "success": True,
        "data": {
            "services": _service_states,
            "timestamp": datetime.now().isoformat()
        }
    }


class ImpactMatrixRequest(BaseModel):
    """影响矩阵分析请求"""
    news_content: str
    source: Optional[str] = "manual"  # manual, newspaper, realtime


@router.post("/impact-matrix")
async def analyze_impact_matrix(request: ImpactMatrixRequest):
    """
    结构化影响矩阵分析

    将新闻内容解析为标准化的影响矩阵表格
    用于"深思模式"可视化展示
    """
    try:
        from core.orchestrator import get_orchestrator

        logger.info(f"[Showcase API] 影响矩阵分析，来源: {request.source}")

        orchestrator = get_orchestrator()
        matrices = await orchestrator.analyze_with_impact_matrix(request.news_content)

        # 转换为可序列化的格式
        matrix_data = []
        for m in matrices:
            matrix_data.append({
                "news_summary": m.news_summary,
                "geopolitical_score": m.geopolitical_score,
                "tech_breakthrough": m.tech_breakthrough,
                "policy_relevance": m.policy_relevance,
                "supply_chain_impact": m.supply_chain_impact,
                "cost_price_change": m.cost_price_change,
                "related_companies": m.related_companies,
                "overall_score": m.overall_score,
            })

        return {
            "success": True,
            "data": {
                "matrices": matrix_data,
                "count": len(matrix_data),
                "source": request.source,
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"[Showcase API] 影响矩阵分析失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {"matrices": [], "count": 0}
        }


@router.post("/global-intel")
async def analyze_global_intel():
    """
    研读全球情报

    从今日报刊中提取重要新闻，生成影响矩阵
    """
    try:
        from core.orchestrator import get_orchestrator
        from core.api.v1.newspapers import get_latest_news_summary

        logger.info("[Showcase API] 研读全球情报")

        # 获取今日新闻摘要
        news_summary = await get_latest_news_summary()

        if not news_summary:
            return {
                "success": False,
                "error": "未找到今日新闻",
                "data": {"matrices": [], "count": 0}
            }

        # 调用影响矩阵分析
        orchestrator = get_orchestrator()
        matrices = await orchestrator.analyze_with_impact_matrix(news_summary)

        matrix_data = []
        for m in matrices:
            matrix_data.append({
                "news_summary": m.news_summary,
                "geopolitical_score": m.geopolitical_score,
                "tech_breakthrough": m.tech_breakthrough,
                "policy_relevance": m.policy_relevance,
                "supply_chain_impact": m.supply_chain_impact,
                "cost_price_change": m.cost_price_change,
                "related_companies": m.related_companies,
                "overall_score": m.overall_score,
            })

        return {
            "success": True,
            "data": {
                "matrices": matrix_data,
                "count": len(matrix_data),
                "source": "newspaper",
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"[Showcase API] 研读全球情报失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {"matrices": [], "count": 0}
        }


__all__ = ["router"]
