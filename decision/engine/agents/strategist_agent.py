"""
AI TradeBot - Strategist Agent (策略架构师)

负责生成交易策略代码，进行AST代码提取和逻辑推演。

作者: Matrix Agent
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent
from ..schemas import AgentState, AgentStatus
from ..prompts import STRATEGIST_SYSTEM_PROMPT, format_strategist_prompt
from ..llm_client import get_llm_client_for_agent
from ..ast_utils import extract_and_validate_code, CodeExtractionError


class StrategistAgent(BaseAgent):
    """
    Strategist Agent - 策略架构师
    
    职责:
    - 基于市场假说生成策略代码
    - 进行AST代码提取和验证
    - 输出可执行的Python策略代码
    """
    
    def __init__(self, llm_client=None, timeout: int = 45):
        super().__init__(
            name="Strategist",
            system_prompt=STRATEGIST_SYSTEM_PROMPT,
            timeout=timeout
        )
        self.llm_client = llm_client or get_llm_client_for_agent("Strategist")
    
    async def process(self, state: AgentState) -> AgentState:
        """
        生成策略代码
        
        Args:
            state: 包含strategy_hypothesis的状态
            
        Returns:
            更新后的状态，包含strategy_code
        """
        self.logger.info("Strategist Agent 开始生成策略代码...")
        
        state.pipeline_logs.append({
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": "开始生成策略代码..."
        })
        
        try:
            # 检查是否有假说
            if not state.strategy_hypothesis:
                state.pipeline_logs.append({
                    "agent": self.name,
                    "timestamp": datetime.now().isoformat(),
                    "level": "ERROR",
                    "message": "缺少市场假说，无法生成策略"
                })
                return self._create_empty_strategy(state)
            
            # 构建提示词
            hypothesis = state.strategy_hypothesis
            prompt = format_strategist_prompt(
                signal_type=hypothesis.signal_type,
                market_insight=hypothesis.market_insight,
                trading_direction=hypothesis.trading_direction.value,
                rationale=hypothesis.rationale,
                risk_factors=", ".join(hypothesis.risk_factors) if hypothesis.risk_factors else "无"
            )
            
            # 调用LLM生成代码
            response = await self.llm_client.chat(
                system_prompt=self.system_prompt,
                user_prompt=prompt
            )
            
            # 提取和验证代码
            code_result = self._extract_code(response)
            
            # 创建策略代码字典
            strategy_code = {
                "language": "python",
                "code": code_result["code"],
                "logic_reasoning": code_result.get("reasoning", ""),
                "entry_condition": code_result.get("entry", ""),
                "exit_condition": code_result.get("exit", ""),
                "stop_loss": code_result.get("stop_loss", 0.05),
                "take_profit": code_result.get("take_profit", 0.10),
                "created_at": datetime.now().isoformat()
            }
            
            # 更新状态
            state.strategy_code = strategy_code
            state.code_generated = True
            
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"策略代码生成完成，止损: {strategy_code['stop_loss']:.1%}, 止盈: {strategy_code['take_profit']:.1%}"
            })
            
            self.logger.info("Strategist Agent 完成策略代码生成")
            return state
            
        except Exception as e:
            self.logger.error(f"Strategist Agent 处理失败: {str(e)}")
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"策略生成失败: {str(e)}"
            })
            return self._create_empty_strategy(state)
    
    def _extract_code(self, response: str) -> Dict[str, Any]:
        """从LLM响应中提取代码"""
        import re
        
        # 尝试提取代码块
        code_match = re.search(r'```python([\s\S]*?)```', response)
        if code_match:
            code = code_match.group(1).strip()
        else:
            # 尝试直接提取
            code_match = re.search(r'def[\s\S]*', response)
            code = code_match.group(0) if code_match else response
        
        # AST验证
        try:
            validated = extract_and_validate_code(code)
        except CodeExtractionError as e:
            self.logger.warning(f"代码验证警告: {e}")
            validated = code  # 使用原始代码
        
        # 提取参数
        stop_loss = self._extract_param(response, "止损") or 0.05
        take_profit = self._extract_param(response, "止盈") or 0.10
        
        return {
            "code": validated,
            "reasoning": "基于市场分析生成的策略代码",
            "entry": "RSI < 30 且 MACD 金叉",
            "exit": "RSI > 70 或 MACD 死叉",
            "stop_loss": stop_loss,
            "take_profit": take_profit
        }
    
    def _extract_param(self, text: str, keyword: str) -> Optional[float]:
        """提取参数"""
        import re
        pattern = f'{keyword}[：:]*\\s*(\\d+\\.?\\d*)%?'
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))
            return value / 100 if value > 1 else value
        return None
    
    def _create_empty_strategy(self, state: AgentState) -> AgentState:
        """创建空策略"""
        state.strategy_code = {
            "language": "python",
            "code": "# 策略生成失败",
            "logic_reasoning": "",
            "entry_condition": "",
            "exit_condition": "",
            "stop_loss": 0.05,
            "take_profit": 0.10,
            "created_at": datetime.now().isoformat()
        }
        return state
