"""
AI TradeBot - Discord 协作工作流

监听 Discord Bot 消息，解析 Clawdbot 响应，并将结果发送到 Showcase
"""
import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime

from core.comms.discord_client import ClawdbotResponse, send_discord_analysis_request
from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# Discord 工作流处理器
# =============================================================================

class DiscordWorkflowHandler:
    """
    Discord 工作流处理器

    处理从 Discord Bot 收到的 Clawdbot 响应
    """

    def __init__(self, showcase_callback=None):
        """初始化处理器"""
        self.showcase_callback = showcase_callback
        logger.info("[Discord工作流] 初始化完成")

    async def handle_clawdbot_response(self, response: ClawdbotResponse):
        """
        处理 Clawdbot 响应

        Args:
            response: Clawdbot 响应
        """
        logger.info(
            f"[Discord工作流] 收到分析结果: "
            f"{response.ticker} - {response.fair_value_range}"
        )

        # 广播到 Showcase（通过 WebSocket）
        if self.showcase_callback:
            from core.api.app import manager as app_manager

            # 构造广播消息
            broadcast_data = {
                "type": "valuation_update",
                "data": {
                    "ticker": response.ticker,
                    "fair_value_range": response.fair_value_range,
                    "pe_ratio": response.pe_ratio if response.pe_ratio else None,
                    "growth_expectation": response.growth_expectation,
                    "risk_factors": response.risk_factors,
                },
                "timestamp": response.timestamp,
            }

            # 广播到所有连接的 WebSocket 客户端
            for ws in app_manager.active_connections.copy():
                try:
                    await ws.send_json(broadcast_data)
                except Exception as e:
                    logger.error(f"WebSocket 广播失败: {e}")

        async def send_analysis_request(self, ticker: str, event_description: str):
        """
        发送分析请求到 Discord

        Args:
            ticker: 股票代码
            event_description: 事件描述
        """
        logger.info(f"[Discord工作流] 发送分析请求: {ticker}")

        await send_discord_analysis_request(
            ticker=ticker,
            event_description=event_description,
            valuation_context="需要深度估值分析",
            reply_to_message=None,  # 让 Clawdbot 决定回复频道
        )

    async def process_discord_message(self, message_data: Dict[str, Any]):
        """
        处理 Discord 消息（从 core/api/app.py 传入）

        Args:
            message_data: Discord 消息数据
        """
        # 解析消息类型
        msg_type = message_data.get("type", "")
        content = message_data.get("content", "")

        if msg_type == "clawbot_response":
            try:
                # 解析 Clawdbot 响应
                response_data = json.loads(content)

                response = ClawdbotResponse(
                    success=response_data.get("success", False),
                    analysis_id=response_data.get("analysis_id", ""),
                    ticker=response_data.get("ticker", ""),
                    fair_value_range=response_data.get("fair_value_range", {}),
                    pe_ratio=response_data.get("pe_ratio"),
                    growth_expectation=response_data.get("growth_expectation"),
                    risk_factors=response_data.get("risk_factors", []),
                    reasoning=response_data.get("reasoning", ""),
                    timestamp=response_data.get("timestamp", ""),
                )

                await self.handle_clawdbot_response(response)

            elif msg_type == "valuation_update":
                # 估值更新通知（用于计算完成后）
                logger.info(f"估值更新: {content}")

        except Exception as e:
            logger.error(f"[Discord工作流] 消息处理异常: {e}")


# =============================================================================
# 全局处理器实例
# =============================================================================

_discord_workflow: Optional[DiscordWorkflowHandler] = None


def get_discord_workflow() -> DiscordWorkflowHandler:
    """获取全局 Discord 工作流处理器"""
    global _discord_workflow
    if _discord_workflow is None:
        _discord_workflow = DiscordWorkflowHandler()
    return _discord_workflow


# =============================================================================
# 便捷函数
# =============================================================================

async def start_discord_workflow(showcase_callback=None):
    """启动 Discord 工作流"""
    workflow = get_discord_workflow()
    if workflow:
        workflow.showcase_callback = showcase_callback
        logger.info("[Discord工作流] 已启动")
    else:
        logger.warning("[Discord工作流] 未配置")


async def send_discord_analysis(ticker: str, event_description: str):
    """发送 Discord 分析请求"""
    workflow = get_discord_workflow()
    if workflow:
        await workflow.send_analysis_request(ticker, event_description)
    else:
        logger.warning("Discord 工作流未配置")


async def process_discord_message(message_data: Dict[str, Any]):
    """处理 Discord 消息（供 API 调用）"""
    workflow = get_discord_workflow()
    if workflow:
        await workflow.process_discord_message(message_data)
    else:
        logger.warning("Discord 工作流未配置")
