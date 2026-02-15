"""
AI TradeBot - 蒙特卡洛模拟 API

提供概率分布估值的后端接口
支持 100,000+ 次并行模拟
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import asyncio
import json

from shared.logging import get_logger
from decision.engine.monte_carlo_engine import (
    get_monte_carlo_engine,
    SimulationInput,
    SimulationResult,
    DistributionParams,
    detect_gpu_backend,
)


logger = get_logger(__name__)


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/monte-carlo", tags=["monte-carlo"])


# =============================================================================
# Request Models
# =============================================================================

class DistributionParamsRequest(BaseModel):
    """分布参数请求"""
    mean: float = 0.1
    std: float = 0.05
    distribution_type: str = "normal"  # normal, lognormal, triangular


class MonteCarloRequest(BaseModel):
    """蒙特卡洛模拟请求"""
    ticker: str
    current_price: float

    # 分布参数
    revenue_growth: Optional[DistributionParamsRequest] = None
    discount_rate: Optional[DistributionParamsRequest] = None
    terminal_multiple: Optional[DistributionParamsRequest] = None
    profit_margin: Optional[DistributionParamsRequest] = None

    # 模拟配置
    num_simulations: int = 100000
    time_horizon: int = 5
    geopolitical_risk: float = 0.0


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/simulate")
async def run_simulation(request: MonteCarloRequest):
    """
    执行蒙特卡洛模拟

    返回概率分布估值结果，包含 VaR、Expected Shortfall 等风险指标
    """
    try:
        engine = get_monte_carlo_engine()

        # 构建模拟输入
        def make_params(req: Optional[DistributionParamsRequest], default_mean: float, default_std: float):
            if req:
                return DistributionParams(
                    distribution_type=req.distribution_type,
                    mean=req.mean,
                    std=req.std,
                )
            return DistributionParams(
                distribution_type="normal",
                mean=default_mean,
                std=default_std,
            )

        inputs = SimulationInput(
            ticker=request.ticker,
            current_price=request.current_price,
            revenue_growth=make_params(request.revenue_growth, 0.10, 0.05),
            discount_rate=make_params(request.discount_rate, 0.12, 0.02),
            terminal_multiple=make_params(request.terminal_multiple, 10.0, 2.0),
            profit_margin=make_params(request.profit_margin, 0.15, 0.03),
            num_simulations=request.num_simulations,
            time_horizon=request.time_horizon,
            geopolitical_risk=request.geopolitical_risk,
        )

        logger.info(
            f"[蒙特卡洛 API] 开始模拟: {request.ticker}, "
            f"次数={request.num_simulations}, "
            f"当前价格={request.current_price}"
        )

        # 执行模拟
        result = engine.simulate(inputs)

        logger.info(
            f"[蒙特卡洛 API] 模拟完成: 耗时={result.compute_time_ms:.0f}ms, "
            f"GPU={result.gpu_used}"
        )

        return {
            "success": True,
            "data": {
                "ticker": result.ticker,
                "num_simulations": result.num_simulations,
                "compute_time_ms": result.compute_time_ms,
                "backend": result.backend,
                "gpu_used": result.gpu_used,
                "gpu_name": result.gpu_name,
                "parallel_threads": result.parallel_threads,

                # 估值分布
                "valuation": {
                    "mean": round(result.mean_value, 2),
                    "median": round(result.median_value, 2),
                    "std": round(result.std_value, 2),
                    "min": round(result.min_value, 2),
                    "max": round(result.max_value, 2),
                },

                # 分位数
                "percentiles": {
                    k: round(v, 2) for k, v in result.percentiles.items()
                },

                # 风险指标
                "risk_metrics": {
                    "var_95": round(result.var_95, 2),
                    "var_99": round(result.var_99, 2),
                    "expected_shortfall_95": round(result.expected_shortfall_95, 2),
                    "expected_shortfall_99": round(result.expected_shortfall_99, 2),
                },

                # 概率分析
                "probability": {
                    "above_current": round(result.prob_above_current * 100, 1),
                    "above_mean": round(result.prob_above_mean * 100, 1),
                    "tail_risk": round(result.tail_risk_probability * 100, 2),
                },

                # 置信区间
                "confidence_intervals": {
                    f"{int(k*100)}%": [round(v[0], 2), round(v[1], 2)]
                    for k, v in result.confidence_intervals.items()
                },

                # 分布数据（用于可视化）
                "distribution": {
                    "histogram": result.distribution_histogram,
                    "bin_edges": result.bin_edges,
                },

                # 投资建议
                "recommendation": _generate_recommendation(result, request.current_price),

                "simulated_at": result.simulated_at,
            }
        }

    except Exception as e:
        logger.error(f"[蒙特卡洛 API] 模拟失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/status")
async def get_engine_status():
    """
    获取蒙特卡洛引擎状态

    返回当前计算后端和 GPU 信息
    """
    try:
        backend_type, message = detect_gpu_backend()

        return {
            "success": True,
            "data": {
                "backend": backend_type.value,
                "message": message,
                "gpu_available": backend_type.value in ["cupy", "pytorch"],
                "default_simulations": 100000,
                "supported_distributions": [
                    "normal",
                    "lognormal",
                    "triangular",
                    "uniform",
                ],
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/quick-demo")
async def quick_demo(ticker: str = "600000.SH", current_price: float = 95.0):
    """
    快速演示蒙特卡洛模拟

    使用默认参数执行 50,000 次模拟
    """
    from decision.engine.monte_carlo_engine import run_monte_carlo_simulation

    try:
        logger.info(f"[蒙特卡洛 API] 快速演示: {ticker}")

        result = run_monte_carlo_simulation(
            ticker=ticker,
            current_price=current_price,
            growth_mean=0.10,
            growth_std=0.05,
            discount_mean=0.12,
            discount_std=0.02,
            terminal_mean=10.0,
            terminal_std=2.0,
            margin_mean=0.15,
            margin_std=0.03,
            geopolitical_risk=0.05,
            num_simulations=50000,  # 演示用较少次数
        )

        return {
            "success": True,
            "data": {
                "ticker": result.ticker,
                "current_price": current_price,
                "simulations": result.num_simulations,
                "compute_time_ms": round(result.compute_time_ms, 1),
                "backend": result.backend,
                "gpu_used": result.gpu_used,

                "valuation": {
                    "mean": round(result.mean_value, 2),
                    "median": round(result.median_value, 2),
                    "range": f"{round(result.min_value, 2)} - {round(result.max_value, 2)}",
                },

                "risk": {
                    "var_95": round(result.var_95, 2),
                    "es_95": round(result.expected_shortfall_95, 2),
                },

                "probability": {
                    "above_current": f"{round(result.prob_above_current * 100, 1)}%",
                    "tail_risk": f"{round(result.tail_risk_probability * 100, 2)}%",
                },

                "confidence_95": [
                    round(result.confidence_intervals.get(0.95, (0, 0))[0], 2),
                    round(result.confidence_intervals.get(0.95, (0, 0))[1], 2),
                ],

                "distribution_histogram": result.distribution_histogram,
                "bin_edges": result.bin_edges,

                "recommendation": _generate_recommendation(result, current_price),
            }
        }

    except Exception as e:
        logger.error(f"[蒙特卡洛 API] 演示失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _generate_recommendation(result: SimulationResult, current_price: float) -> str:
    """生成投资建议"""
    prob = result.prob_above_current

    if prob > 0.75:
        confidence = "极高"
        action = "当前价格处于概率分布的底部区域，上涨空间大，胜率较高"
    elif prob > 0.60:
        confidence = "较高"
        action = "当前价格低于中位数，具备一定安全边际"
    elif prob > 0.45:
        confidence = "中等"
        action = "当前价格接近合理估值区间"
    elif prob > 0.30:
        confidence = "较低"
        action = "当前价格略高于中位数，建议谨慎"
    else:
        confidence = "低"
        action = "当前价格处于高位，风险较大，不建议追高"

    # 添加风险提示
    if result.tail_risk_probability > 0.10:
        action += f"。注意：长尾风险概率 {result.tail_risk_probability*100:.1f}% 偏高"

    return f"【{confidence}信心】{action}"


__all__ = ["router"]
