"""
AI TradeBot - 决策引擎模块

包含:
- 传统AI决策: 新闻分类、五维评估、推理引擎
- 生成式策略: 实时AI生成交易策略
- Agent状态机: 多智能体协作系统
"""

# 传统决策模块
from .news_classifier import (
    NewsClassifier,
    BatchNewsProcessor,
    NewsItem,
    ClassificationScore,
    ValuationImpactLevel,
    DurationEstimate,
    NewsCategory,
    get_news_classifier,
    get_batch_processor,
    classify_news,
)

from .five_dimension_scorer import (
    FiveDimensionScorer,
    FiveDimensionAssessment,
    DimensionScore,
    ScoreLevel,
    get_five_dimension_scorer,
    assess_trading_opportunity,
)

from .reasoning_engine import (
    ReasoningEngine,
    ReasoningChain,
    ReasoningStep,
    ReasoningStatus,
    get_reasoning_engine,
    start_reasoning_chain,
)

from .sandbox_validator import (
    SandboxValidator,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
    get_sandbox_validator,
    validate_valuation_output,
)

# 生成式策略模块
try:
    from .generator import (
        MarketContext,
        MarketContextBuilder,
        MarketPhase,
        StrategyGenerator,
        StrategyTemplate,
        CodeReviewer,
        ReviewResult,
        BacktestEngine,
        BacktestResult,
        HybridDecisionEngine,
    )
    GENERATOR_AVAILABLE = True
except ImportError as e:
    GENERATOR_AVAILABLE = False
    print(f"[Warning] Generator module not available: {e}")

# Agent 状态机模块
try:
    from .schemas import (
        AgentState,
        AgentStatus,
        PipelineStep,
        StrategyHypothesis,
        ReviewFeedback,
        LessonsLearned,
        BacktestResult as AgentBacktestResult,
        ErrorType,
        TradingDirection,
        StrategyCode,
        create_initial_state,
        parse_llm_json_response,
    )
    from .ast_utils import (
        extract_and_validate_code,
        CodeExtractionError,
        SyntaxValidationError,
        SecurityViolationError,
        safe_extract_code,
    )
    from .orchestrator import (
        AgentOrchestrator,
        AgentName,
        run_agent_pipeline,
    )
    from .llm_client import (
        LLMClient,
        LLMConfig,
        get_llm_client,
        LLMError,
        LLMJSONParseError,
    )
    from .prompts import (
        get_prompt,
        format_hunter_prompt,
        format_strategist_prompt,
        format_risk_officer_prompt,
        format_analyst_prompt,
    )
    ORCHESTRATOR_AVAILABLE = True
except ImportError as e:
    ORCHESTRATOR_AVAILABLE = False
    print(f"[Warning] Orchestrator module not available: {e}")


__all__ = [
    # News Classifier
    "NewsClassifier",
    "BatchNewsProcessor",
    "NewsItem",
    "ClassificationScore",
    "ValuationImpactLevel",
    "DurationEstimate",
    "NewsCategory",
    "get_news_classifier",
    "get_batch_processor",
    "classify_news",
    # Five Dimension Scorer
    "FiveDimensionScorer",
    "FiveDimensionAssessment",
    "DimensionScore",
    "ScoreLevel",
    "get_five_dimension_scorer",
    "assess_trading_opportunity",
    # Reasoning Engine
    "ReasoningEngine",
    "ReasoningChain",
    "ReasoningStep",
    "ReasoningStatus",
    "get_reasoning_engine",
    "start_reasoning_chain",
    # Sandbox Validator
    "SandboxValidator",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "get_sandbox_validator",
    "validate_valuation_output",
]

# 添加生成式策略到导出列表
if GENERATOR_AVAILABLE:
    __all__.extend([
        "MarketContext",
        "MarketContextBuilder",
        "MarketPhase",
        "StrategyGenerator",
        "StrategyTemplate",
        "CodeReviewer",
        "ReviewResult",
        "BacktestEngine",
        "BacktestResult",
        "HybridDecisionEngine",
    ])

# 添加 Agent 状态机到导出列表
if ORCHESTRATOR_AVAILABLE:
    __all__.extend([
        "AgentState",
        "AgentStatus",
        "PipelineStep",
        "StrategyHypothesis",
        "ReviewFeedback",
        "LessonsLearned",
        "AgentBacktestResult",
        "ErrorType",
        "TradingDirection",
        "StrategyCode",
        "create_initial_state",
        "parse_llm_json_response",
        "extract_and_validate_code",
        "CodeExtractionError",
        "SyntaxValidationError",
        "SecurityViolationError",
        "safe_extract_code",
        "AgentOrchestrator",
        "AgentName",
        "run_agent_pipeline",
        "LLMClient",
        "LLMConfig",
        "get_llm_client",
        "LLMError",
        "LLMJSONParseError",
        "get_prompt",
        "format_hunter_prompt",
        "format_strategist_prompt",
        "format_risk_officer_prompt",
        "format_analyst_prompt",
    ])
