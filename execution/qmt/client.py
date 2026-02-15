"""
AI TradeBot - QMT Client Module

QMT Trading Client with simulation mode support
"""
import os
import time
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel

from shared.logging import get_logger


logger = get_logger(__name__)


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass
class AccountInfo:
    total_assets: float = 0.0
    available_cash: float = 0.0
    market_value: float = 0.0
    frozen_cash: float = 0.0
    position_profit: float = 0.0
    balance_profit: float = 0.0


@dataclass
class Position:
    symbol: str = ""
    symbol_name: str = ""
    quantity: int = 0
    available: int = 0
    cost_price: float = 0.0
    current_price: float = 0.0
    market_value: float = 0.0
    profit_loss: float = 0.0
    profit_loss_ratio: float = 0.0


@dataclass
class Order:
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.LIMIT
    quantity: int = 0
    price: float = 0.0
    filled_quantity: int = 0
    filled_amount: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    message: str = ""
    create_time: datetime = None
    update_time: datetime = None


class QMTClient:
    """QMT Trading Client

    Supports both real trading (with xtquant) and simulation mode
    """

    def __init__(
        self,
        qmt_path: Optional[str] = None,
        session_id: Optional[int] = None,
        simulation_mode: bool = True,
    ):
        qmt_default = os.path.join("C:", "QMT", "userdata_mini").replace("\\", "\\\\")
        self.qmt_path = qmt_path or os.getenv("QMT_PATH", qmt_default)
        self.session_id = session_id or int(os.getenv("QMT_SESSION_ID", "0"))
        self.simulation_mode = simulation_mode or os.getenv("SIMULATION_MODE", "true").lower() == "true"

        self._connected = False
        self._xt_trader = None

        logger.info(
            f"QMT Client: simulation={self.simulation_mode}, path={self.qmt_path}"
        )

        if not self.simulation_mode:
            self._init_real_trading()

    def _init_real_trading(self) -> None:
        try:
            import sys
            xt_path = os.path.join(self.qmt_path, "PyModules")
            if os.path.exists(xt_path):
                sys.path.insert(0, xt_path)

            from xtquant import xttrader
            self._xt_trader = xttrader
            logger.info("xtquant loaded, real trading enabled")

        except ImportError as e:
            logger.warning(f"xtquant import failed: {e}, switching to simulation")
            self.simulation_mode = True

    async def connect(self) -> bool:
        if self.simulation_mode:
            logger.info("[Simulation] Connected to QMT simulator")
            self._connected = True
            return True

        try:
            if self._xt_trader:
                result = self._xt_trader.connect(
                    path=self.qmt_path,
                    session_id=self.session_id,
                )
                self._connected = result == 0
                if self._connected:
                    logger.info(f"QMT connected: session={self.session_id}")
                else:
                    logger.error(f"QMT connection failed: {result}")
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

        return self._connected

    async def disconnect(self) -> None:
        if not self._connected:
            return

        if self.simulation_mode:
            logger.info("[Simulation] Disconnected from QMT")
        else:
            try:
                if self._xt_trader:
                    self._xt_trader.disconnect()
                logger.info("Disconnected from QMT")
            except Exception as e:
                logger.error(f"Disconnect error: {e}")

        self._connected = False

    async def get_account_info(self) -> Optional[AccountInfo]:
        if not self._connected:
            await self.connect()

        if self.simulation_mode:
            return AccountInfo(
                total_assets=1000000.0,
                available_cash=500000.0,
                market_value=500000.0,
                frozen_cash=0.0,
                position_profit=50000.0,
                balance_profit=0.0,
            )

        try:
            if self._xt_trader:
                data = self._xt_trader.query_stock_account(self.session_id)
                if data:
                    return AccountInfo(
                        total_assets=data.get("total_assets", 0.0),
                        available_cash=data.get("cash", 0.0),
                        market_value=data.get("market_value", 0.0),
                        frozen_cash=data.get("frozen_cash", 0.0),
                        position_profit=data.get("position_profit", 0.0),
                        balance_profit=data.get("balance_profit", 0.0),
                    )
        except Exception as e:
            logger.error(f"Query account error: {e}")

        return None

    async def get_positions(self) -> List[Position]:
        if not self._connected:
            await self.connect()

        if self.simulation_mode:
            return [
                Position(
                    symbol="600000.SH",
                    symbol_name="浦发银行",
                    quantity=1000,
                    available=1000,
                    cost_price=10.00,
                    current_price=10.50,
                    market_value=10500.0,
                    profit_loss=500.0,
                    profit_loss_ratio=0.05,
                )
            ]

        positions = []
        try:
            if self._xt_trader:
                data = self._xt_trader.query_stock_positions(self.session_id)
                if data:
                    for item in data:
                        pos = Position(
                            symbol=item.get("stock_code", ""),
                            symbol_name=item.get("stock_name", ""),
                            quantity=int(item.get("volume", 0)),
                            available=int(item.get("can_use_volume", 0)),
                            cost_price=float(item.get("open_price", 0)),
                            current_price=float(item.get("last_price", 0)),
                            market_value=float(item.get("market_value", 0)),
                            profit_loss=float(item.get("profit_loss", 0)),
                            profit_loss_ratio=float(item.get("profit_ratio", 0)),
                        )
                        positions.append(pos)
        except Exception as e:
            logger.error(f"Query positions error: {e}")

        return positions

    async def execute_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: int,
        price: Optional[float] = None,
    ) -> Order:
        order = Order(
            order_id=f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price or 0.0,
            create_time=datetime.now(),
        )

        if self.simulation_mode:
            logger.info(
                f"[MOCK ORDER] {side.value} {symbol} "
                f"{quantity} shares @ {price or 'MARKET'}"
            )
            order.status = OrderStatus.FILLED
            order.filled_quantity = quantity
            order.filled_amount = quantity * (price or 10.0)
            order.message = "Simulation filled"
            order.update_time = datetime.now()
        else:
            try:
                if self._xt_trader:
                    if order_type == OrderType.MARKET:
                        result = self._xt_trader.download_security_stock(
                            session=self.session_id,
                            stock_code=symbol,
                            amount=quantity,
                            price_type=0 if side == OrderSide.BUY else 1,
                            order_type=24,
                            price=0,
                        )
                    else:
                        if price is None:
                            order.status = OrderStatus.ERROR
                            order.message = "Limit order requires price"
                            return order

                        result = self._xt_trader.download_security_stock(
                            session=self.session_id,
                            stock_code=symbol,
                            amount=quantity,
                            price_type=0 if side == OrderSide.BUY else 1,
                            order_type=23,
                            price=price,
                        )

                    if result == 0:
                        order.status = OrderStatus.SUBMITTED
                        order.message = "Order submitted"
                    else:
                        order.status = OrderStatus.ERROR
                        order.message = f"Order failed: code={result}"

                    order.update_time = datetime.now()

            except Exception as e:
                order.status = OrderStatus.ERROR
                order.message = f"Order error: {str(e)}"
                logger.error(f"Execution error: {e}")

        return order

    async def cancel_order(self, order_id: str) -> bool:
        if self.simulation_mode:
            logger.info(f"[MOCK CANCEL] {order_id}")
            return True

        try:
            if self._xt_trader:
                result = self._xt_trader.cancel_order(
                    session=self.session_id,
                    order_id=order_id,
                )
                return result == 0
        except Exception as e:
            logger.error(f"Cancel error: {e}")

        return False

    async def get_orders(self) -> List[Order]:
        if self.simulation_mode:
            return []

        orders = []
        try:
            if self._xt_trader:
                data = self._xt_trader.query_stock_orders(self.session_id)
                if data:
                    for item in data:
                        order = Order(
                            order_id=item.get("order_id", ""),
                            symbol=item.get("stock_code", ""),
                            side=OrderSide.BUY if item.get("order_type", "") == "买入" else OrderSide.SELL,
                            quantity=int(item.get("order_volume", 0)),
                            price=float(item.get("order_price", 0)),
                            filled_quantity=int(item.get("filled_volume", 0)),
                            filled_amount=float(item.get("filled_amount", 0)),
                            status=self._convert_status(item.get("order_status", "")),
                            message=item.get("status_msg", ""),
                            create_time=datetime.fromtimestamp(item.get("order_time", 0)),
                            update_time=datetime.now(),
                        )
                        orders.append(order)
        except Exception as e:
            logger.error(f"Query orders error: {e}")

        return orders

    def _convert_status(self, status: str) -> OrderStatus:
        status_map = {
            "待报": OrderStatus.PENDING,
            "已报": OrderStatus.SUBMITTED,
            "部成": OrderStatus.PARTIAL_FILLED,
            "已成": OrderStatus.FILLED,
            "已撤": OrderStatus.CANCELLED,
            "废单": OrderStatus.REJECTED,
        }
        return status_map.get(status, OrderStatus.ERROR)

    @property
    def is_connected(self) -> bool:
        return self._connected
