"""
AI TradeBot - 推理链 API

提供 AI 思维链展示的后端接口
支持 SSE (Server-Sent Events) 流式推送
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import json
import asyncio

from shared.logging import get_logger
from decision.engine.reasoning_engine import (
    get_reasoning_engine,
    ReasoningStatus,
)


logger = get_logger(__name__)


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/reasoning", tags=["reasoning"])


# =============================================================================
# Request Models
# =============================================================================

class StartReasoningRequest(BaseModel):
    """启动推理请求"""
    ticker: str
    event_description: str
    context: Optional[Dict[str, Any]] = None


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/start")
async def start_reasoning(request: StartReasoningRequest):
    """
    启动推理链

    创建新的推理链并返回 chain_id
    """
    try:
        engine = get_reasoning_engine()

        chain = await engine.start_reasoning(
            ticker=request.ticker,
            event_description=request.event_description,
            context=request.context,
        )

        logger.info(f"[推理 API] 启动推理链: {chain.chain_id} for {request.ticker}")

        return {
            "success": True,
            "data": {
                "chain_id": chain.chain_id,
                "ticker": chain.ticker,
                "status": chain.status.value,
                "created_at": chain.created_at,
            }
        }

    except Exception as e:
        logger.error(f"[推理 API] 启动失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/stream/{chain_id}")
async def stream_reasoning(chain_id: str):
    """
    流式获取推理步骤 (SSE)

    通过 Server-Sent Events 实时推送推理步骤
    """
    engine = get_reasoning_engine()
    chain = engine.get_chain(chain_id)

    if not chain:
        raise HTTPException(status_code=404, detail="推理链不存在")

    async def event_generator():
        """SSE 事件生成器"""
        try:
            async for step in engine.stream_reasoning(chain):
                # 构建 SSE 事件
                event_data = json.dumps(step.to_dict(), ensure_ascii=False)
                yield f"data: {event_data}\n\n"

                # 添加延迟模拟真实推理
                await asyncio.sleep(0.3)

            # 发送完成事件
            final_data = json.dumps({
                "type": "complete",
                "chain_id": chain.chain_id,
                "status": chain.status.value,
                "completed_at": chain.completed_at,
            }, ensure_ascii=False)
            yield f"data: {final_data}\n\n"

        except Exception as e:
            logger.error(f"[推理 API] 流式推送异常: {e}")
            error_data = json.dumps({
                "type": "error",
                "error": str(e),
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/chain/{chain_id}")
async def get_chain_status(chain_id: str):
    """
    获取推理链状态

    返回推理链的当前状态和所有步骤
    """
    engine = get_reasoning_engine()
    chain = engine.get_chain(chain_id)

    if not chain:
        raise HTTPException(status_code=404, detail="推理链不存在")

    return {
        "success": True,
        "data": chain.to_dict()
    }


@router.post("/demo")
async def demo_reasoning():
    """
    演示推理过程

    返回模拟的推理步骤（用于前端测试）
    """
    # 模拟推理步骤
    demo_steps = [
        {"step_id": 1, "icon": "📊", "name": "数据采集", "content": "正在分析全球情报数据...", "status": "completed"},
        {"step_id": 2, "icon": "🌍", "name": "地缘政治分析", "content": "识别到美联储政策转向信号，美元指数回落。", "status": "completed"},
        {"step_id": 3, "icon": "💱", "name": "汇率锚点", "content": "USD/CNH 当前 7.24，处于正常波动区间。", "status": "completed"},
        {"step_id": 4, "icon": "🔍", "name": "市场扫描", "content": "基于情报分析，科技成长板块具备重估机会。", "status": "completed"},
        {"step_id": 5, "icon": "🧠", "name": "AI 深思", "content": "调用 AI 模型进行深度分析...", "status": "completed"},
        {"step_id": 6, "icon": "📈", "name": "五维评估", "content": "重塑性 8.5分、持续性 9.0分、地缘传导 7.5分、定价偏离 8.0分、流动性 8.5分", "status": "completed"},
        {"step_id": 7, "icon": "🎯", "name": "目标锁定", "content": "锁定科技成长板块（半导体、AI 产业链）。", "status": "completed"},
        {"step_id": 8, "icon": "⚙️", "name": "模型选择", "content": "识别为高成长行业，采用 PS 估值模型。", "status": "completed"},
        {"step_id": 9, "icon": "🐍", "name": "代码生成", "content": "正在编写 Python 估值脚本...", "status": "completed"},
        {"step_id": 10, "icon": "✅", "name": "代码验证", "content": "语法检查通过，准备执行计算。", "status": "completed"},
        {"step_id": 11, "icon": "🚀", "name": "计算执行", "content": "正在运行 Python 脚本，生成三档估值...", "status": "completed"},
    ]

    return {
        "success": True,
        "data": {
            "chain_id": "demo_chain",
            "ticker": "DEMO",
            "event_description": "演示推理过程",
            "steps": demo_steps,
            "status": "completed",
            "final_result": {
                "valuation_range": "3500 - 4200 点",
                "recommendation": "高配科技成长板块",
                "confidence": 0.85,
            }
        }
    }


__all__ = ["router"]
