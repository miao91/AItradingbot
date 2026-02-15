"""
AI TradeBot - 交易事件 ORM 模型
体现"以终为始"哲学：从买入起即预设完整退出逻辑
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from sqlalchemy import String, DateTime, Float, Integer, Text, JSON, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pydantic import BaseModel, Field


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


class EventStatus(str, Enum):
    """事件状态枚举 - 体现完整生命周期"""
    OBSERVING = "observing"           # 观察中 - 已发现机会，尚未入场
    PENDING_CONFIRM = "pending_confirm" # 待确认 - AI已出信号，等待人工确认下单
    POSITION_OPEN = "position_open"   # 持仓中 - 已执行买入
    TAKE_PROFIT = "take_profit"       # 已成功 - 止盈退出
    STOPPED_OUT = "stopped_out"       # 已止损 - 触发止损
    LOGIC_EXPIRED = "logic_expired"   # 逻辑失效 - 超过预设时效
    MANUAL_CLOSE = "manual_close"     # 手动关停 - 人工干预
    REJECTED = "rejected"             # 已拒绝 - 风控未通过


class Direction(str, Enum):
    """交易方向"""
    LONG = "long"     # 做多
    SHORT = "short"   # 做空


class ExitPlan(BaseModel):
    """
    退出计划 - "以终为始"核心模型
    在买入时刻即预设清晰的退出逻辑
    """
    take_profit: Optional[Dict[str, Any]] = Field(
        default=None,
        description="止盈计划: {price: float, logic: str, confidence: float}"
    )
    stop_loss: Optional[Dict[str, Any]] = Field(
        default=None,
        description="止损计划: {price: float, logic: str, falsification_point: str}"
    )
    expiration: Optional[Dict[str, Any]] = Field(
        default=None,
        description="时效计划: {expire_time: datetime, logic: str, event_end: str}"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "take_profit": {
                    "price": 12.50,
                    "logic": "基于估值修复预期，目标市盈率回归至15倍",
                    "confidence": 0.75
                },
                "stop_loss": {
                    "price": 11.20,
                    "logic": "逻辑证伪线：若跌破此价格则利好消息已消化",
                    "falsification_point": "支撑位跌破"
                },
                "expiration": {
                    "expire_time": "2025-03-31T15:00:00",
                    "logic": "年报落地时间窗口，预期3个月见效",
                    "event_end": "2025年Q1财报发布"
                }
            }
        }


class EntryPlan(BaseModel):
    """入场计划"""
    trigger_price: Optional[float] = Field(
        default=None,
        description="触发价格"
    )
    limit_price: Optional[float] = Field(
        default=None,
        description="限价价格（限价单使用）"
    )
    entry_condition: str = Field(
        ...,
        description="入场条件描述"
    )
    quantity: int = Field(
        ...,
        gt=0,
        description="计划买入数量"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "trigger_price": 11.50,
                "limit_price": 11.55,
                "entry_condition": "回踩至5日均线附近且成交量放大",
                "quantity": 1000
            }
        }


class AIReasoning(BaseModel):
    """AI 推理记录"""
    model: str = Field(..., description="AI 模型名称")
    timestamp: datetime = Field(default_factory=datetime.now)
    prompt: Optional[str] = Field(default=None, description="输入提示词")
    input_data: Optional[Dict[str, Any]] = Field(default=None, description="输入数据")
    raw_output: str = Field(..., description="原始输出")
    parsed_result: Optional[Dict[str, Any]] = Field(default=None, description="解析后的结果")
    duration_ms: Optional[float] = Field(default=None, description="耗时（毫秒）")
    success: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None)


class TradeEvent(Base):
    """
    交易事件表 - 核心数据模型
    体现"以终为始"：从事件发现到退出的完整生命周期
    """
    __tablename__ = "trade_events"

    # ==================== 主键与基础信息 ====================
    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        comment="事件唯一标识，格式: TEV_YYYYMMDD_序号"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
        comment="事件创建时间"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="最后更新时间"
    )

    # ==================== 标的与方向 ====================
    ticker: Mapped[str] = mapped_column(
        String(20),
        index=True,
        comment="股票代码，如: 600000.SH"
    )

    ticker_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        default=None,
        comment="股票名称"
    )

    direction: Mapped[Direction] = mapped_column(
        String(10),
        default=Direction.LONG,
        comment="交易方向: long/short"
    )

    # ==================== 当前状态 ====================
    current_status: Mapped[EventStatus] = mapped_column(
        String(20),
        default=EventStatus.OBSERVING,
        index=True,
        comment="当前事件状态"
    )

    # ==================== 入场计划 ====================
    entry_plan: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        comment="入场计划 (JSON格式)"
    )

    actual_entry_price: Mapped[Optional[float]] = mapped_column(
        Float,
        default=None,
        comment="实际入场价格"
    )

    actual_entry_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=None,
        comment="实际入场时间"
    )

    actual_quantity: Mapped[Optional[int]] = mapped_column(
        Integer,
        default=None,
        comment="实际买入数量"
    )

    # ==================== 退出计划 (核心) ====================
    exit_plan: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        comment="退出计划 (JSON格式) - 包含止盈、止损、失效时间"
    )

    # 退出执行记录
    actual_exit_price: Mapped[Optional[float]] = mapped_column(
        Float,
        default=None,
        comment="实际退出价格"
    )

    actual_exit_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=None,
        comment="实际退出时间"
    )

    exit_reason: Mapped[Optional[str]] = mapped_column(
        String(200),
        default=None,
        comment="退出原因: take_profit/stop_loss/expired/manual"
    )

    # ==================== 盈亏统计 ====================
    realized_pnl: Mapped[Optional[float]] = mapped_column(
        Float,
        default=None,
        comment="已实现盈亏（绝对值）"
    )

    realized_pnl_ratio: Mapped[Optional[float]] = mapped_column(
        Float,
        default=None,
        comment="已实现盈亏比例（百分比）"
    )

    max_profit: Mapped[Optional[float]] = mapped_column(
        Float,
        default=None,
        comment="期间最大浮盈"
    )

    max_loss: Mapped[Optional[float]] = mapped_column(
        Float,
        default=None,
        comment="期间最大浮亏"
    )

    # ==================== AI 推理链路 ====================
    reasoning_log: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        comment="AI完整推演逻辑（可追溯）"
    )

    # 简化的核心逻辑摘要
    logic_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        default=None,
        comment="交易逻辑摘要"
    )

    # 触发事件描述
    event_description: Mapped[str] = mapped_column(
        Text,
        comment="触发事件的具体描述"
    )

    # AI 参与模型列表
    ai_participants: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        comment="参与决策的AI模型列表"
    )

    # 置信度
    confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        default=None,
        comment="决策置信度 (0-1)"
    )

    # ==================== 数据源信息 ====================
    source_type: Mapped[str] = mapped_column(
        String(50),
        comment="数据源类型: openclaw/tavily/tushare/manual"
    )

    source_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        default=None,
        comment="原始数据URL（如果有）"
    )

    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=None,
        comment="原始数据备份"
    )

    # ==================== 风控信息 ====================
    risk_check_passed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="风控检查是否通过"
    )

    risk_check_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        default=None,
        comment="风控检查详情"
    )

    # ==================== 执行信息 ====================
    order_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        default=None,
        index=True,
        comment="关联的订单ID"
    )

    # ==================== 复盘标记 ====================
    reviewed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否已复盘"
    )

    review_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        default=None,
        comment="复盘笔记"
    )

    # ==================== 标签与分类 ====================
    tags: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        comment="事件标签"
    )

    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        default=None,
        comment="事件分类: announcement/news/policy/earnings等"
    )

    def __repr__(self) -> str:
        return (
            f"<TradeEvent(id={self.id}, ticker={self.ticker}, "
            f"status={self.current_status}, direction={self.direction})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "ticker": self.ticker,
            "ticker_name": self.ticker_name,
            "direction": self.direction,
            "current_status": self.current_status,
            "entry_plan": self.entry_plan,
            "exit_plan": self.exit_plan,
            "logic_summary": self.logic_summary,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "actual_entry_price": self.actual_entry_price,
            "actual_exit_price": self.actual_exit_price,
            "realized_pnl": self.realized_pnl,
            "realized_pnl_ratio": self.realized_pnl_ratio,
        }

    def is_position_open(self) -> bool:
        """是否已开仓"""
        return self.current_status == EventStatus.POSITION_OPEN

    def is_closed(self) -> bool:
        """是否已平仓"""
        return self.current_status in {
            EventStatus.TAKE_PROFIT,
            EventStatus.STOPPED_OUT,
            EventStatus.LOGIC_EXPIRED,
            EventStatus.MANUAL_CLOSE,
        }

    def should_exit(self, current_price: float, current_time: datetime) -> Optional[str]:
        """
        检查是否应该退出

        Args:
            current_price: 当前价格
            current_time: 当前时间

        Returns:
            退出原因或 None
        """
        if not self.is_position_open():
            return None

        exit_plan_dict = self.exit_plan
        if not exit_plan_dict:
            return None

        # 检查止盈
        if exit_plan_dict.get("take_profit"):
            tp_price = exit_plan_dict["take_profit"].get("price")
            if tp_price and current_price >= tp_price:
                return "take_profit"

        # 检查止损
        if exit_plan_dict.get("stop_loss"):
            sl_price = exit_plan_dict["stop_loss"].get("price")
            direction_check = current_price <= sl_price if self.direction == Direction.LONG else current_price >= sl_price
            if sl_price and direction_check:
                return "stop_loss"

        # 检查时效
        if exit_plan_dict.get("expiration"):
            expire_time_str = exit_plan_dict["expiration"].get("expire_time")
            if expire_time_str:
                try:
                    if isinstance(expire_time_str, str):
                        expire_time = datetime.fromisoformat(expire_time_str)
                    else:
                        expire_time = expire_time_str
                    if current_time > expire_time:
                        return "logic_expired"
                except (ValueError, TypeError):
                    pass

        return None
