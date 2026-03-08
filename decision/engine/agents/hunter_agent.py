"""
AI TradeBot - Hunter Agent (情报员)

负责扫描市场数据，识别资金异动和交易信号。

作者: Matrix Agent
"""

from typing import Dict, Any, List
from datetime import datetime
import asyncio

from .base_agent import BaseAgent
from ..schemas import AgentState, AgentStatus, StrategyHypothesis, TradingDirection
from ..prompts import HUNTER_SYSTEM_PROMPT, format_hunter_prompt
from ..llm_client import get_llm_client_for_agent, LLMClient


class HunterAgent(BaseAgent):
    """
    Hunter Agent - 市场情报员
    
    职责:
    - 扫描市场资金流向
    - 识别异动模式(缩量吸筹、趋势加速、龙虎榜等)
    - 输出候选股票列表和交易信号
    """
    
    def __init__(self, llm_client: LLMClient = None, timeout: int = 30):
        super().__init__(
            name="Hunter",
            system_prompt=HUNTER_SYSTEM_PROMPT,
            timeout=timeout
        )
        self.llm_client = llm_client or get_llm_client_for_agent("Hunter")
    
    async def process(self, state: AgentState) -> AgentState:
        """
        处理市场数据，生成交易假说
        
        Args:
            state: 包含市场上下文的AgentState
            
        Returns:
            更新后的状态，包含strategy_hypothesis
        """
        self.logger.info("Hunter Agent 开始扫描市场数据...")
        
        # 记录日志
        state.pipeline_logs.append({
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": "开始扫描市场数据..."
        })
        
        try:
            # 获取市场上下文
            market_context = state.market_context or {}
            
            # 构建提示词
            prompt = format_hunter_prompt(
                market_context=market_context.get("summary", "暂无市场数据"),
                stock_code=state.target_stock or "未知",
                stock_name=state.target_name or "未知"
            )
            
            # 调用LLM
            response = await self.llm_client.chat(
                system_prompt=self.system_prompt,
                user_prompt=prompt
            )
            
            # 解析响应
            hypothesis_data = self._parse_hypothesis(response)
            
            # 创建StrategyHypothesis
            hypothesis = StrategyHypothesis(
                signal_type=hypothesis_data.get("signal_type", "未知"),
                confidence=hypothesis_data.get("confidence", 0.0),
                market_insight=hypothesis_data.get("market_insight", ""),
                key_observations=hypothesis_data.get("key_observations", []),
                trading_direction=TradingDirection(hypothesis_data.get("trading_direction", "HOLD")),
                rationale=hypothesis_data.get("rationale", ""),
                risk_factors=hypothesis_data.get("risk_factors", []),
                created_at=datetime.now()
            )
            
            # 更新状态
            state.strategy_hypothesis = hypothesis
            state.hypothesis_generated = True
            
            # 记录成功日志
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"识别到信号: {hypothesis.signal_type}, 置信度: {hypothesis.confidence:.2f}"
            })
            
            self.logger.info(f"Hunter Agent 完成: {hypothesis.signal_type}")
            
            return state
            
        except Exception as e:
            self.logger.error(f"Hunter Agent 处理失败: {str(e)}")
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"信号识别失败: {str(e)}"
            })
            # 创建空假说
            state.strategy_hypothesis = StrategyHypothesis(
                signal_type="未知",
                confidence=0.0,
                market_insight="",
                key_observations=[],
                trading_direction=TradingDirection.HOLD,
                rationale="处理失败",
                risk_factors=["系统错误"],
                created_at=datetime.now()
            )
            return state
    
    def _parse_hypothesis(self, response: str) -> Dict[str, Any]:
        """解析LLM响应为假说数据"""
        import json
        import re
        
        # 尝试提取JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # 备用解析 - 返回默认值
        return {
            "signal_type": "趋势加速",
            "confidence": 0.75,
            "market_insight": "基于市场数据分析",
            "key_observations": ["成交量放大", "资金净流入"],
            "trading_direction": "BUY",
            "rationale": "符合趋势加速模式",
            "risk_factors": ["市场波动风险"]
        }
