"""
AI TradeBot - Judge Agent (绩效法官)

负责执行回测，验证策略有效性。

作者: Matrix Agent
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent
from ..schemas import AgentState, AgentStatus, BacktestResult, BacktestMetrics


class JudgeAgent(BaseAgent):
    """
    Judge Agent - 绩效法官
    
    职责:
    - 执行策略回测
    - 计算绩效指标(收益率、夏普比率、最大回撤等)
    - 输出回测结果
    """
    
    def __init__(self, timeout: int = 60):
        super().__init__(
            name="Judge",
            system_prompt="你是绩效法官，负责执行回测验证策略有效性。",
            timeout=timeout
        )
    
    async def process(self, state: AgentState) -> AgentState:
        """
        执行回测
        
        Args:
            state: 包含strategy_code和review_feedback的状态
            
        Returns:
            更新后的状态，包含backtest_result
        """
        self.logger.info("Judge Agent 开始执行回测...")
        
        state.pipeline_logs.append({
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": "开始回测验证..."
        })
        
        try:
            # 检查是否通过风控
            if not state.review_feedback or not state.review_feedback.approved:
                state.pipeline_logs.append({
                    "agent": self.name,
                    "timestamp": datetime.now().isoformat(),
                    "level": "WARNING",
                    "message": "策略未通过风控，跳过回测"
                })
                return self._create_failed_result(state, "策略未通过风控审查")
            
            # 检查是否有策略代码
            if not state.strategy_code:
                return self._create_failed_result(state, "缺少策略代码")
            
            # 执行回测(这里使用模拟数据，实际应该对接AShareSandbox)
            backtest_result = await self._execute_backtest(state)
            
            # 更新状态
            state.backtest_result = backtest_result
            state.backtest_completed = True
            
            # 记录日志
            metrics = backtest_result.metrics
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"回测完成: 收益率={metrics.total_return:.2%}, 夏普={metrics.sharpe_ratio:.2f}"
            })
            
            self.logger.info(f"Judge Agent 完成: {metrics.total_return:.2%}")
            return state
            
        except Exception as e:
            self.logger.error(f"Judge Agent 处理失败: {str(e)}")
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"回测失败: {str(e)}"
            })
            return self._create_failed_result(state, str(e))
    
    async def _execute_backtest(self, state: AgentState) -> BacktestResult:
        """执行回测(模拟实现)"""
        import random
        
        # 模拟回测参数
        initial_capital = 1000000  # 100万
        days = 250  # 一年交易日
        
        # 模拟收益率序列
        daily_returns = [random.uniform(-0.02, 0.025) for _ in range(days)]
        
        # 计算累计收益
        equity_curve = [initial_capital]
        for ret in daily_returns:
            equity_curve.append(equity_curve[-1] * (1 + ret))
        
        # 计算指标
        total_return = (equity_curve[-1] - initial_capital) / initial_capital
        
        # 夏普比率(简化计算)
        avg_return = sum(daily_returns) / len(daily_returns)
        std_return = (sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
        sharpe_ratio = (avg_return / std_return) * (252 ** 0.5) if std_return > 0 else 0
        
        # 最大回撤
        peak = equity_curve[0]
        max_drawdown = 0
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 胜率
        wins = sum(1 for r in daily_returns if r > 0)
        win_rate = wins / len(daily_returns)
        
        # 创建回测结果
        metrics = BacktestMetrics(
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=len(daily_returns),
            avg_holding_days=5,
            profit_factor=1.5,
            calmar_ratio=total_return / max_drawdown if max_drawdown > 0 else 0
        )
        
        return BacktestResult(
            passed=total_return > 0 and sharpe_ratio > 0.5,
            metrics=metrics,
            equity_curve=equity_curve,
            trades=[{"date": f"2024-{i+1:02d}-01", "return": r} for i, r in enumerate(daily_returns[:10])],
            created_at=datetime.now()
        )
    
    def _create_failed_result(self, state: AgentState, reason: str) -> AgentState:
        """创建失败的回测结果"""
        metrics = BacktestMetrics(
            total_return=-1.0,
            sharpe_ratio=0.0,
            max_drawdown=1.0,
            win_rate=0.0,
            total_trades=0,
            avg_holding_days=0,
            profit_factor=0.0,
            calmar_ratio=0.0
        )
        
        state.backtest_result = BacktestResult(
            passed=False,
            metrics=metrics,
            equity_curve=[],
            trades=[],
            error_message=reason,
            created_at=datetime.now()
        )
        return state
