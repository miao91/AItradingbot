"""
AI TradeBot - Analyst Agent (归因分析师)

负责失败归因分析，总结经验教训。

作者: Matrix Agent
"""

from typing import Dict, Any, List
from datetime import datetime

from .base_agent import BaseAgent
from ..schemas import AgentState, AgentStatus, LessonsLearned
from ..prompts import ANALYST_SYSTEM_PROMPT, format_analyst_prompt
from ..llm_client import get_llm_client_for_agent


class AnalystAgent(BaseAgent):
    """
    Analyst Agent - 归因分析师
    
    职责:
    - 分析策略失败原因
    - 总结经验教训
    - 输出改进建议
    """
    
    def __init__(self, llm_client=None, timeout: int = 30):
        super().__init__(
            name="Analyst",
            system_prompt=ANALYST_SYSTEM_PROMPT,
            timeout=timeout
        )
        self.llm_client = llm_client or get_llm_client_for_agent("Analyst")
    
    async def process(self, state: AgentState) -> AgentState:
        """
        进行归因分析
        
        Args:
            state: 包含所有前面步骤结果的状态
            
        Returns:
            更新后的状态，包含lessons_learned
        """
        self.logger.info("Analyst Agent 开始归因分析...")
        
        state.pipeline_logs.append({
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": "开始归因分析..."
        })
        
        try:
            # 收集失败信息
            failure_reasons = []
            success_factors = []
            
            # 检查各阶段失败原因
            if state.retry_count >= 3:
                failure_reasons.append("触发熔断机制(重试次数≥3)")
            
            if state.review_feedback and not state.review_feedback.approved:
                failure_reasons.append(f"风控审查未通过: {state.review_feedback.comments}")
            
            if state.backtest_result and not state.backtest_result.passed:
                failure_reasons.append("回测验证未通过")
                if state.backtest_result.metrics:
                    metrics = state.backtest_result.metrics
                    if metrics.total_return < 0:
                        failure_reasons.append(f"回测收益率为负: {metrics.total_return:.2%}")
                    if metrics.sharpe_ratio < 0.5:
                        failure_reasons.append(f"夏普比率过低: {metrics.sharpe_ratio:.2f}")
            
            if state.error_message:
                failure_reasons.append(f"系统错误: {state.error_message}")
            
            # 如果没有失败，收集成功因素
            if not failure_reasons and state.backtest_result and state.backtest_result.passed:
                success_factors.append("策略通过所有审查")
                if state.backtest_result.metrics:
                    metrics = state.backtest_result.metrics
                    if metrics.sharpe_ratio > 1.0:
                        success_factors.append(f"夏普比率优秀: {metrics.sharpe_ratio:.2f}")
                    if metrics.win_rate > 0.5:
                        success_factors.append(f"胜率较高: {metrics.win_rate:.1%}")
            
            # 生成改进建议
            suggestions = self._generate_suggestions(state, failure_reasons)
            
            # 创建LessonsLearned
            lessons = LessonsLearned(
                failure_reasons=failure_reasons if failure_reasons else [],
                success_factors=success_factors if success_factors else [],
                suggestions=suggestions,
                confidence_boost=0.1 if not failure_reasons else 0.0,
                created_at=datetime.now()
            )
            
            # 更新状态
            state.lessons_learned = lessons
            state.analysis_completed = True
            
            # 记录日志
            status = "成功" if not failure_reasons else "失败"
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"归因分析完成: {status}"
            })
            
            self.logger.info(f"Analyst Agent 完成: {status}")
            return state
            
        except Exception as e:
            self.logger.error(f"Analyst Agent 处理失败: {str(e)}")
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"归因分析失败: {str(e)}"
            })
            
            # 创建空归因
            state.lessons_learned = LessonsLearned(
                failure_reasons=[str(e)],
                success_factors=[],
                suggestions=["请检查系统配置"],
                confidence_boost=0.0,
                created_at=datetime.now()
            )
            return state
    
    def _generate_suggestions(self, state: AgentState, failure_reasons: List[str]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        
        # 基于失败原因生成建议
        for reason in failure_reasons:
            if "风控" in reason:
                suggestions.append("优化止损止盈设置，确保符合风控要求")
                suggestions.append("增加仓位管理逻辑，避免单一仓位过重")
            if "回测" in reason:
                suggestions.append("增加风险缓冲，减少最大回撤")
                suggestions.append("考虑增加过滤器条件，提高信号质量")
            if "熔断" in reason:
                suggestions.append("简化策略逻辑，减少复杂条件")
                suggestions.append("检查市场数据质量")
            if "收益率" in reason or "夏普" in reason:
                suggestions.append("优化入场时机选择")
                suggestions.append("考虑添加趋势确认指标")
        
        # 如果没有具体建议，提供通用建议
        if not suggestions:
            suggestions = [
                "当前策略表现良好，建议继续监控",
                "可尝试小仓位实盘验证"
            ]
        
        return suggestions
