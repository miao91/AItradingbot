"""
AI TradeBot - Public API v1 (Enhanced)

只读接口，供外部网站 www.myrwaai.com 调用
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from core.database.session import get_db_context
from storage.models.trade_event import TradeEvent
from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# Response Models (Enhanced)
# =============================================================================

class ExitPlanPublic(BaseModel):
    """退出计划（公开版）"""
    take_profit_price: Optional[float] = Field(None, description="止盈目标价")
    stop_loss_price: Optional[float] = Field(None, description="止损价格")
    logic_deadline: Optional[str] = Field(None, description="逻辑失效时间")
    target_return_ratio: Optional[float] = Field(None, description="目标收益率%")
    days_remaining: Optional[int] = Field(None, description="剩余天数")
    hours_remaining: Optional[int] = Field(None, description="剩余小时数")


class ReasoningCore(BaseModel):
    """智谱推演核心逻辑"""
    analysis_summary: Optional[str] = Field(None, description="分析摘要")
    key_points: List[str] = Field(default_factory=list, description="关键要点")
    risk_factors: List[str] = Field(default_factory=list, description="风险因素")


class EventSummary(BaseModel):
    """事件摘要（增强版）"""
    id: str
    ticker: str
    ticker_name: Optional[str] = None
    direction: str  # long/short
    current_status: str
    status_display: str = Field(..., description="用户友好的状态显示")

    # AI观点
    event_summary: Optional[str] = Field(None, description="事件摘要")
    reasoning_core: Optional[ReasoningCore] = Field(None, description="智谱推演核心")
    logic_summary: Optional[str] = None
    confidence: Optional[float] = None

    # 入场信息
    actual_entry_price: Optional[float] = None
    entry_price_display: Optional[str] = Field(None, description="入场价显示")

    # 退出目标
    target_price: Optional[float] = Field(None, description="目标价（止盈）")
    stop_loss: Optional[float] = Field(None, description="止损价")
    exit_plan: Optional[ExitPlanPublic] = None

    # 当前盈亏
    current_pnl_ratio: Optional[float] = None
    pnl_display: Optional[str] = Field(None, description="盈亏显示")
    distance_to_target_pct: Optional[float] = None  # 距离目标价百分比

    # 事件描述
    event_description: Optional[str] = None

    # AI参与者
    ai_participants: List[str] = []

    # 时间
    created_at: str
    created_display: str = Field(..., description="创建时间显示")
    logic_deadline: Optional[str] = Field(None, description="逻辑失效时间")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "TEV_20260211_120000",
                "ticker": "600519.SH",
                "ticker_name": "贵州茅台",
                "direction": "long",
                "current_status": "position_open",
                "status_display": "持仓待兑现",
                "event_summary": "白酒龙头业绩超预期",
                "reasoning_core": {
                    "analysis_summary": "估值修复空间打开",
                    "key_points": ["Q3财报超预期", "净利润增长25%"],
                    "risk_factors": ["宏观经济下行"]
                },
                "confidence": 0.78,
                "actual_entry_price": 1680.50,
                "entry_price_display": "¥1,680.50",
                "target_price": 1850.00,
                "stop_loss": 1600.00,
                "exit_plan": {
                    "take_profit_price": 1850.00,
                    "stop_loss_price": 1600.00,
                    "target_return_ratio": 10.09,
                    "days_remaining": 85
                },
                "distance_to_target_pct": 9.12,
                "pnl_display": "+2.35%",
                "created_display": "2天前",
                "logic_deadline": "2025-05-01T23:59:59"
            }
        }


class EventReasoning(BaseModel):
    """事件推理详情"""
    event_id: str
    ticker: str
    ticker_name: Optional[str] = None
    logic_summary: Optional[str] = None

    # AI推理链
    reasoning_log: List[Dict[str, Any]]

    # 完整入场计划
    entry_plan_full: Optional[Dict[str, Any]] = None

    # 完整退出计划
    exit_plan_full: Optional[Dict[str, Any]] = None

    # 风控检查
    risk_check_passed: bool
    risk_check_details: Optional[Dict[str, Any]] = None


class DashboardStats(BaseModel):
    """仪表板统计"""
    total_events: int
    observing_count: int
    pending_confirm_count: int
    position_open_count: int
    closed_count: int
    total_pnl_ratio: Optional[float] = None
    win_rate: Optional[float] = None


class ActiveEventsResponse(BaseModel):
    """活跃事件响应"""
    total: int
    events: List[EventSummary]
    stats: DashboardStats
    last_updated: str
    last_updated_display: str


# =============================================================================
# Router
# =============================================================================

router = APIRouter(
    prefix="/public",
    tags=["public"],
)


# =============================================================================
# Helper Functions
# =============================================================================

def _get_status_display(status) -> str:
    """获取用户友好的状态显示"""
    # 处理枚举或字符串
    status_value = status.value if hasattr(status, 'value') else status
    status_value = str(status_value) if status_value else ""

    status_map = {
        "observing": "逻辑验证中",
        "pending_confirm": "待人工确认",
        "position_open": "持仓待兑现",
        "take_profit": "已止盈",
        "stopped_out": "已止损",
        "logic_expired": "逻辑失效",
        "manual_close": "手动平仓",
        "rejected": "已拒绝"
    }
    return status_map.get(status_value, status_value)


def _safe_get_value(enum_or_str) -> str:
    """安全获取枚举值或字符串"""
    if hasattr(enum_or_str, 'value'):
        return enum_or_str.value
    return str(enum_or_str) if enum_or_str else ""


def _format_price(price: Optional[float]) -> Optional[str]:
    """格式化价格显示"""
    if price is None:
        return None
    return f"¥{price:,.2f}"


def _format_pnl(pnl_ratio: Optional[float]) -> Optional[str]:
    """格式化盈亏显示"""
    if pnl_ratio is None:
        return None
    return f"{pnl_ratio:+.2f}%"


def _format_created_time(created_at: str) -> str:
    """格式化创建时间显示"""
    try:
        dt = datetime.fromisoformat(created_at)
        now = datetime.now()
        delta = now - dt

        if delta.days > 0:
            return f"{delta.days}天前"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours}小时前"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes}分钟前"
        else:
            return "刚刚"
    except:
        return created_at[:10]


def _extract_reasoning_core(event: TradeEvent) -> Optional[ReasoningCore]:
    """从 reasoning_log 中提取智谱推演核心逻辑"""
    if not event.reasoning_log:
        return None

    # 查找智谱推演步骤
    glm_steps = [log for log in event.reasoning_log if log.get("step") == "glm4_reasoning"]

    if not glm_steps:
        return None

    step = glm_steps[0]
    data = step.get("data", {})

    return ReasoningCore(
        analysis_summary=data.get("reasoning", event.logic_summary),
        key_points=data.get("key_points", []),
        risk_factors=data.get("risk_factors", [])
    )


def _calculate_distance_to_target(event: TradeEvent) -> Optional[float]:
    """计算距离目标价的百分比"""
    if not event.actual_entry_price:
        return None

    exit_plan = event.exit_plan
    if not exit_plan:
        return None

    tp = exit_plan.get("take_profit", {}).get("price")
    if not tp:
        return None

    if _safe_get_value(event.direction) == "long":
        return (tp - event.actual_entry_price) / event.actual_entry_price * 100
    else:
        return (event.actual_entry_price - tp) / event.actual_entry_price * 100


def _calculate_time_remaining(event: TradeEvent) -> tuple[Optional[int], Optional[int]]:
    """计算剩余时间（天、小时）"""
    exit_plan = event.exit_plan
    if not exit_plan:
        return None, None

    expire_str = exit_plan.get("expiration", {}).get("expire_time")
    if not expire_str:
        return None, None

    try:
        if isinstance(expire_str, str):
            expire_time = datetime.fromisoformat(expire_str)
        else:
            expire_time = expire_str

        delta = expire_time - datetime.now()
        total_seconds = int(delta.total_seconds())

        if total_seconds <= 0:
            return 0, 0

        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600

        return max(0, days), max(0, hours)
    except (ValueError, TypeError):
        return None, None


def _to_event_summary(event: TradeEvent) -> EventSummary:
    """转换为事件摘要（增强版）"""

    # 计算剩余时间
    days_remaining, hours_remaining = _calculate_time_remaining(event)

    # 退出计划（公开版）
    exit_plan_public = None
    target_price = None
    stop_loss = None

    if event.exit_plan:
        target_price = event.exit_plan.get("take_profit", {}).get("price")
        stop_loss = event.exit_plan.get("stop_loss", {}).get("price")
        expire_str = event.exit_plan.get("expiration", {}).get("expire_time")

        # 计算目标收益率
        target_return_ratio = None
        if target_price and event.actual_entry_price:
            if _safe_get_value(event.direction) == "long":
                target_return = (target_price - event.actual_entry_price) / event.actual_entry_price * 100
            else:
                target_return = (event.actual_entry_price - target_price) / event.actual_entry_price * 100
            target_return_ratio = round(target_return, 2)

        exit_plan_public = ExitPlanPublic(
            take_profit_price=target_price,
            stop_loss_price=stop_loss,
            logic_deadline=expire_str,
            target_return_ratio=target_return_ratio,
            days_remaining=days_remaining,
            hours_remaining=hours_remaining
        )

    # 格式化入场价显示
    entry_display = _format_price(event.actual_entry_price) if event.actual_entry_price else None

    # 格式化盈亏显示
    pnl_display = _format_pnl(event.realized_pnl_ratio)

    # 逻辑失效时间
    logic_deadline = None
    if event.exit_plan:
        logic_deadline = event.exit_plan.get("expiration", {}).get("expire_time")

    return EventSummary(
        id=event.id,
        ticker=event.ticker,
        ticker_name=event.ticker_name,
        direction=_safe_get_value(event.direction),
        current_status=_safe_get_value(event.current_status),
        status_display=_get_status_display(event.current_status),
        event_summary=event.event_description or event.logic_summary,
        reasoning_core=_extract_reasoning_core(event),
        logic_summary=event.logic_summary,
        confidence=event.confidence,
        actual_entry_price=event.actual_entry_price,
        entry_price_display=entry_display,
        target_price=target_price,
        stop_loss=stop_loss,
        exit_plan=exit_plan_public,
        current_pnl_ratio=event.realized_pnl_ratio,
        pnl_display=pnl_display,
        distance_to_target_pct=round(_calculate_distance_to_target(event), 2) if _calculate_distance_to_target(event) else None,
        event_description=event.event_description,
        ai_participants=event.ai_participants or [],
        created_at=event.created_at.isoformat() if event.created_at else "",
        created_display=_format_created_time(event.created_at.isoformat() if event.created_at else ""),
        logic_deadline=logic_deadline
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/active_events", response_model=ActiveEventsResponse)
async def get_active_events(
    status: Optional[str] = None,
    limit: int = 50
):
    """
    获取活跃的交易事件（公开接口 - 增强版）

    返回用户友好的数据格式，适合网站展示

    Args:
        status: 过滤状态 (observing/pending_confirm/position_open)
        limit: 返回数量限制 (默认50, 最大100)

    Returns:
        ActiveEventsResponse 包含增强的事件列表和统计信息
    """
    try:
        limit = min(limit, 100)

        async with get_db_context() as db:
            from sqlalchemy import select, desc, func, case

            # 构建查询
            query = select(TradeEvent).order_by(desc(TradeEvent.created_at))

            # 状态过滤（只返回公开状态）
            allowed_statuses = ["observing", "pending_confirm", "position_open"]
            if status:
                if status in allowed_statuses:
                    query = query.where(TradeEvent.current_status == status)
                else:
                    raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
            else:
                query = query.where(TradeEvent.current_status.in_(allowed_statuses))

            query = query.limit(limit)

            result = await db.execute(query)
            events = result.scalars().all()

            # 转换为公开模型（增强版）
            summaries = [_to_event_summary(e) for e in events]

            # 统计数据
            stats_result = await db.execute(
                select(TradeEvent.current_status, func.count(TradeEvent.id))
                .group_by(TradeEvent.current_status)
            )
            status_counts = {_safe_get_value(row[0]): row[1] for row in stats_result.all()}

            # 计算胜率
            pnl_result = await db.execute(
                select(
                    func.avg(TradeEvent.realized_pnl_ratio),
                    func.count(TradeEvent.id).label("total_closed"),
                    func.sum(case((TradeEvent.realized_pnl_ratio > 0, 1), else_=0)).label("win_count")
                ).where(TradeEvent.current_status.in_([
                    "take_profit", "stopped_out", "logic_expired", "manual_close"
                ]))
            )
            pnl_row = pnl_result.one_or_none()

            total_pnl_ratio = None
            win_rate = None
            if pnl_row and pnl_row[1] and pnl_row[1] > 0:
                total_pnl_ratio = pnl_row[0]
                win_rate = (pnl_row[2] or 0) / pnl_row[1] * 100

            stats = DashboardStats(
                total_events=sum(status_counts.values()),
                observing_count=status_counts.get("observing", 0),
                pending_confirm_count=status_counts.get("pending_confirm", 0),
                position_open_count=status_counts.get("position_open", 0),
                closed_count=(
                    status_counts.get("take_profit", 0) +
                    status_counts.get("stopped_out", 0) +
                    status_counts.get("logic_expired", 0) +
                    status_counts.get("manual_close", 0)
                ),
                total_pnl_ratio=round(total_pnl_ratio, 2) if total_pnl_ratio else None,
                win_rate=round(win_rate, 2) if win_rate else None
            )

            now = datetime.now()
            return ActiveEventsResponse(
                total=len(summaries),
                events=summaries,
                stats=stats,
                last_updated=now.isoformat(),
                last_updated_display=f"最后更新: {_format_created_time(now.isoformat())}"
            )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error in get_active_events: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reasoning/{event_id}", response_model=EventReasoning)
async def get_event_reasoning(event_id: str):
    """
    获取事件的AI推理详情（公开接口）

    Args:
        event_id: 事件ID

    Returns:
        EventReasoning 推理详情
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

            return EventReasoning(
                event_id=event.id,
                ticker=event.ticker,
                ticker_name=event.ticker_name,
                logic_summary=event.logic_summary,
                reasoning_log=event.reasoning_log or [],
                entry_plan_full=event.entry_plan,
                exit_plan_full=event.exit_plan,
                risk_check_passed=event.risk_check_passed,
                risk_check_details=event.risk_check_details
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_event_reasoning: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    获取仪表板统计数据（公开接口）

    Returns:
        DashboardStats 统计信息
    """
    try:
        async with get_db_context() as db:
            from sqlalchemy import select, func, case

            # 统计各状态数量
            result = await db.execute(
                select(TradeEvent.current_status, func.count(TradeEvent.id))
                .group_by(TradeEvent.current_status)
            )
            status_counts = {_safe_get_value(row[0]): row[1] for row in result.all()}

            total_events = sum(status_counts.values())

            # 计算盈亏统计
            pnl_result = await db.execute(
                select(
                    func.avg(TradeEvent.realized_pnl_ratio),
                    func.count(TradeEvent.id).label("total_closed"),
                    func.sum(case((TradeEvent.realized_pnl_ratio > 0, 1), else_=0)).label("win_count")
                ).where(TradeEvent.current_status.in_([
                    "take_profit", "stopped_out", "logic_expired", "manual_close"
                ]))
            )
            pnl_row = pnl_result.one_or_none()

            total_pnl_ratio = None
            win_rate = None
            if pnl_row and pnl_row[1] and pnl_row[1] > 0:
                total_pnl_ratio = pnl_row[0]
                win_rate = (pnl_row[2] or 0) / pnl_row[1] * 100

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
                total_pnl_ratio=round(total_pnl_ratio, 2) if total_pnl_ratio else None,
                win_rate=round(win_rate, 2) if win_rate else None
            )

    except Exception as e:
        logger.error(f"Error in get_dashboard_stats: {e}")
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
