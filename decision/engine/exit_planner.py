"""
AI TradeBot - 退出规划器

核心功能：
1. 监控所有持仓中的事件 (status='position_open')
2. 实时获取最新价格
3. 检查是否触发退出条件
4. 生成平仓信号
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, update
from pydantic import BaseModel

from core.database.session import get_db_context, db_manager
from storage.models.trade_event import TradeEvent, EventStatus, Direction
from perception.market_data import get_market_manager
from shared.logging import get_logger


logger = get_logger(__name__)


class ExitSignal(BaseModel):
    """退出信号"""
    event_id: str
    ticker: str
    exit_type: str  # take_profit, stop_loss, expiration, manual
    exit_price: float
    reason: str
    current_price: float
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_ratio: Optional[float] = None
    triggered_at: datetime


class ExitPlannerConfig(BaseModel):
    """退出规划器配置"""
    check_interval: int = 30  # 检查间隔（秒）
    market_check_timeout: int = 10  # 行情查询超时（秒）
    enable_auto_close: bool = False  # 是否自动平仓（默认false，只生成信号）


class ExitPlanner:
    """
    退出规划器

    "以终为始"的核心实现：
    - 从买入时刻起，持续监控是否到达预设的"终点"
    - 终点可能是：止盈、止损、逻辑失效
    """

    def __init__(self, config: Optional[ExitPlannerConfig] = None):
        """
        初始化退出规划器

        Args:
            config: 配置对象
        """
        self.config = config or ExitPlannerConfig()
        self.market_mgr = get_market_manager()
        self.running = False
        self.task: Optional[asyncio.Task] = None

        logger.info(
            f"退出规划器初始化: "
            f"检查间隔={self.config.check_interval}s, "
            f"自动平仓={self.config.enable_auto_close}"
        )

    async def check_positions(self) -> List[ExitSignal]:
        """
        检查所有持仓中的事件

        Returns:
            触发的退出信号列表
        """
        signals = []

        try:
            async with get_db_context() as db:
                # 查询所有持仓中的事件
                result = await db.execute(
                    select(TradeEvent).where(
                        TradeEvent.current_status == EventStatus.POSITION_OPEN
                    )
                )
                events = result.scalars().all()

                if not events:
                    logger.debug("没有持仓中的事件")
                    return signals

                logger.info(f"检查 {len(events)} 个持仓中的事件")

                for event in events:
                    signal = await self._check_single_position(event)
                    if signal:
                        signals.append(signal)

                        # 如果启用自动平仓
                        if self.config.enable_auto_close:
                            await self._execute_exit(db, event, signal)

            if signals:
                logger.info(f"触发 {len(signals)} 个退出信号")

        except Exception as e:
            logger.error(f"检查持仓失败: {e}")

        return signals

    async def _check_single_position(self, event: TradeEvent) -> Optional[ExitSignal]:
        """
        检查单个事件是否需要退出

        Args:
            event: 交易事件

        Returns:
            ExitSignal 如果需要退出，否则 None
        """
        try:
            # 获取实时价格
            current_price = await self.market_mgr.get_realtime_price(event.ticker)

            # 检查是否触发退出
            exit_reason = event.should_exit(current_price, datetime.now())

            if exit_reason:
                # 计算盈亏
                unrealized_pnl = None
                unrealized_pnl_ratio = None

                if event.actual_entry_price:
                    if event.direction == Direction.LONG:
                        unrealized_pnl = (current_price - event.actual_entry_price) * event.actual_quantity
                        unrealized_pnl_ratio = (current_price - event.actual_entry_price) / event.actual_entry_price
                    else:
                        unrealized_pnl = (event.actual_entry_price - current_price) * event.actual_quantity
                        unrealized_pnl_ratio = (event.actual_entry_price - current_price) / event.actual_entry_price

                signal = ExitSignal(
                    event_id=event.id,
                    ticker=event.ticker,
                    exit_type=exit_reason,
                    exit_price=current_price,
                    reason=self._get_exit_reason_description(event, exit_reason),
                    current_price=current_price,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_ratio=unrealized_pnl_ratio,
                    triggered_at=datetime.now(),
                )

                logger.info(
                    f"退出信号: {event.ticker} - {exit_reason} "
                    f"@{current_price:.2f} "
                    f"(盈亏: {unrealized_pnl_ratio*100 if unrealized_pnl_ratio else 0:+.2f}%)"
                )

                return signal

        except Exception as e:
            logger.error(f"检查事件 {event.id} 失败: {e}")

        return None

    def _get_exit_reason_description(self, event: TradeEvent, exit_type: str) -> str:
        """获取退出原因描述"""
        exit_plan = event.exit_plan

        if exit_type == "take_profit" and exit_plan.get("take_profit"):
            return exit_plan["take_profit"].get("logic", "止盈目标达成")
        elif exit_type == "stop_loss" and exit_plan.get("stop_loss"):
            return exit_plan["stop_loss"].get("logic", "止损线触发")
        elif exit_type == "logic_expired" and exit_plan.get("expiration"):
            return exit_plan["expiration"].get("logic", "逻辑时间窗口已过")

        return f"{exit_type} 触发"

    async def _execute_exit(
        self,
        db,
        event: TradeEvent,
        signal: ExitSignal,
    ) -> None:
        """
        执行退出（更新数据库状态）

        Args:
            db: 数据库会话
            event: 交易事件
            signal: 退出信号
        """
        try:
            # 更新事件状态
            status_map = {
                "take_profit": EventStatus.TAKE_PROFIT,
                "stop_loss": EventStatus.STOPPED_OUT,
                "logic_expired": EventStatus.LOGIC_EXPIRED,
                "manual": EventStatus.MANUAL_CLOSE,
            }

            new_status = status_map.get(signal.exit_type, EventStatus.MANUAL_CLOSE)

            event.current_status = new_status
            event.actual_exit_price = signal.exit_price
            event.actual_exit_time = signal.triggered_at
            event.exit_reason = signal.reason
            event.realized_pnl = signal.unrealized_pnl
            event.realized_pnl_ratio = signal.unrealized_pnl_ratio

            await db.commit()

            logger.info(f"已更新事件状态: {event.id} -> {new_status}")

        except Exception as e:
            logger.error(f"执行退出失败: {e}")
            await db.rollback()

    async def start_monitoring(self) -> None:
        """启动后台监控任务"""
        if self.running:
            logger.warning("监控任务已在运行")
            return

        self.running = True
        self.task = asyncio.create_task(self._monitoring_loop())

        logger.info("退出规划器监控已启动")

    async def stop_monitoring(self) -> None:
        """停止后台监控任务"""
        if not self.running:
            return

        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("退出规划器监控已停止")

    async def _monitoring_loop(self) -> None:
        """监控循环"""
        logger.info(f"进入监控循环 (间隔: {self.config.check_interval}s)")

        while self.running:
            try:
                await self.check_positions()
                await asyncio.sleep(self.config.check_interval)

            except asyncio.CancelledError:
                logger.info("监控循环被取消")
                break
            except Exception as e:
                logger.error(f"监控循环出错: {e}")
                await asyncio.sleep(self.config.check_interval)


# =============================================================================
# 全局实例
# =============================================================================

_exit_planner: Optional[ExitPlanner] = None


def get_exit_planner() -> ExitPlanner:
    """获取全局退出规划器实例"""
    global _exit_planner
    if _exit_planner is None:
        _exit_planner = ExitPlanner()
    return _exit_planner


# =============================================================================
# 便捷函数
# =============================================================================

async def check_all_positions() -> List[ExitSignal]:
    """检查所有持仓（便捷函数）"""
    planner = get_exit_planner()
    return await planner.check_positions()


async def start_exit_monitoring(
    check_interval: int = 30,
    enable_auto_close: bool = False,
) -> None:
    """
    启动退出监控（便捷函数）

    Args:
        check_interval: 检查间隔（秒）
        enable_auto_close: 是否自动平仓
    """
    planner = get_exit_planner()
    planner.config.check_interval = check_interval
    planner.config.enable_auto_close = enable_auto_close

    await planner.start_monitoring()


async def stop_exit_monitoring() -> None:
    """停止退出监控（便捷函数）"""
    planner = get_exit_planner()
    await planner.stop_monitoring()


# =============================================================================
# 独立脚本入口
# =============================================================================

async def run_once() -> None:
    """运行一次检查（用于手动触发）"""
    logger.info("=" * 60)
    logger.info("退出规划器 - 单次检查")
    logger.info("=" * 60)

    # 确保数据库已初始化
    await db_manager.initialize_engine()

    signals = await check_all_positions()

    if signals:
        logger.info("\n触发退出信号:")
        for signal in signals:
            logger.info(
                f"  - {signal.ticker}: {signal.exit_type} "
                f"@{signal.exit_price:.2f} "
                f"({signal.reason})"
            )
    else:
        logger.info("\n无需退出的持仓")

    logger.info("=" * 60)


async def run_forever() -> None:
    """持续运行监控"""
    logger.info("=" * 60)
    logger.info("退出规划器 - 持续监控模式")
    logger.info("=" * 60)

    # 确保数据库已初始化
    await db_manager.initialize_engine()

    await start_exit_monitoring(
        check_interval=30,
        enable_auto_close=False,
    )

    # 保持运行
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        await stop_exit_monitoring()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        # 守护进程模式
        asyncio.run(run_forever())
    else:
        # 单次检查模式
        asyncio.run(run_once())
