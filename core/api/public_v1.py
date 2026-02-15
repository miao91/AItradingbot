"""
AI TradeBot - Public API v1

只读接口，供外部网站 www.myrwaai.com 调用
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

from core.database.session import get_db_context
from storage.models.trade_event import TradeEvent, EventStatus
from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# Response Models
# =============================================================================

class ExitPlanPublic(BaseModel):
    """退出计划（公开版）"""
    take_profit_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    expire_time: Optional[str] = None
    target_return_ratio: Optional[float] = None  # 目标收益率


class EntryPlanPublic(BaseModel):
    """入场计划（公开版）"""
    trigger_price: Optional[float] = None
    quantity: int


class EventPublic(BaseModel):
    """交易事件（公开版）"""
    id: str
    ticker: str
    ticker_name: Optional[str] = None
    direction: str
    current_status: str
    logic_summary: Optional[str] = None
    confidence: Optional[float] = None

    # 入场信息
    entry_plan: Optional[EntryPlanPublic] = None
    actual_entry_price: Optional[float] = None
    actual_entry_time: Optional[str] = None

    # 退出计划
    exit_plan: Optional[ExitPlanPublic] = None
    actual_exit_price: Optional[float] = None
    actual_exit_time: Optional[str] = None
    exit_reason: Optional[str] = None

    # 盈亏统计
    realized_pnl: Optional[float] = None
    realized_pnl_ratio: Optional[float] = None

    # 时间
    created_at: str
    updated_at: str

    # 事件描述
    event_description: Optional[str] = None

    # 参与的AI模型
    ai_participants: List[str] = []

    class Config:
        json_schema_extra = {
            "example": {
                "id": "TEV_20260211_120000",
                "ticker": "600519.SH",
                "ticker_name": "贵州茅台",
                "direction": "long",
                "current_status": "position_open",
                "logic_summary": "白酒龙头业绩超预期，估值修复空间打开",
                "confidence": 0.78,
                "actual_entry_price": 1680.50,
                "actual_entry_time": "2026-02-11T14:00:00",
                "exit_plan": {
                    "take_profit_price": 1850.00,
                    "stop_loss_price": 1600.00,
                    "target_return_ratio": 10.09
                }
            }
        }


class ActiveEventsResponse(BaseModel):
    """活跃事件响应"""
    total: int
    events: List[EventPublic]
    last_updated: str


class DashboardStats(BaseModel):
    """仪表板统计"""
    total_events: int
    observing_count: int
    pending_confirm_count: int
    position_open_count: int
    closed_count: int
    total_pnl: Optional[float] = None
    win_rate: Optional[float] = None


# =============================================================================
# Router
# =============================================================================

router = APIRouter(
    prefix="/public/v1",
    tags=["public"],
    responses={
        200: {"description": "Success"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"}
    }
)


# =============================================================================
# Helper Functions
# =============================================================================

def _to_public_event(event: TradeEvent) -> EventPublic:
    """转换为公开事件模型"""

    # 入场计划
    entry_plan_public = None
    if event.entry_plan:
        entry_plan_public = EntryPlanPublic(
            trigger_price=event.entry_plan.get("trigger_price"),
            quantity=event.entry_plan.get("quantity", 0)
        )

    # 退出计划
    exit_plan_public = None
    if event.exit_plan:
        tp_price = event.exit_plan.get("take_profit", {}).get("price") if event.exit_plan.get("take_profit") else None
        sl_price = event.exit_plan.get("stop_loss", {}).get("price") if event.exit_plan.get("stop_loss") else None
        expire_time = event.exit_plan.get("expiration", {}).get("expire_time") if event.exit_plan.get("expiration") else None

        # 计算目标收益率
        target_return_ratio = None
        if tp_price and event.actual_entry_price:
            target_return_ratio = (tp_price - event.actual_entry_price) / event.actual_entry_price * 100

        exit_plan_public = ExitPlanPublic(
            take_profit_price=tp_price,
            stop_loss_price=sl_price,
            expire_time=expire_time,
            target_return_ratio=round(target_return_ratio, 2) if target_return_ratio else None
        )

    return EventPublic(
        id=event.id,
        ticker=event.ticker,
        ticker_name=event.ticker_name,
        direction=event.direction.value,
        current_status=event.current_status.value,
        logic_summary=event.logic_summary,
        confidence=event.confidence,
        entry_plan=entry_plan_public,
        actual_entry_price=event.actual_entry_price,
        actual_entry_time=event.actual_entry_time.isoformat() if event.actual_entry_time else None,
        exit_plan=exit_plan_public,
        actual_exit_price=event.actual_exit_price,
        actual_exit_time=event.actual_exit_time.isoformat() if event.actual_exit_time else None,
        exit_reason=event.exit_reason,
        realized_pnl=event.realized_pnl,
        realized_pnl_ratio=event.realized_pnl_ratio,
        created_at=event.created_at.isoformat() if event.created_at else "",
        updated_at=event.updated_at.isoformat() if event.updated_at else "",
        event_description=event.event_description,
        ai_participants=event.ai_participants or []
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/active_events", response_model=ActiveEventsResponse)
async def get_active_events(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    获取活跃的交易事件

    Args:
        status: 过滤状态 (observing/pending_confirm/position_open/take_profit等)
        limit: 返回数量限制 (默认50, 最大100)
        offset: 偏移量 (用于分页)

    Returns:
        ActiveEventsResponse 包含事件列表和统计信息
    """
    try:
        # 参数校验
        limit = min(limit, 100)

        async with get_db_context() as db:
            from sqlalchemy import select, desc

            # 构建查询
            query = select(TradeEvent).order_by(desc(TradeEvent.created_at))

            # 状态过滤
            if status:
                try:
                    status_enum = EventStatus(status)
                    query = query.where(TradeEvent.current_status == status_enum)
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

            # 分页
            query = query.limit(limit).offset(offset)

            result = await db.execute(query)
            events = result.scalars().all()

            # 转换为公开模型
            public_events = [_to_public_event(e) for e in events]

            return ActiveEventsResponse(
                total=len(public_events),
                events=public_events,
                last_updated=datetime.now().isoformat()
            )

    except Exception as e:
        logger.error(f"Error in get_active_events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/event/{event_id}", response_model=EventPublic)
async def get_event_detail(event_id: str):
    """
    获取单个事件详情

    Args:
        event_id: 事件ID

    Returns:
        EventPublic 事件详情
    """
    try:
        async with get_db_context() as db:
            from sqlalchemy import select

            result = await db.execute(
                select(TradeEvent).where(TradeEvent.id == event_id)
            )
            event = result.scalar_one_or_none()

            if not event:
                raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")

            return _to_public_event(event)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_event_detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    获取仪表板统计数据

    Returns:
        DashboardStats 统计信息
    """
    try:
        async with get_db_context() as db:
            from sqlalchemy import select, func

            # 统计各状态数量
            result = await db.execute(
                select(
                    TradeEvent.current_status,
                    func.count(TradeEvent.id)
                ).group_by(TradeEvent.current_status)
            )
            status_counts = {row[0].value: row[1] for row in result.all()}

            # 总事件数
            total_result = await db.execute(select(func.count(TradeEvent.id)))
            total_events = total_result.scalar() or 0

            # 计算盈亏统计（仅统计已平仓事件）
            pnl_result = await db.execute(
                select(
                    func.sum(TradeEvent.realized_pnl),
                    func.count(TradeEvent.id).label("total_closed"),
                    func.sum(
                        func.case(
                            (TradeEvent.realized_pnl > 0, 1),
                            else_=0
                        )
                    ).label("win_count")
                ).where(
                    TradeEvent.current_status.in_([
                        EventStatus.TAKE_PROFIT,
                        EventStatus.STOPPED_OUT,
                        EventStatus.LOGIC_EXPIRED,
                        EventStatus.MANUAL_CLOSE
                    ])
                )
            )
            pnl_row = pnl_result.one_or_none()

            total_pnl = pnl_row[0] if pnl_row and pnl_row[0] else 0
            total_closed = pnl_row[1] if pnl_row and pnl_row[1] else 0
            win_count = pnl_row[2] if pnl_row and pnl_row[2] else 0

            win_rate = (win_count / total_closed * 100) if total_closed > 0 else None

            return DashboardStats(
                total_events=total_events,
                observing_count=status_counts.get("observing", 0),
                pending_confirm_count=status_counts.get("pending_confirm", 0),
                position_open_count=status_counts.get("position_open", 0),
                closed_count=(
                    status_counts.get("take_profit", 0) +
                    status_counts.get("stopped_out", 0) +
                    status_counts.get("logic_expired", 0) +
                    status_counts.get("manual_close", 0)
                ),
                total_pnl=round(total_pnl, 2) if total_pnl else None,
                win_rate=round(win_rate, 2) if win_rate else None
            )

    except Exception as e:
        logger.error(f"Error in get_dashboard_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions", response_model=List[EventPublic])
async def get_current_positions():
    """
    获取当前持仓列表

    Returns:
        List[EventPublic] 持仓中的事件列表
    """
    try:
        async with get_db_context() as db:
            from sqlalchemy import select, desc

            result = await db.execute(
                select(TradeEvent)
                .where(TradeEvent.current_status == EventStatus.POSITION_OPEN)
                .order_by(desc(TradeEvent.actual_entry_time))
            )
            events = result.scalars().all()

            return [_to_public_event(e) for e in events]

    except Exception as e:
        logger.error(f"Error in get_current_positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending_confirm", response_model=List[EventPublic])
async def get_pending_confirmations():
    """
    获取待确认事件列表

    Returns:
        List[EventPublic] 待确认事件列表
    """
    try:
        async with get_db_context() as db:
            from sqlalchemy import select, desc

            result = await db.execute(
                select(TradeEvent)
                .where(TradeEvent.current_status == EventStatus.PENDING_CONFIRM)
                .order_by(desc(TradeEvent.created_at))
            )
            events = result.scalars().all()

            return [_to_public_event(e) for e in events]

    except Exception as e:
        logger.error(f"Error in get_pending_confirmations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent/{limit}", response_model=List[EventPublic])
async def get_recent_events(limit: int = 10):
    """
    获取最近的事件（所有状态）

    Args:
        limit: 返回数量 (默认10, 最大50)

    Returns:
        List[EventPublic] 最近事件列表
    """
    try:
        limit = min(limit, 50)

        async with get_db_context() as db:
            from sqlalchemy import select, desc

            result = await db.execute(
                select(TradeEvent)
                .order_by(desc(TradeEvent.created_at))
                .limit(limit)
            )
            events = result.scalars().all()

            return [_to_public_event(e) for e in events]

    except Exception as e:
        logger.error(f"Error in get_recent_events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "service": "ai-tradebot-public-api",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }
