"""
AI TradeBot - 手动交易处理器

功能：
1. 处理手动回填逻辑
2. 记录真实成交价格
3. 触发退出规划器监控
"""
import asyncio
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from core.database.session import get_db_context
from storage.models.trade_event import TradeEvent, EventStatus
from decision.engine.exit_planner import get_exit_planner, start_exit_monitoring
from shared.logging import get_logger


logger = get_logger(__name__)


class ManualExecutionRequest(BaseModel):
    """手动执行请求"""
    event_id: str = Field(..., description="事件ID")
    actual_price: float = Field(..., gt=0, description="实际成交价格")
    actual_quantity: int = Field(..., gt=0, description="实际成交数量")
    execution_time: Optional[datetime] = None
    notes: str = ""


class ManualExecutionResult(BaseModel):
    """手动执行结果"""
    success: bool
    event_id: str
    old_status: EventStatus
    new_status: EventStatus
    message: str
    exit_monitoring_started: bool = False


class ManualTradeHandler:
    """
    手动交易处理器

    负责：
    1. 验证回填请求
    2. 更新事件状态
    3. 启动退出监控
    """

    def __init__(self):
        """初始化处理器"""
        self._pending_confirmations = set()  # 防止重复确认
        logger.info("手动交易处理器初始化完成")

    async def confirm_manual_execution(
        self,
        event_id: str,
        actual_price: float,
        actual_quantity: int,
        execution_time: Optional[datetime] = None,
        notes: str = "",
    ) -> ManualExecutionResult:
        """
        确认手动执行（人工回填）

        Args:
            event_id: 事件 ID
            actual_price: 实际成交价格
            actual_quantity: 实际成交数量
            execution_time: 成交时间
            notes: 备注

        Returns:
            ManualExecutionResult 执行结果
        """
        logger.info(f"收到手动执行确认: {event_id}")

        # 防止重复确认
        if event_id in self._pending_confirmations:
            return ManualExecutionResult(
                success=False,
                event_id=event_id,
                old_status=EventStatus.OBSERVING,
                new_status=EventStatus.OBSERVING,
                message="该事件正在处理中，请勿重复确认"
            )

        try:
            async with get_db_context() as db:
                from sqlalchemy import select

                # 查询事件
                result = await db.execute(
                    select(TradeEvent).where(TradeEvent.id == event_id)
                )
                event = result.scalar_one_or_none()

                if not event:
                    return ManualExecutionResult(
                        success=False,
                        event_id=event_id,
                        old_status=EventStatus.OBSERVING,
                        new_status=EventStatus.OBSERVING,
                        message=f"事件不存在: {event_id}"
                    )

                old_status = event.current_status

                # 检查当前状态是否可以手动确认
                if event.current_status not in [
                    EventStatus.OBSERVING,
                    EventStatus.PENDING_CONFIRM,
                ]:
                    return ManualExecutionResult(
                        success=False,
                        event_id=event_id,
                        old_status=old_status,
                        new_status=event.current_status,
                        message=f"当前状态 {event.current_status} 不支持手动确认"
                    )

                # 更新事件为持仓中
                event.current_status = EventStatus.POSITION_OPEN
                event.actual_entry_price = actual_price
                event.actual_quantity = actual_quantity
                event.actual_entry_time = execution_time or datetime.now()

                # 如果有备注，添加到日志
                if notes:
                    if not event.reasoning_log:
                        event.reasoning_log = []
                    event.reasoning_log.append({
                        "step": "manual_execution",
                        "timestamp": datetime.now().isoformat(),
                        "actual_price": actual_price,
                        "actual_quantity": actual_quantity,
                        "notes": notes,
                    })

                await db.commit()

                logger.info(
                    f"事件 {event_id} 已确认为持仓: "
                    f"@{actual_price} x {actual_quantity}股"
                )

                # 启动退出规划器监控
                try:
                    planner = get_exit_planner()
                    # 确保监控正在运行
                    if not planner.running:
                        await planner.start_monitoring()
                        exit_monitoring_started = True
                        logger.info(f"退出规划器已启动监控 {event_id}")
                    else:
                        exit_monitoring_started = True
                except Exception as e:
                    logger.error(f"启动退出监控失败: {e}")
                    exit_monitoring_started = False

                return ManualExecutionResult(
                    success=True,
                    event_id=event_id,
                    old_status=old_status,
                    new_status=EventStatus.POSITION_OPEN,
                    message=f"手动确认成功，已转为持仓状态",
                    exit_monitoring_started=exit_monitoring_started,
                )

        except Exception as e:
            logger.error(f"手动执行确认失败: {e}")
            return ManualExecutionResult(
                success=False,
                event_id=event_id,
                old_status=EventStatus.OBSERVING,
                new_status=EventStatus.OBSERVING,
                message=f"执行失败: {str(e)}"
            )

    async def cancel_pending_confirmation(self, event_id: str) -> bool:
        """
        取消待确认状态

        Args:
            event_id: 事件 ID

        Returns:
            是否成功
        """
        try:
            async with get_db_context() as db:
                from sqlalchemy import select

                result = await db.execute(
                    select(TradeEvent).where(TradeEvent.id == event_id)
                )
                event = result.scalar_one_or_none()

                if event and event.current_status == EventStatus.PENDING_CONFIRM:
                    # 取消确认，恢复为观察中
                    event.current_status = EventStatus.OBSERVING
                    await db.commit()

                    logger.info(f"事件 {event_id} 已取消确认，恢复为观察中")
                    return True

                return False

        except Exception as e:
            logger.error(f"取消确认失败: {e}")
            return False

    async def get_pending_confirmations(self) -> list:
        """
        获取所有待确认的事件

        Returns:
            待确认事件列表
        """
        try:
            async with get_db_context() as db:
                from sqlalchemy import select

                result = await db.execute(
                    select(TradeEvent).where(
                        TradeEvent.current_status == EventStatus.PENDING_CONFIRM
                    ).order_by(TradeEvent.created_at.desc())
                )
                events = result.scalars().all()

                return [
                    {
                        "event_id": e.id,
                        "ticker": e.ticker,
                        "ticker_name": e.ticker_name,
                        "created_at": e.created_at.isoformat(),
                        "entry_plan": e.entry_plan,
                        "exit_plan": e.exit_plan,
                        "logic_summary": e.logic_summary,
                    }
                    for e in events
                ]

        except Exception as e:
            logger.error(f"查询待确认事件失败: {e}")
            return []

    def mark_processing(self, event_id: str) -> None:
        """标记为处理中（防止重复）"""
        self._pending_confirmations.add(event_id)

    def mark_complete(self, event_id: str) -> None:
        """标记处理完成"""
        self._pending_confirmations.discard(event_id)


# =============================================================================
# 便捷函数
# =============================================================================

async def confirm_manual_trade(
    event_id: str,
    actual_price: float,
    actual_quantity: int,
    notes: str = "",
) -> ManualExecutionResult:
    """
    确认手动交易的便捷函数

    Args:
        event_id: 事件 ID
        actual_price: 实际成交价格
        actual_quantity: 实际成交数量
        notes: 备注

    Returns:
        ManualExecutionResult 执行结果
    """
    handler = ManualTradeHandler()
    return await handler.confirm_manual_execution(
        event_id=event_id,
        actual_price=actual_price,
        actual_quantity=actual_quantity,
        notes=notes,
    )


async def cancel_confirmation(event_id: str) -> bool:
    """取消待确认的便捷函数"""
    handler = ManualTradeHandler()
    return await handler.cancel_pending_confirmation(event_id)


async def get_pending_trades() -> list:
    """获取待确认交易的便捷函数"""
    handler = ManualTradeHandler()
    return await handler.get_pending_confirmations()
