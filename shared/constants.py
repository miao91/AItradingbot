"""
AI TradeBot - 常量定义
"""
from enum import Enum

# =============================================================================
# 项目信息
# =============================================================================
PROJECT_NAME = "AI_TradeBot"
VERSION = "1.0.0"

# =============================================================================
# 交易相关常量
# =============================================================================
class Side:
    """交易方向"""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


class OrderType:
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus:
    """订单状态"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide:
    """持仓方向"""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


# =============================================================================
# 事件类型
# =============================================================================
class EventType:
    """事件类型"""
    ANNOUNCEMENT = "announcement"       # 公告
    NEWS = "news"                       # 新闻
    POLICY = "policy"                   # 政策
    EARNINGS = "earnings"               # 财报
    DIVIDEND = "dividend"               # 分红
    RESTRUCTURING = "restructuring"     # 重组
    BLOCK_TRADE = "block_trade"         # 大宗交易
    OTHER = "other"


class EventSource:
    """事件来源"""
    TUSHARE = "tushare"
    AKSHARE = "akshare"
    OPENCLAW = "openclaw"
    TAVILY = "tavily"
    MANUAL = "manual"


class ExecutionMode(str, Enum):
    """执行模式"""
    AUTO = "auto"           # 全自动 - QMT 自动下单
    MANUAL = "manual"       # 手动 - 人工下单后回填
    SIMULATION = "simulation"  # 模拟 - 仅记录不执行


# =============================================================================
# 决策相关
# =============================================================================
class DecisionAction:
    """决策动作"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"
    SKIP = "SKIP"


class DecisionStatus:
    """决策状态"""
    PENDING = "pending"                 # 待处理
    APPROVED = "approved"               # 已批准
    REJECTED = "rejected"               # 已拒绝（风控）
    EXECUTED = "executed"               # 已执行
    EXPIRED = "expired"                 # 已过期


class ExitType:
    """退出类型"""
    TAKE_PROFIT = "take_profit"         # 止盈
    STOP_LOSS = "stop_loss"             # 止损
    EXPIRATION = "expiration"           # 到期失效
    MANUAL = "manual"                   # 手动
    REVERSAL = "reversal"               # 逻辑反转
    RISK_CONTROL = "risk_control"       # 风控强平


# =============================================================================
# 风控常量
# =============================================================================
class RiskLevel:
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class CircuitBreakStatus:
    """熔断状态"""
    NORMAL = "normal"
    TRIGGERED = "triggered"
    COOLDOWN = "cooldown"


# =============================================================================
# AI 模型
# =============================================================================
class AIModel:
    """AI 模型标识"""
    KIMI = "kimi"
    GLM4 = "glm4"
    MINIMAX = "minimax"
    TAVILY = "tavily"


# =============================================================================
# 时间相关
# =============================================================================
TIMEZONE = "Asia/Shanghai"

# 交易时段
MARKET_OPEN = "09:30"
MARKET_CLOSE = "15:00"
LUNCH_BREAK_START = "11:30"
LUNCH_BREAK_END = "13:00"

# =============================================================================
# 数据库
# =============================================================================
DEFAULT_DB_PATH = "data/database/aitradebot.db"

# =============================================================================
# 日志级别
# =============================================================================
class LogLevel:
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# =============================================================================
# API 响应码
# =============================================================================
class StatusCode:
    SUCCESS = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_ERROR = 500


# =============================================================================
# 消息队列
# =============================================================================
class MQEventType:
    """消息队列事件类型"""
    NEW_EVENT = "new_event"
    NEW_DECISION = "new_decision"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    EXIT_TRIGGERED = "exit_triggered"
    RISK_WARNING = "risk_warning"


# =============================================================================
# 配置默认值
# =============================================================================
DEFAULT_DECISION_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_MAX_POSITION_RATIO = 0.10
DEFAULT_MAX_DAILY_LOSS_RATIO = 0.03
DEFAULT_MIN_HOLDING_TIME_SECONDS = 60
