"""
AI TradeBot - Agent编排器 (解耦版)

这是整个系统的核心心脏。采用主板-插件架构，将5个Agent完全解耦。

5 个 Agent 职责：
1. Hunter (猎手) - 筛选候选标的，输出候选股票列表
2. Strategist (策略师) - 基于市场上下文生成策略代码
3. RiskOfficer (风控官) - 审查代码，检测 A 股规则违规
4. Judge (裁判) - 执行回测，验证策略有效性
5. Analyst (分析师) - 归因分析，总结经验教训

主板架构：
- 只负责按顺序实例化和调度Agent
- 保留原有的 retry_count >= 3 熔断机制
- 不包含任何具体的业务逻辑

作者: Matrix Agent
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

from shared.logging import get_logger

# 导入Agent模块
from .agents import (
    BaseAgent,
    HunterAgent,
    StrategistAgent,
    RiskAgent,
    JudgeAgent,
    AnalystAgent,
)

# 导入Schema
from .schemas import (
    AgentState,
    AgentStatus,
    PipelineStep,
    create_initial_state,
)


logger = get_logger(__name__)


# =============================================================================
# 常量定义
# =============================================================================

# 最大重试次数 (熔断阈值)
MAX_RETRY_COUNT = 3


# =============================================================================
# 核心类: AgentOrchestrator (主板)
# =============================================================================

class AgentOrchestrator:
    """
    Agent编排器 (主板模式)
    
    采用主板-插件架构：
    - 主板(Motherboard): 负责流程控制和状态流转
    - 插件(Agent): 5个独立的Agent模块，各司其职
    
    Usage:
        orchestrator = AgentOrchestrator()
        result = await orchestrator.run_pipeline("600519.SH", "20250220")
    """
    
    def __init__(
        self,
        max_retries: int = MAX_RETRY_COUNT,
        enable_circuit_breaker: bool = True,
    ):
        """
        初始化编排器 (主板)
        
        Args:
            max_retries: 最大重试次数 (熔断阈值)
            enable_circuit_breaker: 是否启用熔断机制
        """
        self.max_retries = max_retries
        self.enable_circuit_breaker = enable_circuit_breaker
        
        # 实例化5个独立Agent (插件)
        self.hunter = HunterAgent()
        self.strategist = StrategistAgent()
        self.risk_officer = RiskAgent()
        self.judge = JudgeAgent()
        self.analyst = AnalystAgent()
        
        # Agent列表 (按顺序)
        self.agent_pipeline: List[BaseAgent] = [
            self.hunter,
            self.strategist,
            self.risk_officer,
            self.judge,
            self.analyst,
        ]
        
        # 当前状态
        self.state: Optional[AgentState] = None
        
        logger.info(f"[Orchestrator] 主板初始化完成")
        logger.info(f"[Orchestrator] 已加载 Agent: {[a.name for a in self.agent_pipeline]}")
        logger.info(f"[Orchestrator] 熔断阈值: {max_retries}, 启用: {enable_circuit_breaker}")
    
    # =========================================================================
    # 核心方法: run_pipeline
    # =========================================================================
    
    async def run_pipeline(
        self,
        stock_code: str,
        trade_date: str = None,
        market_context: Dict[str, Any] = None,
    ) -> AgentState:
        """
        运行完整的Agent流水线
        
        Args:
            stock_code: 股票代码
            trade_date: 交易日期
            market_context: 市场上下文数据
            
        Returns:
            最终的AgentState状态
        """
        logger.info(f"[Orchestrator] 开始流水线: {stock_code}")
        
        # 初始化状态
        self.state = create_initial_state(
            stock_code=stock_code,
            trade_date=trade_date or datetime.now().strftime("%Y%m%d"),
        )
        self.state.market_context = market_context or {}
        
        # 重试循环 (当熔断触发时)
        while True:
            logger.info(f"[Orchestrator] 第 {self.state.retry_count + 1} 次尝试")
            
            # 重置状态 (保留retry_count)
            retry_count = self.state.retry_count
            
            # 执行完整流水线
            self.state = await self._execute_pipeline(self.state)
            
            # 检查是否需要熔断
            if self.enable_circuit_breaker and self.state.retry_count >= self.max_retries:
                logger.warning(f"[Orchestrator] ⚠️ 熔断触发! 重试次数: {self.state.retry_count}")
                self.state.status = AgentStatus.CIRCUIT_BROKEN
                break
            
            # 检查是否成功完成
            if self.state.status == AgentStatus.COMPLETED:
                logger.info(f"[Orchestrator] ✅ 流水线成功完成")
                break
            
            # 检查是否应该重试
            if self.state.retry_count > retry_count:
                logger.info(f"[Orchestrator] 🔄 需要重试，继续执行...")
                continue
            
            # 其他失败情况
            break
        
        return self.state
    
    async def _execute_pipeline(self, state: AgentState) -> AgentState:
        """
        执行单次完整流水线
        
        Args:
            state: 初始状态
            
        Returns:
            处理后的状态
        """
        logger.info("[Orchestrator] ===== 流水线开始 =====")
        
        # 遍历每个Agent (插件)
        for agent in self.agent_pipeline:
            logger.info(f"[Orchestrator] → 调用 {agent.name}...")
            
            # 更新当前Agent
            state.current_agent = agent.name
            
            # 执行Agent处理
            state = await agent.execute(state)
            
            # 检查Agent是否失败
            if state.status == AgentStatus.FAILED:
                logger.warning(f"[Orchestrator] {agent.name} 执行失败")
                # 如果是Strategist之后的Agent失败，增加重试计数
                if agent in [self.strategist, self.risk_officer, self.judge]:
                    state.retry_count += 1
                break
            
            # 检查风控是否拒绝 (需要重试)
            if agent == self.risk_officer and state.review_feedback:
                if not state.review_feedback.approved:
                    logger.warning(f"[Orchestrator] ⚠️ 风控拒绝策略")
                    # 不再继续执行，直接跳转到Analyst
                    continue
            
            # 记录进度
            state.pipeline_logs.append({
                "agent": "Orchestrator",
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"{agent.name} 执行完成"
            })
        
        logger.info("[Orchestrator] ===== 流水线结束 =====")
        
        # 更新最终状态
        if state.status != AgentStatus.FAILED:
            state.status = AgentStatus.COMPLETED
        
        return state
    
    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    def get_agent_status(self) -> Dict[str, str]:
        """
        获取所有Agent的状态
        
        Returns:
            Agent名称到状态的映射
        """
        return {
            "Hunter": "READY",
            "Strategist": "READY",
            "RiskOfficer": "READY",
            "Judge": "READY",
            "Analyst": "READY",
        }
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """
        获取流水线信息
        
        Returns:
            流水线配置信息
        """
        return {
            "agents": [agent.name for agent in self.agent_pipeline],
            "max_retries": self.max_retries,
            "circuit_breaker_enabled": self.enable_circuit_breaker,
            "current_state": self.state.status.value if self.state else "NOT_STARTED",
        }
    
    async def run_single_agent(
        self,
        agent_name: str,
        state: AgentState,
    ) -> AgentState:
        """
        运行单个Agent (用于调试)
        
        Args:
            agent_name: Agent名称
            state: 输入状态
            
        Returns:
            处理后的状态
        """
        agent_map = {
            "Hunter": self.hunter,
            "Strategist": self.strategist,
            "RiskOfficer": self.risk_officer,
            "Judge": self.judge,
            "Analyst": self.analyst,
        }
        
        agent = agent_map.get(agent_name)
        if not agent:
            raise ValueError(f"Unknown agent: {agent_name}")
        
        return await agent.execute(state)


# =============================================================================
# 便捷函数
# =============================================================================

async def quick_decision(
    stock_code: str,
    trade_date: str = None,
) -> AgentState:
    """
    快速决策 (一键调用)
    
    Args:
        stock_code: 股票代码
        trade_date: 交易日期
        
    Returns:
        最终决策状态
    """
    orchestrator = AgentOrchestrator()
    return await orchestrator.run_pipeline(stock_code, trade_date)
