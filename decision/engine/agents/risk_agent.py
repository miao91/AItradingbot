"""
AI TradeBot - Risk Agent (风控合规官)

负责审查策略代码，检测A股规则违规。

作者: Matrix Agent
"""

from typing import Dict, Any, List
from datetime import datetime

from .base_agent import BaseAgent
from ..schemas import AgentState, AgentStatus, ReviewFeedback
from ..prompts import RISK_OFFICER_SYSTEM_PROMPT, format_risk_officer_prompt
from ..llm_client import get_llm_client_for_agent


class RiskAgent(BaseAgent):
    """
    Risk Agent - 风控合规官
    
    职责:
    - 审查策略代码的合规性
    - 检测A股规则违规(T+1、涨跌停等)
    - 输出审查反馈
    """
    
    def __init__(self, llm_client=None, timeout: int = 30):
        super().__init__(
            name="RiskOfficer",
            system_prompt=RISK_OFFICER_SYSTEM_PROMPT,
            timeout=timeout
        )
        self.llm_client = llm_client or get_llm_client_for_agent("RiskOfficer")
    
    async def process(self, state: AgentState) -> AgentState:
        """
        审查策略代码
        
        Args:
            state: 包含strategy_code的状态
            
        Returns:
            更新后的状态，包含review_feedback
        """
        self.logger.info("Risk Agent 开始审查策略代码...")
        
        state.pipeline_logs.append({
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": "开始风控审查..."
        })
        
        try:
            # 检查是否有策略代码
            if not state.strategy_code:
                state.pipeline_logs.append({
                    "agent": self.name,
                    "timestamp": datetime.now().isoformat(),
                    "level": "ERROR",
                    "message": "缺少策略代码，无法审查"
                })
                return self._create_reject_feedback(state, "缺少策略代码")
            
            # 构建提示词
            prompt = format_risk_officer_prompt(
                strategy_code=state.strategy_code.code,
                stop_loss=state.strategy_code.stop_loss,
                take_profit=state.strategy_code.take_profit
            )
            
            # 调用LLM进行审查
            response = await self.llm_client.chat(
                system_prompt=self.system_prompt,
                user_prompt=prompt
            )
            
            # 解析审查结果
            review_result = self._parse_review(response)
            
            # 创建ReviewFeedback
            feedback = ReviewFeedback(
                approved=review_result["approved"],
                risk_score=review_result.get("risk_score", 0.5),
                risk_flags=review_result.get("risk_flags", []),
                compliance_checklist=review_result.get("compliance_checklist", []),
                comments=review_result.get("comments", ""),
                retry_suggestions=review_result.get("retry_suggestions", []),
                created_at=datetime.now()
            )
            
            # 更新状态
            state.review_feedback = feedback
            state.code_reviewed = True
            
            # 如果未通过，增加重试计数
            if not feedback.approved:
                state.retry_count += 1
                state.pipeline_logs.append({
                    "agent": self.name,
                    "timestamp": datetime.now().isoformat(),
                    "level": "WARNING",
                    "message": f"策略未通过风控审查，重试次数: {state.retry_count}"
                })
            else:
                state.pipeline_logs.append({
                    "agent": self.name,
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "message": f"策略通过风控审查，风险评分: {feedback.risk_score:.2f}"
                })
            
            self.logger.info(f"Risk Agent 完成: approved={feedback.approved}")
            return state
            
        except Exception as e:
            self.logger.error(f"Risk Agent 处理失败: {str(e)}")
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"风控审查失败: {str(e)}"
            })
            return self._create_reject_feedback(state, str(e))
    
    def _parse_review(self, response: str) -> Dict[str, Any]:
        """解析审查结果"""
        import re
        
        # 简单解析 - 检查是否包含"通过"、"批准"等关键词
        approved = any(keyword in response for keyword in ["通过", "批准", "approved", "pass", "✓"])
        
        # 提取风险评分
        score_match = re.search(r'风险评分[：:]*\s*(\d+\.?\d*)', response)
        risk_score = float(score_match.group(1)) / 100 if score_match else 0.5
        
        # 提取风险因素
        risk_flags = []
        if "频繁交易" in response:
            risk_flags.append("可能存在频繁交易")
        if "止损" not in response and "止盈" not in response:
            risk_flags.append("缺少止损止盈设置")
        
        # 合规检查清单
        checklist = [
            ("T+1规则", "T+1规则已考虑" in response or "t+1" in response.lower()),
            ("涨跌停", "涨跌停" in response or "limit" in response.lower()),
            ("仓位管理", "仓位" in response or "position" in response.lower()),
            ("止损机制", "止损" in response or "stop" in response.lower()),
        ]
        
        return {
            "approved": approved,
            "risk_score": risk_score,
            "risk_flags": risk_flags,
            "compliance_checklist": checklist,
            "comments": response[:200],
            "retry_suggestions": risk_flags if not approved else []
        }
    
    def _create_reject_feedback(self, state: AgentState, reason: str) -> AgentState:
        """创建拒绝反馈"""
        state.review_feedback = ReviewFeedback(
            approved=False,
            risk_score=1.0,
            risk_flags=[reason],
            compliance_checklist=[],
            comments=reason,
            retry_suggestions=["请检查输入数据"],
            created_at=datetime.now()
        )
        state.retry_count += 1
        return state
