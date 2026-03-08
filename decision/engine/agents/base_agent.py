"""
AI TradeBot - Agent抽象基类

定义所有Agent必须实现的接口，确保模块化设计的一致性。

作者: Matrix Agent
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
import asyncio

from ..schemas import AgentState, AgentStatus, PipelineStep


class BaseAgent(ABC):
    """
    Agent抽象基类
    
    所有Agent必须继承此类并实现process方法。
    采用Chain of Responsibility模式，每个Agent处理完成后将状态传递给下一个Agent。
    
    Attributes:
        name: Agent名称
        system_prompt: 系统提示词
        timeout: 超时时间(秒)
    """
    
    def __init__(
        self, 
        name: str, 
        system_prompt: str = "",
        timeout: int = 30
    ):
        """
        初始化Agent
        
        Args:
            name: Agent名称
            system_prompt: 系统提示词
            timeout: 超时时间(秒)
        """
        self.name = name
        self.system_prompt = system_prompt
        self.timeout = timeout
        self._logger = None
    
    @property
    def logger(self):
        """懒加载日志器"""
        if self._logger is None:
            try:
                from shared.logging import get_logger
                self._logger = get_logger(self.__class__.__name__)
            except ImportError:
                import logging
                self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger
    
    @abstractmethod
    async def process(self, state: AgentState) -> AgentState:
        """
        处理AgentState的核心方法
        
        每个Agent必须实现此方法，处理输入的状态并返回更新后的状态。
        
        Args:
            state: 当前AgentState状态
            
        Returns:
            更新后的AgentState状态
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement process()")
    
    async def execute(self, state: AgentState) -> AgentState:
        """
        执行Agent处理，包含超时和异常处理
        
        Args:
            state: 当前AgentState状态
            
        Returns:
            处理后的状态
        """
        start_time = datetime.now()
        
        try:
            # 更新状态为处理中
            state.current_step = self._get_pipeline_step()
            state.status = AgentStatus.PROCESSING
            
            self.logger.info(f"[{self.name}] 开始处理...")
            
            # 执行处理逻辑
            result_state = await asyncio.wait_for(
                self.process(state),
                timeout=self.timeout
            )
            
            # 处理成功
            result_state.status = AgentStatus.COMPLETED
            result_state.error_message = None
            
            elapsed = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"[{self.name}] 处理完成，耗时 {elapsed:.2f}秒")
            
            return result_state
            
        except asyncio.TimeoutError:
            self.logger.error(f"[{self.name}] 处理超时 ({self.timeout}秒)")
            state.status = AgentStatus.FAILED
            state.error_message = f"{self.name} 处理超时"
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"处理超时 ({self.timeout}秒)"
            })
            return state
            
        except Exception as e:
            self.logger.error(f"[{self.name}] 处理失败: {str(e)}")
            state.status = AgentStatus.FAILED
            state.error_message = f"{self.name}: {str(e)}"
            state.pipeline_logs.append({
                "agent": self.name,
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"处理异常: {str(e)}"
            })
            return state
    
    def _get_pipeline_step(self) -> PipelineStep:
        """获取当前Agent对应的PipelineStep"""
        step_map = {
            "Hunter": PipelineStep.HUNTER,
            "Strategist": PipelineStep.STRATEGIST,
            "RiskOfficer": PipelineStep.RISK_OFFICER,
            "Judge": PipelineStep.JUDGE,
            "Analyst": PipelineStep.ANALYST,
        }
        return step_map.get(self.name, PipelineStep.HUNTER)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"
