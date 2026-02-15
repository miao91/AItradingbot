"""
AI TradeBot - FastAPI 主应用

提供 Web API 服务，配置 CORS 支持外部网站访问
支持 WebSocket 实时推送
"""
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
import json
from typing import Set
from datetime import datetime

from core.api.v1 import router as v1_router
from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# WebSocket 连接管理
# =============================================================================

class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket 已连接，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket 已断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        if not self.active_connections:
            return

        data = json.dumps(message, ensure_ascii=False)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except Exception as e:
                logger.error(f"广播消息失败: {e}")
                disconnected.append(connection)

        # 清理断开的连接
        for conn in disconnected:
            self.disconnect(conn)

    async def send_personal(self, message: dict, websocket: WebSocket):
        """发送消息到单个连接"""
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.error(f"发送个人消息失败: {e}")


# 全局连接管理器
manager = ConnectionManager()


# =============================================================================
# 实时事件推送工具
# =============================================================================

async def broadcast_perception_start(source: str = "未知来源"):
    """广播感知阶段开始"""
    await manager.broadcast({
        "type": "perception_start",
        "data": {
            "source": source,
            "timestamp": datetime.now().isoformat()
        }
    })


async def broadcast_perception_captured(event_id: str, ticker: str, title: str, url: str, raw_data: dict = None):
    """广播感知捕获事件"""
    await manager.broadcast({
        "type": "perception_captured",
        "data": {
            "event_id": event_id,
            "ticker": ticker,
            "title": title,
            "url": url,
            "raw_data": raw_data,
            "summary": title[:100],
            "timestamp": datetime.now().isoformat()
        }
    })


async def broadcast_analysis_start(event_id: str, ticker: str):
    """广播分析阶段开始"""
    await manager.broadcast({
        "type": "analysis_start",
        "data": {
            "event_id": event_id,
            "ticker": ticker,
            "timestamp": datetime.now().isoformat()
        }
    })


async def broadcast_ai_thinking(event_id: str, model: str, step: str):
    """广播AI思考过程"""
    await manager.broadcast({
        "type": "ai_thinking",
        "data": {
            "event_id": event_id,
            "model": model,
            "step": step,
            "timestamp": datetime.now().isoformat()
        }
    })


async def broadcast_decision_complete(event_id: str, ticker: str, action: str, exit_plan: dict, reasoning: str):
    """广播决策完成"""
    await manager.broadcast({
        "type": "decision_complete",
        "data": {
            "event_id": event_id,
            "ticker": ticker,
            "action": action,
            "exit_plan": exit_plan,
            "reasoning": reasoning,
            "timestamp": datetime.now().isoformat()
        }
    })


async def broadcast_event_filtered(reason: str, ticker: str = None):
    """广播事件被过滤"""
    await manager.broadcast({
        "type": "event_filtered",
        "data": {
            "ticker": ticker,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
    })


# 兼容旧接口
async def broadcast_new_event(event_id: str, ticker: str, status: str, summary: str):
    """广播新事件到所有 WebSocket 连接（兼容旧接口）"""
    await manager.broadcast({
        "type": "perception_captured",
        "data": {
            "event_id": event_id,
            "ticker": ticker,
            "title": summary,
            "url": "",
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    })


async def broadcast_event_update(event_id: str, status: str, update_type: str = "status_change"):
    """广播事件状态更新（兼容旧接口）"""
    await manager.broadcast({
        "type": update_type,
        "data": {
            "event_id": event_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
    })


# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("=" * 60)
    logger.info("AI TradeBot API 启动中...")
    logger.info("=" * 60)

    # 初始化数据库连接
    from core.database.session import db_manager
    await db_manager.initialize_engine()
    logger.info("数据库连接已初始化")

    yield

    # 关闭
    logger.info("正在关闭数据库连接...")
    await db_manager.close()
    logger.info("API 服务已停止")


# =============================================================================
# App Factory
# =============================================================================

def create_app() -> FastAPI:
    """创建 FastAPI 应用"""

    app = FastAPI(
        title="AI TradeBot API",
        description="AI 量化交易系统 - 以终为始",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # =============================================================================
    # CORS 配置 - 允许外部网站访问
    # =============================================================================

    # 开发环境允许所有来源
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 开发环境允许所有来源
        allow_credentials=False,  # 不能与 * 同时使用
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.info("CORS 已配置: 允许所有来源 (开发模式)")

    # =============================================================================
    # 路由注册
    # =============================================================================

    # v1 API
    app.include_router(v1_router)

    # =============================================================================
    # Exception Handlers
    # =============================================================================

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": str(exc) if logger.level <= 10 else "服务暂时不可用"
            }
        )

    # =============================================================================
    # Root Endpoints
    # =============================================================================

    @app.get("/", tags=["root"])
    async def root():
        """根路径 - API 信息"""
        return {
            "service": "AI TradeBot API",
            "version": "1.0.0",
            "status": "running",
            "description": "AI 量化交易系统 - 以终为始",
            "endpoints": {
                "docs": "/docs",
                "redoc": "/redoc",
                "public_api": "/api/v1/public/active_events",
                "health": "/health"
            }
        }

    @app.get("/health", tags=["root"])
    async def health():
        """健康检查"""
        return {
            "status": "healthy",
            "service": "ai-tradebot-api",
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }

    # =============================================================================
    # WebSocket 实时推送
    # =============================================================================

    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket):
        """
        实时事件推送 WebSocket

        连接后可接收：
        - new_event: 新交易事件
        - status_change: 事件状态变更
        - ai_analysis: AI 分析完成

        消息格式：{"type": "...", "data": {...}}
        """
        await manager.connect(websocket)

        try:
            # 发送欢迎消息
            await manager.send_personal({
                "type": "connected",
                "data": {
                    "message": "已连接到 AI TradeBot 实时推送",
                    "timestamp": datetime.now().isoformat()
                }
            }, websocket)

            # 保持连接并接收客户端消息（心跳等）
            while True:
                data = await websocket.receive_text()

                # 处理客户端心跳
                if data == "ping":
                    await manager.send_personal({"type": "pong"}, websocket)

        except WebSocketDisconnect:
            manager.disconnect(websocket)
            logger.info("WebSocket 客户端主动断开")
        except Exception as e:
            logger.error(f"WebSocket 异常: {e}")
            manager.disconnect(websocket)

    return app


# =============================================================================
# App Instance
# =============================================================================

app = create_app()


# =============================================================================
# Main Entry
# =============================================================================

def main():
    """启动 API 服务器"""
    uvicorn.run(
        "core.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
