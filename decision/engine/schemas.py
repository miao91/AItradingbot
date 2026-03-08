"""
AI TradeBot - 强类型数据契约协议

定义 Agent 之间传递的严格数据结构，解决大模型输出 JSON 解析失败的痛点。

核心数据结构：
- AgentState: 状态机核心上下文
- StrategyHypothesis: 策略假设
- ReviewFeedback: 审查反馈
- LessonsLearned: 归因分析结果

作者: Matrix Agent
"""

import os
import sys
import ast
import re
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 枚举定义
# =============================================================================

class AgentStatus(Enum):
    """Agent 状态机状态"""
    INIT = "init"                       # 初始状态
    DRAFTING = "drafting"               # 生成中
    REVIEWING = "reviewing"             # 审查中
    TESTING = "testing"                 # 测试中
    PROCESSING = "processing"           # 处理中
    FAILED = "failed"                   # 失败
    SUCCESS = "success"                 # 成功
    COMPLETED = "completed"             # 完成
    CIRCUIT_BROKEN = "circuit_broken"   # 熔断


class TradingDirection(Enum):
    """交易方向"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class ErrorType(Enum):
    """错误类型"""
    NONE = "none"
    SYNTAX = "syntax"                   # 语法错误
    A_SHARE_RULE = "a_share_rule"       # A股规则违规
    LOGIC = "logic"                     # 逻辑错误
    SECURITY = "security"                # 安全问题
    TIMEOUT = "timeout"                 # 超时
    UNKNOWN = "unknown"                  # 未知错误


class PipelineStep(Enum):
    """流水线步骤"""
    HUNTING = "hunting"                 # 猎手阶段
    STRATEGIZING = "strategizing"       # 策略生成阶段
    RISK_REVIEW = "risk_review"         # 风险审查阶段
    JUDGING = "judging"                 # 裁判执行阶段
    ANALYZING = "analyzing"             # 分析阶段
    TERMINATED = "terminated"           # 终止
    # 别名 (Agent 使用)
    HUNTER = "hunting"
    STRATEGIST = "strategizing"
    RISK_OFFICER = "risk_review"
    JUDGE = "judging"
    ANALYST = "analyzing"


# =============================================================================
# 强类型数据模型 (Pydantic)
# =============================================================================

class SignalType(Enum):
    """信号类型"""
    ENTRY = "entry"       # 入场信号
    EXIT = "exit"         # 出场信号
    HOLD = "hold"         # 持有信号
    UNKNOWN = "unknown"   # 未知信号


class StrategyHypothesis(BaseModel):
    """
    策略假设

    包含市场洞察、交易方向和逻辑规则。
    """
    model_config = ConfigDict(strict=True)

    # 市场洞察
    market_insight: str = Field(
        default="",
        description="市场洞察描述，包含对当前市场状态的解读"
    )

    # 交易方向
    trading_direction: TradingDirection = Field(
        default=TradingDirection.HOLD,
        description="交易方向：买入/卖出/持有"
    )

    # 信号类型
    signal_type: SignalType = Field(
        default=SignalType.HOLD,
        description="信号类型：入场/出场/持有/未知"
    )

    # 逻辑规则列表
    logic_rules: List[str] = Field(
        default_factory=list,
        description="策略逻辑规则列表"
    )

    # 置信度 (0.0 - 1.0)
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="策略置信度"
    )

    # 原始代码 (可选)
    code_snippet: Optional[str] = Field(
        default=None,
        description="策略生成的代码片段"
    )

    # 策略代码 (可选) - 用于存储完整策略代码
    strategy_code: Optional[str] = Field(
        default=None,
        description="完整的策略代码"
    )

    # 风险评分 (1-10, 可选)
    risk_score: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="风险评分 (1-10)"
    )

    @field_validator("logic_rules", mode="before")
    @classmethod
    def parse_logic_rules(cls, v):
        """确保 logic_rules 是列表"""
        if isinstance(v, str):
            return [v]
        return v or []

    @field_validator("strategy_code", mode="before")
    @classmethod
    def validate_strategy_code(cls, v):
        """验证策略代码，允许字符串或None"""
        if v is None:
            return None
        if isinstance(v, str):
            return v
        # 如果是其他类型，转为字符串
        return str(v)

    @field_validator("risk_score", mode="before")
    @classmethod
    def validate_risk_score(cls, v):
        """验证风险评分，允许1-10的整数或None"""
        if v is None:
            return None
        if isinstance(v, int):
            return max(1, min(10, v))
        if isinstance(v, float):
            return max(1, min(10, int(v)))
        if isinstance(v, str):
            try:
                return max(1, min(10, int(float(v))))
            except ValueError:
                return None
        return None
    
    def to_prompt_string(self) -> str:
        """转换为提示字符串"""
        direction_map = {
            TradingDirection.BUY: "看多",
            TradingDirection.SELL: "看空",
            TradingDirection.HOLD: "观望"
        }

        signal_map = {
            SignalType.ENTRY: "入场",
            SignalType.EXIT: "出场",
            SignalType.HOLD: "持有",
            SignalType.UNKNOWN: "未知"
        }

        rules_str = "\n".join([f"- {r}" for r in self.logic_rules]) if self.logic_rules else "- 无"

        signal_str = signal_map.get(self.signal_type, "未知") if hasattr(self, 'signal_type') else "未知"
        risk_str = f"- 风险评分: {self.risk_score}/10\n" if self.risk_score else ""

        return f"""
【策略假设】
- 方向: {direction_map.get(self.trading_direction, '观望')}
- 信号类型: {signal_str}
- 置信度: {self.confidence:.1%}
- 市场洞察: {self.market_insight}
{risk_str}- 逻辑规则:
{rules_str}
"""


class ReviewFeedback(BaseModel):
    """
    审查反馈
    
    包含审查结果、错误类型和修复建议。
    """
    model_config = ConfigDict(strict=True)
    
    # 是否通过
    passed: bool = Field(
        default=False,
        description="是否通过审查"
    )
    
    # 错误类型
    error_type: ErrorType = Field(
        default=ErrorType.NONE,
        description="错误类型"
    )
    
    # 修复建议
    fix_suggestion: str = Field(
        default="",
        description="修复建议"
    )
    
    # 详细错误信息
    error_message: str = Field(
        default="",
        description="详细错误信息"
    )
    
    # 风险评分 (1-10)
    risk_score: int = Field(
        default=5,
        ge=1,
        le=10,
        description="风险评分"
    )
    
    # 审查时间
    reviewed_at: datetime = Field(
        default_factory=datetime.now,
        description="审查时间"
    )
    
    def to_prompt_string(self) -> str:
        """转换为提示字符串"""
        if self.passed:
            return "✅ 审查通过"
        
        error_type_map = {
            ErrorType.SYNTAX: "语法错误",
            ErrorType.A_SHARE_RULE: "A股规则违规",
            ErrorType.LOGIC: "逻辑错误",
            ErrorType.SECURITY: "安全问题",
            ErrorType.TIMEOUT: "超时",
            ErrorType.UNKNOWN: "未知错误",
        }
        
        return f"""
❌ 审查未通过
- 错误类型: {error_type_map.get(self.error_type, '未知')}
- 风险评分: {self.risk_score}/10
- 错误信息: {self.error_message}
- 修复建议: {self.fix_suggestion}
"""


class LessonsLearned(BaseModel):
    """
    归因分析结果
    
    包含失败原因和避免规则。
    """
    model_config = ConfigDict(strict=True)
    
    # 失败原因
    failure_reason: str = Field(
        default="",
        description="失败原因描述"
    )
    
    # 避免规则
    avoidance_rule: str = Field(
        default="",
        description="避免再次失败的规则"
    )
    
    # 改进建议
    improvement_suggestion: str = Field(
        default="",
        description="改进建议"
    )
    
    # 归因时间
    analyzed_at: datetime = Field(
        default_factory=datetime.now,
        description="归因分析时间"
    )
    
    # 关联的交易标的
    related_ticker: Optional[str] = Field(
        default=None,
        description="关联的股票代码"
    )
    
    def to_prompt_string(self) -> str:
        """转换为提示字符串"""
        return f"""
【归因分析】
- 失败原因: {self.failure_reason}
- 避免规则: {self.avoidance_rule}
- 改进建议: {self.improvement_suggestion}
"""


class StrategyCode(BaseModel):
    """
    策略代码

    包含生成的策略代码和相关参数。
    """
    model_config = ConfigDict(strict=True)

    # 代码内容
    code: str = Field(
        default="",
        description="策略代码"
    )

    # 止损价格
    stop_loss: float = Field(
        default=0.0,
        description="止损价格"
    )

    # 止盈价格
    take_profit: float = Field(
        default=0.0,
        description="止盈价格"
    )

    # 策略描述
    description: str = Field(
        default="",
        description="策略描述"
    )


class AgentState(BaseModel):
    """
    状态机核心上下文
    
    贯穿整个 Pipeline 的全局状态。
    """
    model_config = ConfigDict(strict=True)
    
    # 股票代码
    stock_code: str = Field(
        default="",
        description="股票代码，如 600519.SH"
    )
    
    # 交易日期
    trade_date: str = Field(
        default="",
        description="交易日期，如 20250220"
    )
    
    # 市场上下文文本 (从 Builder 获取)
    context_text: str = Field(
        default="",
        description="MarketContextBuilder 生成的文本描述"
    )
    
    # 当前策略假设
    current_hypothesis: Optional[StrategyHypothesis] = Field(
        default=None,
        description="当前策略假设"
    )
    
    # 当前代码
    current_code: str = Field(
        default="",
        description="当前生成的代码"
    )
    
    # 重试计数
    retry_count: int = Field(
        default=0,
        ge=0,
        description="重试次数"
    )
    
    # 当前状态
    status: AgentStatus = Field(
        default=AgentStatus.INIT,
        description="Agent 状态"
    )
    
    # 当前流水线步骤
    current_step: PipelineStep = Field(
        default=PipelineStep.HUNTING,
        description="当前流水线步骤"
    )
    
    # 审查历史
    review_history: List[ReviewFeedback] = Field(
        default_factory=list,
        description="审查历史记录"
    )
    
    # 执行日志
    execution_logs: List[str] = Field(
        default_factory=list,
        description="执行日志"
    )
    
    # 创建时间
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    
    # 最后更新时间
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="最后更新时间"
    )
    
    # 额外元数据
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="额外元数据"
    )

    # 市场上下文 (Orchestrator 使用)
    market_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="市场上下文数据"
    )

    # 当前执行的 Agent 名称
    current_agent: str = Field(
        default="",
        description="当前执行的 Agent 名称"
    )

    # 流水线日志
    pipeline_logs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="流水线执行日志"
    )

    # 审查反馈
    review_feedback: Optional["ReviewFeedback"] = Field(
        default=None,
        description="审查反馈"
    )

    # 目标股票信息 (Hunter 使用)
    target_stock: str = Field(
        default="",
        description="目标股票代码"
    )
    target_name: str = Field(
        default="",
        description="目标股票名称"
    )

    # 策略假设 (Hunter 生成)
    strategy_hypothesis: Optional["StrategyHypothesis"] = Field(
        default=None,
        description="策略假设"
    )
    hypothesis_generated: bool = Field(
        default=False,
        description="策略假设是否已生成"
    )

    # 策略代码 (Strategist 生成)
    strategy_code: Optional["StrategyCode"] = Field(
        default=None,
        description="策略代码"
    )
    code_generated: bool = Field(
        default=False,
        description="代码是否已生成"
    )
    code_reviewed: bool = Field(
        default=False,
        description="代码是否已审查"
    )

    # 回测结果 (Judge 生成)
    backtest_result: Optional["BacktestResult"] = Field(
        default=None,
        description="回测结果"
    )
    backtest_completed: bool = Field(
        default=False,
        description="回测是否完成"
    )

    # 归因分析 (Analyst 生成)
    lessons_learned: Optional["LessonsLearned"] = Field(
        default=None,
        description="归因分析结果"
    )
    analysis_completed: bool = Field(
        default=False,
        description="分析是否完成"
    )

    # 错误信息
    error_message: Optional[str] = Field(
        default=None,
        description="错误信息"
    )
    
    def add_log(self, message: str) -> None:
        """添加执行日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.execution_logs.append(log_entry)
        self.updated_at = datetime.now()
        logger.info(f"[AgentState] {log_entry}")
    
    def add_review(self, feedback: ReviewFeedback) -> None:
        """添加审查反馈"""
        self.review_history.append(feedback)
        self.updated_at = datetime.now()
    
    def increment_retry(self) -> None:
        """增加重试计数"""
        self.retry_count += 1
        self.updated_at = datetime.now()
    
    def reset_retry(self) -> None:
        """重置重试计数"""
        self.retry_count = 0
        self.updated_at = datetime.now()
    
    def to_summary(self) -> str:
        """转换为摘要字符串"""
        return f"""
【Agent 状态摘要】
- 标的: {self.stock_code}
- 日期: {self.trade_date}
- 状态: {self.status.value}
- 步骤: {self.current_step.value}
- 重试次数: {self.retry_count}
- 审查历史: {len(self.review_history)} 条
"""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stock_code": self.stock_code,
            "trade_date": self.trade_date,
            "status": self.status.value,
            "current_step": self.current_step.value,
            "retry_count": self.retry_count,
            "review_history_count": len(self.review_history),
            "execution_logs_count": len(self.execution_logs),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class BacktestResult(BaseModel):
    """
    回测结果
    
    来自 Judge (AShareSandbox) 的执行结果。
    """
    model_config = ConfigDict(strict=True)
    
    # 是否成功
    success: bool = Field(
        default=False,
        description="是否成功执行"
    )
    
    # 总收益率
    total_return: float = Field(
        default=0.0,
        description="总收益率"
    )
    
    # 夏普比率
    sharpe_ratio: float = Field(
        default=0.0,
        description="夏普比率"
    )
    
    # 最大回撤
    max_drawdown: float = Field(
        default=0.0,
        description="最大回撤"
    )
    
    # 胜率
    win_rate: float = Field(
        default=0.0,
        description="胜率"
    )
    
    # 交易次数
    total_trades: int = Field(
        default=0,
        description="总交易次数"
    )
    
    # 被阻断次数
    rejected_trades: int = Field(
        default=0,
        description="被阻断次数"
    )
    
    # 错误信息
    error_message: str = Field(
        default="",
        description="错误信息"
    )
    
    # 原始数据
    raw_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="原始回测数据"
    )
    
    def is_profitable(self) -> bool:
        """是否盈利"""
        return self.success and self.total_return > 0
    
    def to_prompt_string(self) -> str:
        """转换为提示字符串"""
        if not self.success:
            return f"❌ 回测失败: {self.error_message}"
        
        return f"""
【回测结果】
- 总收益率: {self.total_return:+.2%}
- 夏普比率: {self.sharpe_ratio:.2f}
- 最大回撤: {self.max_drawdown:.2%}
- 胜率: {self.win_rate:.1%}
- 交易次数: {self.total_trades}
- 被阻断: {self.rejected_trades}
"""


class BacktestMetrics(BaseModel):
    """
    回测指标
    
    详细的回测性能指标，用于策略评估。
    """
    model_config = ConfigDict(strict=True)
    
    # 年化收益率
    annual_return: float = Field(
        default=0.0,
        description="年化收益率"
    )
    
    # 夏普比率
    sharpe_ratio: float = Field(
        default=0.0,
        description="夏普比率"
    )
    
    # 卡尔玛比率
    calmar_ratio: float = Field(
        default=0.0,
        description="卡尔玛比率 (年化收益/最大回撤)"
    )
    
    # 最大回撤
    max_drawdown: float = Field(
        default=0.0,
        description="最大回撤"
    )
    
    # 最大回撤持续时间(天)
    max_drawdown_duration: int = Field(
        default=0,
        description="最大回撤持续天数"
    )
    
    # 胜率
    win_rate: float = Field(
        default=0.0,
        description="胜率"
    )
    
    # 盈亏比
    profit_loss_ratio: float = Field(
        default=0.0,
        description="盈亏比"
    )
    
    # 交易次数
    total_trades: int = Field(
        default=0,
        description="总交易次数"
    )
    
    # 盈利次数
    winning_trades: int = Field(
        default=0,
        description="盈利交易次数"
    )
    
    # 亏损次数
    losing_trades: int = Field(
        default=0,
        description="亏损交易次数"
    )
    
    # 平均持仓天数
    avg_holding_days: float = Field(
        default=0.0,
        description="平均持仓天数"
    )
    
    # 波动率
    volatility: float = Field(
        default=0.0,
        description="收益率波动率"
    )
    
    # 风险调整收益
    risk_adjusted_return: float = Field(
        default=0.0,
        description="风险调整收益"
    )
    
    def to_summary(self) -> str:
        """转换为摘要字符串"""
        return f"""
【回测指标】
- 年化收益: {self.annual_return:+.2%}
- 夏普比率: {self.sharpe_ratio:.2f}
- 卡尔玛比率: {self.calmar_ratio:.2f}
- 最大回撤: {self.max_drawdown:.2%}
- 胜率: {self.win_rate:.1%}
- 交易次数: {self.total_trades}
"""


# =============================================================================
# 便捷函数
# =============================================================================

def create_initial_state(
    stock_code: str,
    trade_date: str,
    context_text: str = ""
) -> AgentState:
    """
    创建初始状态
    
    Args:
        stock_code: 股票代码
        trade_date: 交易日期
        context_text: 市场上下文文本
        
    Returns:
        AgentState: 初始状态
    """
    return AgentState(
        stock_code=stock_code,
        trade_date=trade_date,
        context_text=context_text,
        status=AgentStatus.INIT,
        current_step=PipelineStep.HUNTING,
        retry_count=0,
        execution_logs=[f"状态机初始化: {stock_code} {trade_date}"]
    )


def parse_llm_json_response(
    response: str,
    expected_type: type[BaseModel]
) -> BaseModel:
    """
    解析 LLM 输出的 JSON 响应
    
    Args:
        response: LLM 原始响应
        expected_type: 期望的 Pydantic 类型
        
    Returns:
        解析后的 Pydantic 模型
        
    Raises:
        ValueError: 解析失败
    """
    # 尝试提取 JSON
    json_str = extract_json_from_response(response)
    
    if not json_str:
        raise ValueError("无法从响应中提取 JSON")
    
    try:
        # 解析为指定类型
        return expected_type.model_validate_json(json_str)
    except Exception as e:
        logger.error(f"JSON 解析失败: {e}, 内容: {json_str[:200]}")
        raise ValueError(f"JSON 解析失败: {e}")


def extract_json_from_response(response: str) -> Optional[str]:
    """
    从 LLM 响应中提取 JSON
    
    Args:
        response: LLM 原始响应
        
    Returns:
        提取的 JSON 字符串，如果没有则返回 None
    """
    # 尝试直接解析
    response = response.strip()
    
    # 移除 Markdown 代码块
    if "```json" in response:
        response = re.sub(r"```json\n?", "", response)
        response = re.sub(r"\n?```$", "", response)
    elif "```" in response:
        response = re.sub(r"```python\n?", "", response)
        response = re.sub(r"\n?```$", "", response)
    
    # 尝试找到 JSON 对象
    json_match = re.search(r"\{[\s\S]*\}", response)
    if json_match:
        return json_match.group(0)
    
    return None


# =============================================================================
# 测试入口
# =============================================================================

if __name__ == "__main__":
    # 测试数据模型
    print("=" * 60)
    print("测试强类型数据模型")
    print("=" * 60)
    
    # 测试 AgentState
    state = create_initial_state("600519.SH", "20250220", "市场上涨")
    print(state.to_summary())
    
    # 测试 StrategyHypothesis
    hypothesis = StrategyHypothesis(
        market_insight="市场放量上涨",
        trading_direction=TradingDirection.BUY,
        signal_type=SignalType.ENTRY,
        logic_rules=["突破20日均线", "成交量放大"],
        confidence=0.8,
        risk_score=6
    )
    print(hypothesis.to_prompt_string())
    
    # 测试 ReviewFeedback
    feedback = ReviewFeedback(
        passed=False,
        error_type=ErrorType.SYNTAX,
        fix_suggestion="修复语法错误",
        error_message="缺少冒号",
        risk_score=3
    )
    print(feedback.to_prompt_string())
    
    # 测试 BacktestResult
    result = BacktestResult(
        success=True,
        total_return=0.15,
        sharpe_ratio=1.5,
        max_drawdown=0.05,
        win_rate=0.6,
        total_trades=10,
        rejected_trades=2
    )
    print(result.to_prompt_string())
    
    print("\n✅ 所有测试通过")
