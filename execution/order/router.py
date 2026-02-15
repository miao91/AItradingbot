"""
AI TradeBot - 订单路由与风控

功能：
1. 硬风控检查（仓位、资金、频率限制）
2. 订单路由到 QMT 或手动确认流程
3. 持仓状态同步
4. EmergencyStop 紧急制动
5. 支持三种执行模式：AUTO / MANUAL / SIMULATION
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel

from core.database.session import get_db_context, db_manager
from storage.models.trade_event import TradeEvent, EventStatus, Direction
from execution.qmt.client import (
    QMTClient, OrderType, OrderSide, Order, AccountInfo, Position
)
from execution.order.manual_handler import ManualTradeHandler
from shared.logging import get_logger
from shared.constants import DEFAULT_DB_PATH, ExecutionMode


logger = get_logger(__name__)


class RiskCheckResult(BaseModel):
    """风控检查结果"""
    passed: bool
    reason: str = ""
    details: Dict[str, Any] = {}


class OrderSignal(BaseModel):
    """订单信号"""
    event_id: str
    ticker: str
    action: str  # BUY / SELL
    quantity: int
    price: Optional[float] = None
    order_type: str = "limit"  # market / limit
    reason: str = ""


class SafetyConfig(BaseModel):
    """安全配置（硬编码，不可配置修改）"""
    # 单笔限制
    MAX_SINGLE_ORDER_RATIO: float = 0.10  # 单笔不超过总资产10%
    MIN_ORDER_AMOUNT: float = 1000.0      # 最小单笔金额

    # 总仓位限制
    MAX_TOTAL_POSITION_RATIO: float = 0.70  # 总持仓不超过70%
    MAX_CASH_RESERVE_RATIO: float = 0.10    # 保留10%现金储备

    # 频率限制
    MAX_ORDERS_PER_DAY: int = 20
    MAX_ORDERS_PER_HOUR: int = 5

    # 熔断
    DAILY_LOSS_LIMIT_RATIO: float = 0.05     # 单日亏损5%熔断
    DAILY_DRAWDOWN_LIMIT: float = 50000.0    # 单日回撤5万

    # 持仓限制
    MAX_POSITIONS_COUNT: int = 10           # 最多持有10只股票
    MAX_SINGLE_STOCK_RATIO: float = 0.20    # 单只股票不超过20%


# 硬编码风控参数（不可通过配置修改）
SAFETY_CONFIG = SafetyConfig()


class OrderRouter:
    """
    订单路由器

    职责：
    1. 接收决策层信号
    2. 执行硬风控检查
    3. 根据 execution_mode 路由到：
       - AUTO: QMT 自动执行
       - MANUAL: 待人工确认流程
       - SIMULATION: 模拟执行
    4. 同步持仓状态
    """

    def __init__(
        self,
        qmt_client: Optional[QMTClient] = None,
        safety_config: Optional[SafetyConfig] = None,
        execution_mode: ExecutionMode = ExecutionMode.MANUAL,
    ):
        """
        初始化订单路由器

        Args:
            qmt_client: QMT 客户端
            safety_config: 安全配置
            execution_mode: 执行模式 (AUTO/MANUAL/SIMULATION)
        """
        self.qmt_client = qmt_client or QMTClient()
        self.safety_config = safety_config or SAFETY_CONFIG
        self.execution_mode = execution_mode
        self.manual_handler = ManualTradeHandler()

        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_running = False

        mode_name = {
            ExecutionMode.AUTO: "全自动",
            ExecutionMode.MANUAL: "手动确认",
            ExecutionMode.SIMULATION: "模拟",
        }
        logger.info(f"订单路由器初始化完成 - 模式: {mode_name.get(execution_mode, execution_mode)}")

    async def process_signal(self, signal: OrderSignal) -> RiskCheckResult:
        """
        处理交易信号

        Args:
            signal: 订单信号

        Returns:
            RiskCheckResult 风控检查结果
        """
        logger.info(f"收到交易信号: {signal.action} {signal.ticker} {signal.quantity}股")

        # ========== 硬风控检查 ==========
        check_result = await self._safety_check(signal)

        if not check_result.passed:
            logger.warning(f"风控检查未通过: {check_result.reason}")
            # 将事件标记为拒绝
            await self._mark_event_rejected(signal.event_id, check_result.reason)
            return check_result

        logger.info("风控检查通过")

        # ========== 根据执行模式处理 ==========
        if self.execution_mode == ExecutionMode.MANUAL:
            # 手动确认模式
            return await self._handle_manual_mode(signal)
        elif self.execution_mode == ExecutionMode.SIMULATION:
            # 模拟模式
            return await self._handle_simulation_mode(signal)
        else:
            # 自动模式
            return await self._handle_auto_mode(signal)

    async def _handle_manual_mode(self, signal: OrderSignal) -> RiskCheckResult:
        """
        处理手动确认模式

        不调用 QMT，仅设置状态为 PENDING_CONFIRM 并高亮打印提示
        """
        try:
            async with get_db_context() as db:
                from sqlalchemy import select

                result = await db.execute(
                    select(TradeEvent).where(TradeEvent.id == signal.event_id)
                )
                event = result.scalar_one_or_none()

                if not event:
                    return RiskCheckResult(
                        passed=False,
                        reason=f"事件不存在: {signal.event_id}",
                    )

                # 更新状态为待确认
                old_status = event.current_status
                event.current_status = EventStatus.PENDING_CONFIRM
                await db.commit()

                # 高亮打印提示信息（使用特殊字符增强可见性）
                price_str = f"{signal.price:.2f}" if signal.price else "市价"
                logger.info("=" * 60)
                logger.info(f"[信号待确认] 请在券商APP手动买入 {signal.ticker}")
                logger.info(f"[信号待确认] 建议价格: {price_str}")
                logger.info(f"[信号待确认] 建议数量: {signal.quantity}股")
                logger.info(f"[信号待确认] 事件ID: {signal.event_id}")
                logger.info(f"[信号待确认] 买入后请使用 manual_trade_flow.py 回填")
                logger.info("=" * 60)

                return RiskCheckResult(
                    passed=True,
                    reason="已进入待确认状态，等待人工回填",
                    details={
                        "mode": "manual",
                        "old_status": old_status,
                        "new_status": "pending_confirm",
                        "pending_action": "manual_buy",
                    },
                )

        except Exception as e:
            logger.error(f"手动模式处理失败: {e}")
            return RiskCheckResult(
                passed=False,
                reason=f"手动模式处理失败: {str(e)}",
            )

    async def _handle_simulation_mode(self, signal: OrderSignal) -> RiskCheckResult:
        """处理模拟模式"""
        logger.info("[模拟模式] 跳过真实下单")

        # 模拟执行订单
        order = await self._execute_order(signal)

        if order.status.value in ["filled", "submitted"]:
            logger.info(f"[模拟] 订单执行成功: {order.order_id}")
            await self._update_event_after_order(signal.event_id, order)
        else:
            logger.error(f"[模拟] 订单执行失败: {order.message}")

        return RiskCheckResult(
            passed=True,
            reason="模拟执行完成",
            details={"mode": "simulation"},
        )

    async def _handle_auto_mode(self, signal: OrderSignal) -> RiskCheckResult:
        """处理自动模式"""
        logger.info("[自动模式] 提交订单到 QMT...")

        order = await self._execute_order(signal)

        if order.status.value in ["filled", "submitted"]:
            logger.info(f"订单执行成功: {order.order_id}")
            await self._update_event_after_order(signal.event_id, order)
        else:
            logger.error(f"订单执行失败: {order.message}")

        return RiskCheckResult(
            passed=True,
            reason="订单已提交",
            details={"mode": "auto", "order_id": order.order_id},
        )

    async def _safety_check(self, signal: OrderSignal) -> RiskCheckResult:
        """
        硬风控检查

        Args:
            signal: 订单信号

        Returns:
            RiskCheckResult 检查结果
        """
        # 1. 连接 QMT 并获取账户信息
        await self.qmt_client.connect()
        account = await self.qmt_client.get_account_info()

        if not account:
            return RiskCheckResult(
                passed=False,
                reason="无法获取账户信息",
            )

        # 2. 单笔金额检查
        order_amount = signal.quantity * (signal.price or 10.0)  # 估算

        if order_amount < self.safety_config.MIN_ORDER_AMOUNT:
            return RiskCheckResult(
                passed=False,
                reason=f"单笔金额 {order_amount:.2f} 低于最小限制 {self.safety_config.MIN_ORDER_AMOUNT}",
                details={"order_amount": order_amount},
            )

        if order_amount > account.total_assets * self.safety_config.MAX_SINGLE_ORDER_RATIO:
            return RiskCheckResult(
                passed=False,
                reason=f"单笔金额 {order_amount:.2f} 超过总资产 {self.safety_config.MAX_SINGLE_ORDER_RATIO*100}% 限制",
                details={
                    "order_amount": order_amount,
                    "max_allowed": account.total_assets * self.safety_config.MAX_SINGLE_ORDER_RATIO,
                },
            )

        # 3. 现金储备检查
        if signal.action == "BUY":
            required_cash = order_amount * 1.001  # 考虑手续费
            available = account.available_cash

            min_reserve = account.total_assets * self.safety_config.MAX_CASH_RESERVE_RATIO
            usable_cash = available - min_reserve

            if required_cash > usable_cash:
                return RiskCheckResult(
                    passed=False,
                    reason=f"可用资金不足（需保留 {self.safety_config.MAX_CASH_RESERVE_RATIO*100}% 现金储备）",
                    details={
                        "required": required_cash,
                        "available": available,
                        "usable": usable_cash,
                    },
                )

        # 4. 总仓位检查
        positions = await self.qmt_client.get_positions()
        current_market_value = sum(p.market_value for p in positions)
        current_position_ratio = current_market_value / account.total_assets

        if signal.action == "BUY":
            new_market_value = current_market_value + order_amount
            new_ratio = new_market_value / account.total_assets

            if new_ratio > self.safety_config.MAX_TOTAL_POSITION_RATIO:
                return RiskCheckResult(
                    passed=False,
                    reason=f"总仓位将达到 {new_ratio*100:.1f}%，超过限制 {self.safety_config.MAX_TOTAL_POSITION_RATIO*100}%",
                    details={
                        "current_ratio": current_position_ratio,
                        "new_ratio": new_ratio,
                        "max_ratio": self.safety_config.MAX_TOTAL_POSITION_RATIO,
                    },
                )

        # 5. 持仓数量检查
        if len(positions) >= self.safety_config.MAX_POSITIONS_COUNT:
            # 检查是否已持有该股票
            has_position = any(p.symbol == signal.ticker for p in positions)
            if not has_position:
                return RiskCheckResult(
                    passed=False,
                    reason=f"持仓数量已达上限 {self.safety_config.MAX_POSITIONS_COUNT} 只",
                )

        # 6. 单只股票仓位检查
        if signal.action == "BUY":
            target_position = next((p for p in positions if p.symbol == signal.ticker), None)
            current_value = target_position.market_value if target_position else 0.0
            new_value = current_value + order_amount
            new_stock_ratio = new_value / account.total_assets

            if new_stock_ratio > self.safety_config.MAX_SINGLE_STOCK_RATIO:
                return RiskCheckResult(
                    passed=False,
                    reason=f"单只股票仓位将达到 {new_stock_ratio*100:.1f}%，超过限制 {self.safety_config.MAX_SINGLE_STOCK_RATIO*100}%",
                )

        # 7. 频率限制检查
        today_orders_count = await self._count_orders_today()
        if today_orders_count >= self.safety_config.MAX_ORDERS_PER_DAY:
            return RiskCheckResult(
                passed=False,
                reason=f"今日订单数已达上限 {self.safety_config.MAX_ORDERS_PER_DAY}",
            )

        # 所有检查通过
        return RiskCheckResult(
            passed=True,
            reason="风控检查通过",
            details={
                "order_amount": order_amount,
                "available_cash": account.available_cash,
                "position_ratio": current_position_ratio,
                "orders_today": today_orders_count,
            },
        )

    async def _execute_order(self, signal: OrderSignal) -> Order:
        """执行订单"""
        side = OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL
        order_type = OrderType.MARKET if signal.order_type == "market" else OrderType.LIMIT

        order = await self.qmt_client.execute_order(
            symbol=signal.ticker,
            side=side,
            order_type=order_type,
            quantity=signal.quantity,
            price=signal.price,
        )

        return order

    async def _mark_event_rejected(self, event_id: str, reason: str) -> None:
        """标记事件为已拒绝"""
        try:
            async with get_db_context() as db:
                from sqlalchemy import select, update

                result = await db.execute(
                    select(TradeEvent).where(TradeEvent.id == event_id)
                )
                event = result.scalar_one_or_none()

                if event:
                    event.current_status = EventStatus.REJECTED
                    # 记录风控拒绝原因
                    if not event.risk_check_details:
                        event.risk_check_details = {}
                    event.risk_check_details["rejection_reason"] = reason
                    event.risk_check_details["rejected_at"] = datetime.now().isoformat()

                    await db.commit()
                    logger.info(f"事件 {event_id} 已标记为拒绝: {reason}")

        except Exception as e:
            logger.error(f"标记事件拒绝失败: {e}")

    async def _update_event_after_order(self, event_id: str, order: Order) -> None:
        """订单执行后更新事件"""
        try:
            async with get_db_context() as db:
                from sqlalchemy import select

                result = await db.execute(
                    select(TradeEvent).where(TradeEvent.id == event_id)
                )
                event = result.scalar_one_or_none()

                if event:
                    event.order_id = order.order_id

                    if order.status.value == "filled":
                        # 全部成交
                        event.current_status = EventStatus.POSITION_OPEN
                        event.actual_entry_price = order.price
                        event.actual_entry_time = order.update_time or datetime.now()
                        event.actual_quantity = order.filled_quantity

                    elif order.status.value == "partial_filled":
                        # 部分成交
                        event.current_status = EventStatus.POSITION_OPEN
                        event.actual_entry_price = order.price
                        event.actual_entry_time = order.update_time or datetime.now()
                        event.actual_quantity = order.filled_quantity

                    await db.commit()
                    logger.info(f"事件 {event_id} 状态已更新")

        except Exception as e:
            logger.error(f"更新事件失败: {e}")

    async def _count_orders_today(self) -> int:
        """统计今日订单数"""
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())

        try:
            async with get_db_context() as db:
                from sqlalchemy import select

                result = await db.execute(
                    select(TradeEvent).where(
                        TradeEvent.actual_entry_time >= today_start,
                        TradeEvent.order_id.isnot(None),
                    )
                )
                return len(result.scalars().all())
        except:
            return 0

    async def start_monitoring(self, interval: int = 5) -> None:
        """
        启动持仓监控

        Args:
            interval: 同步间隔（秒）
        """
        if self._monitoring_running:
            logger.warning("持仓监控已在运行")
            return

        self._monitoring_running = True
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval)
        )

        logger.info(f"持仓监控已启动 (间隔: {interval}秒)")

    async def stop_monitoring(self) -> None:
        """停止持仓监控"""
        if not self._monitoring_running:
            return

        self._monitoring_running = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("持仓监控已停止")

    async def _monitoring_loop(self, interval: int) -> None:
        """持仓监控循环"""
        logger.info("进入持仓监控循环")

        while self._monitoring_running:
            try:
                await self._sync_positions()
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                logger.info("持仓监控循环被取消")
                break
            except Exception as e:
                logger.error(f"持仓监控出错: {e}")
                await asyncio.sleep(interval)

    async def _sync_positions(self) -> None:
        """同步持仓状态到数据库"""
        try:
            # 从 QMT 获取持仓
            positions = await self.qmt_client.get_positions()

            # 更新数据库中的持仓事件
            async with get_db_context() as db:
                from sqlalchemy import select

                # 查询所有持仓中的事件
                result = await db.execute(
                    select(TradeEvent).where(
                        TradeEvent.current_status == EventStatus.POSITION_OPEN
                    )
                )
                events = result.scalars().all()

                for event in events:
                    # 查找对应的持仓
                    position = next((p for p in positions if p.symbol == event.ticker), None)

                    if position:
                        # 更新实时数据
                        event.actual_entry_price = position.cost_price
                        event.realized_pnl = position.profit_loss
                        event.realized_pnl_ratio = position.profit_loss_ratio

                await db.commit()

            logger.debug(f"持仓同步完成: {len(positions)} 只股票")

        except Exception as e:
            logger.error(f"同步持仓失败: {e}")

    async def emergency_stop(self, reason: str = "手动触发") -> None:
        """
        紧急制动

        将所有在途事件设为手动干预状态
        """
        logger.warning(f"!!! 紧急制动触发: {reason} !!!")

        try:
            async with get_db_context() as db:
                from sqlalchemy import select, update

                # 更新所有观察中和持仓中的事件
                await db.execute(
                    update(TradeEvent)
                    .where(
                        TradeEvent.current_status.in_([
                            EventStatus.OBSERVING,
                            EventStatus.POSITION_OPEN,
                        ])
                    )
                    .values(current_status=EventStatus.MANUAL_CLOSE)
                )

                await db.commit()

            logger.warning("所有在途事件已标记为手动关闭")

        except Exception as e:
            logger.error(f"紧急制动执行失败: {e}")


# =============================================================================
# 便捷函数
# =============================================================================

async def process_decision_bundle(
    event_id: str,
    ticker: str,
    action: str,
    quantity: int,
    price: Optional[float] = None,
    execution_mode: ExecutionMode = ExecutionMode.MANUAL,
) -> RiskCheckResult:
    """
    处理决策包的便捷函数

    Args:
        event_id: 事件 ID
        ticker: 股票代码
        action: 动作 (BUY/SELL)
        quantity: 数量
        price: 价格
        execution_mode: 执行模式 (AUTO/MANUAL/SIMULATION)

    Returns:
        RiskCheckResult 风控检查结果
    """
    router = OrderRouter(execution_mode=execution_mode)

    signal = OrderSignal(
        event_id=event_id,
        ticker=ticker,
        action=action,
        quantity=quantity,
        price=price,
    )

    return await router.process_signal(signal)


async def emergency_stop(reason: str = "手动触发") -> None:
    """紧急停车的便捷函数"""
    router = OrderRouter()
    await router.emergency_stop(reason)
