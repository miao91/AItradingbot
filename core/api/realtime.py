"""
AI TradeBot - 实时问答与状态API

提供：
1. 实时状态查询
2. 问答历史管理
3. 动态配置更新
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio

from shared.logging import get_logger
from shared.trading_state import get_trading_state, DecisionPhase


logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])


# =============================================================================
# 状态查询API
# =============================================================================

@router.get("/status")
async def get_status():
    """
    获取当前交易状态
    
    返回当前机器人状态、当前决策阶段、活跃会话信息
    """
    state = get_trading_state()
    return state.get_status()


@router.get("/decision-log")
async def get_decision_log(minutes: int = Query(5, ge=1, le=60)):
    """
    获取决策日志
    
    获取最近N分钟的完整决策过程，用于问答系统的上下文
    """
    state = get_trading_state()
    return {
        "decision_steps": state.get_decision_log(minutes),
        "current_decision": state.get_current_decision(),
        "market_data": state.get_market_data()
    }


@router.get("/config")
async def get_config():
    """获取当前配置"""
    state = get_trading_state()
    return state.get_config()


@router.post("/config")
async def update_config(config: Dict[str, Any]):
    """
    更新配置
    
    支持动态更新风险等级等配置
    """
    state = get_trading_state()
    state.update_config(**config)
    return {"success": True, "config": state.get_config()}


# =============================================================================
# 聊天历史API
# =============================================================================

@router.get("/chat/history")
async def get_chat_history(limit: int = Query(20, ge=1, le=100)):
    """
    获取聊天历史
    """
    state = get_trading_state()
    return {
        "messages": state.get_chat_history(limit)
    }


@router.post("/chat/question")
async def submit_question(question: str, context: Optional[Dict[str, Any]] = None):
    """
    提交问题（异步处理）
    
    问题会被加入队列，由后台任务处理
    不阻塞主交易流程
    """
    state = get_trading_state()
    
    # 添加用户消息到历史
    state.add_chat_message("user", question, context or {})
    
    # 加入待处理队列
    await state.enqueue_question({
        "question": question,
        "context": context or {},
        "timestamp": datetime.now().isoformat()
    })
    
    return {
        "success": True,
        "message": "问题已提交，将在后台处理",
        "message_id": str(uuid.uuid4())[:8]
    }


@router.get("/chat/pending")
async def get_pending_count():
    """获取待处理问题数量"""
    state = get_trading_state()
    return {"pending_count": state.get_pending_question_count()}


# 导入uuid用于生成消息ID
import uuid


# =============================================================================
# WebSocket 问答连接
# =============================================================================

class QAController:
    """问答WebSocket控制器"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"QA WebSocket 已连接，当前连接数: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"QA WebSocket 已断开，当前连接数: {len(self.active_connections)}")
    
    async def send_answer(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送答案失败: {e}")
    
    async def broadcast_to_all(self, message: dict):
        """广播到所有连接"""
        for conn in self.active_connections[:]:  # 复制列表避免迭代中修改
            try:
                await conn.send_json(message)
            except Exception as e:
                logger.error(f"广播失败: {e}")
                self.disconnect(conn)


qa_controller = QAController()


@router.websocket("/ws/qa")
async def websocket_qa(websocket: WebSocket):
    """
    实时问答WebSocket
    
    连接后可以：
    - 发送问题: {"type": "question", "content": "..."}
    - 接收答案: {"type": "answer", "content": "...", "sources": [...]}
    - 接收状态更新: {"type": "status", "data": {...}}
    
    这个连接是独立的，不影响主交易流程
    """
    await qa_controller.connect(websocket)
    state = get_trading_state()
    
    try:
        # 发送欢迎消息
        await qa_controller.send_answer({
            "type": "connected",
            "message": "已连接到AI TradeBot问答系统",
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        # 同时发送当前状态
        await qa_controller.send_answer({
            "type": "status",
            "data": state.get_status(),
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        # 保持连接并处理消息
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await qa_controller.send_answer({
                    "type": "error",
                    "message": "无效的JSON格式"
                }, websocket)
                continue
            
            msg_type = message.get("type")
            
            if msg_type == "question":
                question = message.get("content", "")
                
                # 添加到聊天历史
                state.add_chat_message("user", question)
                
                # 立即返回"处理中"状态
                await qa_controller.send_answer({
                    "type": "processing",
                    "message": "正在分析您的问题...",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
                
                # 获取决策上下文
                decision_log = state.get_decision_log(5)  # 最近5分钟
                current_decision = state.get_current_decision()
                market_data = state.get_market_data()
                
                # 在后台处理问题（不阻塞）
                asyncio.create_task(
                    process_question(
                        question=question,
                        decision_log=decision_log,
                        current_decision=current_decision,
                        market_data=market_data,
                        websocket=websocket,
                        state=state
                    )
                )
            
            elif msg_type == "ping":
                await qa_controller.send_answer({"type": "pong"}, websocket)
            
            elif msg_type == "get_status":
                await qa_controller.send_answer({
                    "type": "status",
                    "data": state.get_status()
                }, websocket)
            
            else:
                await qa_controller.send_answer({
                    "type": "error",
                    "message": f"未知的消息类型: {msg_type}"
                }, websocket)
    
    except WebSocketDisconnect:
        qa_controller.disconnect(websocket)
    except Exception as e:
        logger.error(f"QA WebSocket异常: {e}")
        qa_controller.disconnect(websocket)


async def process_question(
    question: str,
    decision_log: List[Dict],
    current_decision: Optional[Dict],
    market_data: Dict,
    websocket: WebSocket,
    state
):
    """后台处理问题"""
    try:
        # 构建上下文
        context_parts = []
        
        if decision_log:
            context_parts.append("=== 最近决策过程 ===")
            for step in decision_log[-5:]:  # 最近5步
                context_parts.append(
                    f"[{step['phase']}] {step['model']}: {step['description']}"
                )
                context_parts.append(f"  输入: {step['input'][:100]}")
                context_parts.append(f"  输出: {step['output'][:100]}")
        
        if current_decision:
            context_parts.append("\n=== 当前决策 ===")
            context_parts.append(str(current_decision))
        
        if market_data:
            context_parts.append("\n=== 市场数据 ===")
            context_parts.append(str(market_data)[:500])
        
        context = "\n".join(context_parts) if context_parts else "暂无决策上下文"
        
        # 调用AI生成答案（简化版，实际应该调用LLM）
        answer = generate_answer(question, context)
        
        # 发送答案
        await qa_controller.send_answer({
            "type": "answer",
            "content": answer,
            "sources": {
                "decision_steps": len(decision_log),
                "has_current_decision": current_decision is not None
            },
            "timestamp": datetime.now().isoformat()
        }, websocket)
        
        # 添加助手消息到历史
        state.add_chat_message("assistant", answer)
        
    except Exception as e:
        logger.error(f"处理问题失败: {e}")
        await qa_controller.send_answer({
            "type": "error",
            "message": f"处理问题时出错: {str(e)}"
        }, websocket)


def generate_answer(question: str, context: str) -> str:
    """
    生成答案（简化版）
    
    实际生产环境中应该调用LLM API
    """
    question_lower = question.lower()
    
    # 简单规则匹配
    if "为什么" in question or "why" in question_lower:
        if context and "决策" in context:
            return f"基于最近的决策过程，我理解您想知道决策的原因。\n\n{context[:500]}..."
        return "目前没有足够的决策信息来回答这个问题。"
    
    elif "建议" in question or "优化" in question or "optimize" in question_lower:
        return "我注意到您希望优化交易策略。当前系统支持以下调整：\n- 风险等级：low/medium/high\n- 最大仓位比例\n- 自动交易开关\n\n您想调整哪些参数？"
    
    elif "状态" in question or "status" in question_lower:
        state = get_trading_state()
        status = state.get_status()
        return f"当前系统状态：\n- 状态：{status.get('status', 'unknown')}\n- 阶段：{status.get('phase', 'unknown')}\n- 标的：{status.get('ticker', 'N/A')}"
    
    elif "决策" in question:
        state = get_trading_state()
        decision = state.get_current_decision()
        if decision:
            return f"当前决策：\n{json.dumps(decision, ensure_ascii=False, indent=2)}"
        return "目前没有活跃的决策。"
    
    else:
        # 默认回答
        return f"您的问题是：{question}\n\n当前决策上下文：\n{context[:800]}...\n\n如果您想了解更多关于当前交易状态的信息，请告诉我您具体想了解什么（例如：为什么买入、当前决策、优化建议等）。"


# =============================================================================
# K线数据API
# =============================================================================

@router.get("/kline")
async def get_kline(
    symbol: str = Query("000001.SH", description="股票代码"),
    days: int = Query(50, ge=10, le=300, description="K线天数")
):
    """
    获取K线数据
    
    使用项目现有的market_data模块获取真实K线数据
    """
    try:
        from perception.market_data import get_daily_bars
        
        # 计算日期范围
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days*1.5)).strftime("%Y%m%d")
        
        # 获取K线数据
        bars = get_daily_bars(symbol, start_date, end_date)
        
        if not bars:
            return {"error": "暂无数据", "symbol": symbol}
        
        # 转换为JSON格式
        data = []
        for bar in bars[-days:]:  # 最多返回days条
            data.append({
                "date": bar.trade_date,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "amount": bar.amount
            })
        
        return {
            "symbol": symbol,
            "bars": data,
            "count": len(data)
        }
        
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return {"error": str(e), "symbol": symbol}


# 导出qa_controller供广播使用
get_qa_controller = lambda: qa_controller
