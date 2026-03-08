"""
AI TradeBot - 生成式策略模块

核心公式: S_{t+1} = AI_agent(News_t, Flow_t, Factor_t)

模块组成:
- context_builder.py: 市场上下文构建器
- strategy_generator.py: AI策略生成器
- strategy_reviewer.py: 策略代码审查器
- backtest_engine.py: 快速回测引擎
- hybrid_engine.py: 混合决策引擎
"""

from .context_builder import MarketContext, MarketContextBuilder
from .strategy_generator import StrategyGenerator, StrategyTemplate
from .strategy_reviewer import CodeReviewer, ReviewResult
from .backtest_engine import BacktestEngine, BacktestResult
from .hybrid_engine import HybridDecisionEngine

__all__ = [
    "MarketContext",
    "MarketContextBuilder", 
    "StrategyGenerator",
    "StrategyTemplate",
    "CodeReviewer",
    "ReviewResult",
    "BacktestEngine",
    "BacktestResult",
    "HybridDecisionEngine",
]
