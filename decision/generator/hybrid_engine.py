"""
AI TradeBot - 混合决策引擎

功能：
- 结合传统五维评估与AI生成策略
- 策略回测失败时自动回退
- 对接现有风控系统

核心公式: S_{t+1} = AI_agent(News_t, Flow_t, Factor_t)
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from shared.logging import get_logger

from .context_builder import MarketContext, MarketContextBuilder, get_market_context
from .strategy_generator import StrategyGenerator, GeneratedStrategy
from .strategy_reviewer import CodeReviewer, ReviewResult
from .backtest_engine import BacktestEngine, BacktestResult, BacktestStatus


logger = get_logger(__name__)


# =============================================================================
# 数据模型
# =============================================================================

class DecisionMode(Enum):
    """决策模式"""
    GENERATIVE_ONLY = "generative"     # 仅生成式策略
    TRADITIONAL_ONLY = "traditional"   # 仅传统策略
    HYBRID = "hybrid"                 # 混合模式


class DecisionResult(Enum):
    """决策结果"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    WAIT = "WAIT"


@dataclass
class TradingSignal:
    """交易信号"""
    result: DecisionResult
    action: str                      # BUY/SELL/HOLD
    size: float = 0.0                # 仓位比例
    stop_loss: float = 0.0          # 止损比例
    take_profit: float = 0.0        # 止盈比例
    confidence: float = 0.0         # 信心度 0-1
    reason: str = ""                 # 决策原因
    strategy_id: str = ""           # 策略ID
    strategy_type: str = ""          # 策略类型
    generated_strategy: Optional[GeneratedStrategy] = None  # 生成的策略
    backtest_result: Optional[BacktestResult] = None       # 回测结果
    timestamp: str = ""               # 时间戳
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.value,
            "action": self.action,
            "size": self.size,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "confidence": self.confidence,
            "reason": self.reason,
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type,
            "timestamp": self.timestamp,
        }


@dataclass
class DecisionProcess:
    """决策过程记录"""
    ticker: str
    start_time: str
    end_time: str = ""
    mode: DecisionMode = DecisionMode.HYBRID
    
    context_build_time: float = 0.0      # 上下文构建时间
    generation_time: float = 0.0        # 策略生成时间
    review_time: float = 0.0            # 审查时间
    backtest_time: float = 0.0          # 回测时间
    
    market_context: Optional[Dict] = None
    generated_strategy: Optional[Dict] = None
    review_result: Optional[Dict] = None
    backtest_result: Optional[Dict] = None
    
    final_signal: Optional[TradingSignal] = None
    
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "mode": self.mode.value,
            "timing": {
                "context_build": f"{self.context_build_time:.2f}s",
                "generation": f"{self.generation_time:.2f}s",
                "review": f"{self.review_time:.2f}s",
                "backtest": f"{self.backtest_time:.2f}s",
            },
            "market_context": self.market_context,
            "generated_strategy": self.generated_strategy,
            "review_result": self.review_result,
            "backtest_result": self.backtest_result,
            "final_signal": self.final_signal.to_dict() if self.final_signal else None,
            "error": self.error,
        }


# =============================================================================
# 混合决策引擎
# =============================================================================

class HybridDecisionEngine:
    """
    混合决策引擎
    
    结合传统五维评估与AI生成式策略
    """
    
    def __init__(
        self,
        mode: DecisionMode = DecisionMode.HYBRID,
        model: str = "glm-5"
    ):
        """
        初始化混合决策引擎
        
        Args:
            mode: 决策模式
            model: LLM模型
        """
        self.mode = mode
        self.model = model
        
        # 初始化各组件
        self.context_builder = MarketContextBuilder()
        self.strategy_generator = StrategyGenerator(model=model)
        self.code_reviewer = CodeReviewer()
        self.backtest_engine = BacktestEngine()
        
        logger.info(f"[HybridEngine] 初始化完成: mode={mode.value}, model={model}")
    
    async def make_decision(
        self,
        ticker: str = "000001.SH",
        force_generative: bool = False,
    ) -> TradingSignal:
        """
        做出交易决策
        
        Args:
            ticker: 股票代码
            force_generative: 是否强制使用生成式策略
            
        Returns:
            TradingSignal: 交易信号
        """
        import time
        process = DecisionProcess(
            ticker=ticker,
            start_time=datetime.now().isoformat(),
            mode=self.mode,
        )
        
        try:
            # 步骤1: 构建市场上下文
            start = time.time()
            logger.info(f"[HybridEngine] 构建市场上下文: {ticker}")
            market_context = await self.context_builder.build(ticker)
            process.context_build_time = time.time() - start
            process.market_context = market_context.to_dict()
            
            # 如果是纯传统模式，返回默认信号
            if self.mode== DecisionMode.TRADITIONAL_ONLY and not force_generative:
                return self._get_traditional_signal(ticker)
            
            # 步骤2: 生成策略
            start = time.time()
            logger.info(f"[HybridEngine] 生成AI策略")
            generated_strategy = await self.strategy_generator.generate(
                market_context.to_prompt_string()
            )
            process.generation_time = time.time() - start
            process.generated_strategy = generated_strategy.to_dict()
            
            # 步骤3: 审查策略代码
            start = time.time()
            logger.info(f"[HybridEngine] 审查策略代码")
            review_result = self.code_reviewer.review(generated_strategy.code)
            process.review_time = time.time() - start
            process.review_result = review_result.to_dict()
            
            # 步骤4: 回测验证
            if review_result.passed:
                start = time.time()
                logger.info(f"[HybridEngine] 执行回测验证")
                backtest_result = await self.backtest_engine.backtest(
                    generated_strategy.code,
                    ticker,
                    lookback_days=30
                )
                process.backtest_time = time.time() - start
                process.backtest_result = backtest_result.to_dict()
                
                # 判断是否通过验证
                if backtest_result.passed:
                    # 回测通过，使用生成策略
                    signal = self._build_signal_from_strategy(
                        generated_strategy,
                        backtest_result
                    )
                    process.final_signal = signal
                else:
                    # 回测失败，回退到传统信号
                    logger.warning(f"[HybridEngine] 回测未通过，使用传统信号")
                    signal = self._get_traditional_signal(ticker)
            else:
                # 审查未通过，回退到传统信号
                logger.warning(f"[HybridEngine] 策略审查未通过，使用传统信号")
                signal = self._get_traditional_signal(ticker)
            
            # 设置时间戳
            signal.timestamp = datetime.now().isoformat()
            process.end_time = datetime.now().isoformat()
            
            # 记录决策过程
            logger.info(f"[HybridEngine] 决策完成: {signal.action}, 信心度={signal.confidence:.2f}")
            
            return signal
            
        except Exception as e:
            logger.error(f"[HybridEngine] 决策出错: {e}")
            process.error = str(e)
            process.end_time = datetime.now().isoformat()
            
            # 返回默认持有信号
            return TradingSignal(
                result=DecisionResult.HOLD,
                action="HOLD",
                size=0,
                confidence=0.0,
                reason=f"决策出错: {str(e)}",
                timestamp=datetime.now().isoformat(),
            )
    
    def _build_signal_from_strategy(
        self,
        strategy: GeneratedStrategy,
        backtest: BacktestResult
    ) -> TradingSignal:
        """从生成的策略构建交易信号"""
        
        # 尝试执行策略获取信号
        try:
            import importlib.util
            
            # 加载策略函数
            spec = importlib.util.spec_from_loader("temp_strategy", loader=None)
            module = importlib.util.module_from_spec(spec)
            exec(strategy.code, module.__dict__)
            
            if hasattr(module, 'strategy'):
                func = module.strategy
                
                # 创建简单的上下文
                context = {
                    "sentiment": 0.0,
                    "rsi": 50.0,
                    "momentum": 0.0,
                }
                
                result = func(context)
                
                if result and isinstance(result, dict):
                    return TradingSignal(
                        result=DecisionResult(result.get("action", "HOLD")),
                        action=result.get("action", "HOLD"),
                        size=result.get("size", 0),
                        stop_loss=result.get("stop_loss", 0.02),
                        take_profit=result.get("take_profit", 0.05),
                        confidence=result.get("confidence", 0.5),
                        reason=result.get("reason", strategy.logic_description),
                        strategy_id=strategy.strategy_id,
                        strategy_type=strategy.strategy_type.value,
                        generated_strategy=strategy,
                        backtest_result=backtest,
                    )
        
        except Exception as e:
            logger.warning(f"[HybridEngine] 执行策略获取信号失败: {e}")
        
        # 如果无法执行，返回默认信号
        return TradingSignal(
            result=DecisionResult.HOLD,
            action="HOLD",
            size=0,
            confidence=0.5,
            reason=strategy.logic_description,
            strategy_id=strategy.strategy_id,
            strategy_type=strategy.strategy_type.value,
            generated_strategy=strategy,
            backtest_result=backtest,
        )
    
    def _get_traditional_signal(self, ticker: str) -> TradingSignal:
        """获取传统信号（基于简单规则）"""
        
        return TradingSignal(
            result=DecisionResult.HOLD,
            action="HOLD",
            size=0,
            confidence=0.3,
            reason="传统规则信号 - 保持观望",
            strategy_id="traditional",
            strategy_type="rule_based",
        )


# =============================================================================
# 便捷函数
# =============================================================================

async def make_decision(
    ticker: str = "000001.SH",
    mode: str = "hybrid"
) -> TradingSignal:
    """
    快速做出交易决策
    
    Usage:
        signal = await make_decision("600519.SH")
        print(signal.action, signal.reason)
    """
    mode_enum = DecisionMode.HYBRID
    if mode == "generative":
        mode_enum = DecisionMode.GENERATIVE_ONLY
    elif mode == "traditional":
        mode_enum = DecisionMode.TRADITIONAL_ONLY
    
    engine = HybridDecisionEngine(mode=mode_enum)
    return await engine.make_decision(ticker)


# =============================================================================
# 测试入口
# =============================================================================

if __name__ == "__main__":
    async def test():
        print("=" * 60)
        print("测试混合决策引擎")
        print("=" * 60)
        
        engine = HybridDecisionEngine(mode=DecisionMode.HYBRID)
        
        # 测试决策
        signal = await engine.make_decision("600519.SH")
        
        print(f"\n最终信号: {signal.action}")
        print(f"仓位: {signal.size:.1%}")
        print(f"止损: {signal.stop_loss:.1%}")
        print(f"止盈: {signal.take_profit:.1%}")
        print(f"信心度: {signal.confidence:.2f}")
        print(f"原因: {signal.reason}")
        print(f"策略ID: {signal.strategy_id}")
        print(f"策略类型: {signal.strategy_type}")
        
        if signal.backtest_result:
            print(f"\n回测结果: {'通过' if signal.backtest_result.passed else '未通过'}")
            print(f"  夏普比率: {signal.backtest_result.metrics.sharpe_ratio:.2f}")
            print(f"  胜率: {signal.backtest_result.metrics.win_rate:.1%}")
            print(f"  最大回撤: {signal.backtest_result.metrics.max_drawdown:.2%}")
        
        print("=" * 60)
    
    # asyncio.run(test())
    print("HybridDecisionEngine 模块已加载")
