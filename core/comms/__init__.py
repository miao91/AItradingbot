"""
AI TradeBot - 智能体通信模块 (OpenClaw 集成版)

整合 Discord Bot 通信桥接，实现与 Clawdbot 的标准化交互
"""
from .discord_client import (
    AItradingBotClient,
    get_discord_client,
    start_discord_bot,
    stop_discord_bot,
    ClawdbotAnalysisData,
    AnalysisRequest,
)
from .discord_broker import (
    DiscordBroker,
    get_discord_broker,
    ClawdbotValuationData,
)

__all__ = [
    "AItradingBotClient",
    "get_discord_client",
    "start_discord_bot",
    "stop_discord_bot",
    "ClawdbotAnalysisData",
    "AnalysisRequest",
    "DiscordBroker",
    "get_discord_broker",
    "ClawdbotValuationData",
]
