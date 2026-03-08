"""
AI TradeBot - 交易状态管理器

线程安全的全局状态管理器，用于：
1. 存储当前交易决策过程
2. 提供决策日志给问答系统
3. 支持动态配置更新
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from threading import Lock
import uuid

from shared.logging import get_logger


logger = get_logger(__name__)


class BotStatus(Enum):
    """机器人状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ANALYZING = "analyzing"
    ERROR = "error"


class DecisionPhase(Enum):
    """决策阶段"""
    IDLE = "idle"
    PERCEPTION = "perception"  # 感知阶段
    ANALYSIS = "analysis"       # 分析阶段
    REASONING = "reasoning"     # 推理阶段
    DECISION = "decision"       # 决策阶段
    EXECUTION = "execution"     # 执行阶段
    COMPLETE = "complete"       # 完成


@dataclass
class DecisionStep:
    """决策步骤"""
    step_id: str
    phase: DecisionPhase
    model: str
    description: str
    input_summary: str
    output_summary: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradingSession:
    """交易会话"""
    session_id: str
    ticker: str
    status: BotStatus
    current_phase: DecisionPhase
    decision_steps: List[DecisionStep] = field(default_factory=list)
    final_decision: Optional[Dict[str, Any]] = None
    market_data: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    def add_step(self, step: DecisionStep):
        """添加决策步骤"""
        self.decision_steps.append(step)
        self.current_phase = step.phase
    
    def get_recent_steps(self, minutes: int = 5) -> List[DecisionStep]:
        """获取最近N分钟的决策步骤"""
        cutoff = datetime.now().timestamp() - (minutes * 60)
        return [s for s in self.decision_steps if s.timestamp.timestamp() > cutoff]


@dataclass
class ChatMessage:
    """聊天消息"""
    message_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)


class TradingStateManager:
    """
    交易状态管理器 (单例)
    
    提供线程安全的全局状态访问：
    - 当前交易状态
    - 决策日志
    - 问答历史
    - 配置管理
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 当前活跃会话
        self._current_session: Optional[TradingSession] = None
        
        # 历史会话
        self._sessions: List[TradingSession] = []
        self._max_sessions = 100  # 最多保留100个历史会话
        
        # 问答历史
        self._chat_history: List[ChatMessage] = []
        self._max_chat_history = 200
        
        # 全局配置
        self._config: Dict[str, Any] = {
            "risk_level": "medium",  # low, medium, high
            "max_position_size": 0.1,
            "enable_auto_trade": True,
            "max_daily_trades": 10,
            "dxy_threshold": 0.5,
        }
        
        # 状态锁
        self._state_lock = Lock()
        
        # 问答队列
        self._pending_questions: asyncio.Queue = asyncio.Queue()
        
        self._initialized = True
        logger.info("[状态管理器] 初始化完成")
    
    # =========================================================================
    # 会话管理
    # =========================================================================
    
    def start_session(self, ticker: str) -> TradingSession:
        """开始新的交易会话"""
        with self._state_lock:
            # 如果有未完成的会话，先标记结束
            if self._current_session and self._current_session.end_time is None:
                self._current_session.end_time = datetime.now()
                self._sessions.append(self._current_session)
                # 修剪历史会话
                if len(self._sessions) > self._max_sessions:
                    self._sessions = self._sessions[-self._max_sessions:]
            
            # 创建新会话
            session_id = f"SESSION_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self._current_session = TradingSession(
                session_id=session_id,
                ticker=ticker,
                status=BotStatus.RUNNING,
                current_phase=DecisionPhase.IDLE
            )
            
            logger.info(f"[状态管理器] 开始新会话: {session_id}")
            return self._current_session
    
    def end_session(self):
        """结束当前会话"""
        with self._state_lock:
            if self._current_session:
                self._current_session.end_time = datetime.now()
                self._current_session.status = BotStatus.IDLE
                self._sessions.append(self._current_session)
                
                # 修剪历史会话
                if len(self._sessions) > self._max_sessions:
                    self._sessions = self._sessions[-self._max_sessions:]
                
                logger.info(f"[状态管理器] 结束会话: {self._current_session.session_id}")
                self._current_session = None
    
    def get_current_session(self) -> Optional[TradingSession]:
        """获取当前会话"""
        with self._state_lock:
            return self._current_session
    
    def get_recent_sessions(self, limit: int = 10) -> List[TradingSession]:
        """获取最近的会话"""
        with self._state_lock:
            return self._sessions[-limit:] if self._sessions else []
    
    # =========================================================================
    # 决策步骤管理
    # =========================================================================
    
    def add_decision_step(
        self,
        phase: DecisionPhase,
        model: str,
        description: str,
        input_summary: str,
        output_summary: str,
        metadata: Dict[str, Any] = None
    ) -> DecisionStep:
        """添加决策步骤"""
        with self._state_lock:
            if not self._current_session:
                # 如果没有活跃会话，创建一个
                self.start_session("UNKNOWN")
            
            step = DecisionStep(
                step_id=str(uuid.uuid4())[:8],
                phase=phase,
                model=model,
                description=description,
                input_summary=input_summary,
                output_summary=output_summary,
                metadata=metadata or {}
            )
            
            self._current_session.add_step(step)
            
            # 同时更新状态
            self._current_session.status = BotStatus.ANALYZING
            
            logger.info(f"[状态管理器] 添加决策步骤: {phase.value} - {model}")
            return step
    
    def get_decision_log(self, minutes: int = 5) -> List[Dict[str, Any]]:
        """获取决策日志（用于问答）"""
        with self._state_lock:
            if not self._current_session:
                return []
            
            recent_steps = self._current_session.get_recent_steps(minutes)
            return [
                {
                    "step_id": s.step_id,
                    "phase": s.phase.value,
                    "model": s.model,
                    "description": s.description,
                    "input": s.input_summary,
                    "output": s.output_summary,
                    "timestamp": s.timestamp.isoformat(),
                    "metadata": s.metadata
                }
                for s in recent_steps
            ]
    
    # =========================================================================
    # 最终决策管理
    # =========================================================================
    
    def set_final_decision(self, decision: Dict[str, Any]):
        """设置最终决策"""
        with self._state_lock:
            if self._current_session:
                self._current_session.final_decision = decision
                self._current_session.current_phase = DecisionPhase.COMPLETE
                self._current_session.status = BotStatus.RUNNING
                logger.info(f"[状态管理器] 设置最终决策: {decision.get('action', 'UNKNOWN')}")
    
    def get_current_decision(self) -> Optional[Dict[str, Any]]:
        """获取当前决策"""
        with self._state_lock:
            return self._current_session.final_decision if self._current_session else None
    
    # =========================================================================
    # 市场数据
    # =========================================================================
    
    def update_market_data(self, data: Dict[str, Any]):
        """更新市场数据"""
        with self._state_lock:
            if self._current_session:
                self._current_session.market_data.update(data)
    
    def get_market_data(self) -> Dict[str, Any]:
        """获取市场数据"""
        with self._state_lock:
            return self._current_session.market_data.copy() if self._current_session else {}
    
    # =========================================================================
    # 聊天历史
    # =========================================================================
    
    def add_chat_message(self, role: str, content: str, context: Dict[str, Any] = None):
        """添加聊天消息"""
        with self._state_lock:
            message = ChatMessage(
                message_id=str(uuid.uuid4())[:8],
                role=role,
                content=content,
                context=context or {}
            )
            self._chat_history.append(message)
            
            # 修剪历史
            if len(self._chat_history) > self._max_chat_history:
                self._chat_history = self._chat_history[-self._max_chat_history:]
            
            return message
    
    def get_chat_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取聊天历史"""
        with self._state_lock:
            recent = self._chat_history[-limit:]
            return [
                {
                    "message_id": m.message_id,
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat()
                }
                for m in recent
            ]
    
    # =========================================================================
    # 配置管理
    # =========================================================================
    
    def update_config(self, **kwargs):
        """更新配置"""
        with self._state_lock:
            self._config.update(kwargs)
            logger.info(f"[状态管理器] 配置已更新: {kwargs}")
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        with self._state_lock:
            return self._config.copy()
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        with self._state_lock:
            return self._config.get(key, default)
    
    # =========================================================================
    # 状态管理
    # =========================================================================
    
    def set_status(self, status: BotStatus):
        """设置状态"""
        with self._state_lock:
            if self._current_session:
                self._current_session.status = status
            logger.info(f"[状态管理器] 状态更新: {status.value}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        with self._state_lock:
            if not self._current_session:
                return {
                    "status": BotStatus.IDLE.value,
                    "phase": DecisionPhase.IDLE.value,
                    "ticker": None,
                    "session_id": None
                }
            
            return {
                "status": self._current_session.status.value,
                "phase": self._current_session.current_phase.value,
                "ticker": self._current_session.ticker,
                "session_id": self._current_session.session_id,
                "decision_steps_count": len(self._current_session.decision_steps),
                "has_decision": self._current_session.final_decision is not None
            }
    
    # =========================================================================
    # 问答队列
    # =========================================================================
    
    async def enqueue_question(self, question: Dict[str, Any]):
        """将问题加入队列"""
        await self._pending_questions.put(question)
        logger.info(f"[状态管理器] 问题已加入队列: {question.get('question', '')[:50]}")
    
    async def dequeue_question(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """从队列取出问题"""
        try:
            return await asyncio.wait_for(self._pending_questions.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
    
    def get_pending_question_count(self) -> int:
        """获取待处理问题数量"""
        return self._pending_questions.qsize()


# 全局单例
_trading_state: Optional[TradingStateManager] = None


def get_trading_state() -> TradingStateManager:
    """获取交易状态管理器单例"""
    global _trading_state
    if _trading_state is None:
        _trading_state = TradingStateManager()
    return _trading_state
