"""
AI TradeBot - Discord A2A 自动代理（冷处理版）

实现与 Clawdbot 的自动化代理通信：
1. 自动寻址：评分≥7的标的自动封装JSON请求并发送给CLAWDBOT_USER_ID
2. 数据拦截：异步监听频道，捕获Clawdbot的JSON回复
3. 解析 fair_value_range、pe_analysis 及 projected_data
4. 将数据注入事件总线

⚠️ 冷处理模式：
- 默认 is_active=False，不启动 Discord 连接
- 保留完整代码，等需要时在 .env 设置 ENABLE_DISCORD_BROKER=true 即可激活
- 总工决策："代码先行，模块挂起"，确保内置 AI 引擎全功率运行
"""
import asyncio
import json
import os
from typing import Optional, Dict, Any, Callable, Awaitable, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

import discord
from discord.ext import commands, tasks
from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

DISCORD_BROKER_CONFIG = {
    "bot_token": os.getenv("DISCORD_BOT_TOKEN", ""),
    "channel_id": os.getenv("DISCORD_CHANNEL_ID", ""),
    "clawdbot_user_id": os.getenv("CLAWDBOT_USER_ID", ""),
    "guild_id": os.getenv("DISCORD_GUILD_ID", ""),
    "command_prefix": "!",
    "classification_threshold": float(os.getenv("NEWS_CLASSIFICATION_THRESHOLD", "7.0")),
    # 冷处理开关：默认 False，需要显式启用
    "is_active": os.getenv("ENABLE_DISCORD_BROKER", "false").lower() == "true",
}


# =============================================================================
# 数据类
# =============================================================================

class ValuationLevel(Enum):
    """估值级别"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class ClawdbotValuationData:
    """Clawdbot 估值数据"""
    ticker: str
    fair_value_min: float
    fair_value_max: float
    current_price: float
    pe_ratio: Optional[float] = None
    industry_pe: Optional[float] = None
    growth_expectation: Optional[str] = None  # high, medium, low
    consensus: float = 50.0  # 机构共识度 0-100
    risk_factors: List[str] = field(default_factory=list)
    reasoning: str = ""
    projected_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AnalysisRequest:
    """分析请求"""
    ticker: str
    score: float
    valuation_level: str
    event_description: str
    source: str
    category: str
    duration_estimate: str
    sentiment: str


# =============================================================================
# Discord Broker 自动代理
# =============================================================================

class DiscordBroker:
    """
    Discord 自动代理（冷处理版）

    实现与 Clawdbot 的自动化交互：
    - 自动发送高分新闻的分析请求
    - 监听并解析 Clawdbot 的估值响应
    - 将数据注入事件总线

    ⚠️ 冷处理模式：
    - 默认不启动 Discord 连接
    - 在 .env 设置 ENABLE_DISCORD_BROKER=true 激活
    """

    def __init__(self, config: Optional[Dict] = None):
        """初始化代理"""
        self.config = config or DISCORD_BROKER_CONFIG
        self.running = False
        self.is_active = self.config.get("is_active", False)
        self.client: Optional[discord.Client] = None
        self.event_handler: Optional[Callable] = None
        self.pending_requests: Dict[str, AnalysisRequest] = {}

        # 冷处理模式日志
        if not self.is_active:
            logger.info(
                "[DiscordBroker] 🌙 冷处理模式: Expert System (Standby) - "
                "代码保留但未激活 Discord 连接，内置 AI 引擎全功率运行"
            )
            logger.info(
                "[DiscordBroker] 💡 提示: 在 .env 设置 ENABLE_DISCORD_BROKER=true 即可激活"
            )
        else:
            # 验证配置（仅在激活时）
            if not all([
                self.config["bot_token"],
                self.config["channel_id"],
                self.config["clawdbot_user_id"]
            ]):
                logger.warning("[DiscordBroker] 配置不完整，自动代理将无法启动")
                self.is_active = False

    async def start(self, event_handler: Optional[Callable] = None):
        """启动自动代理（冷处理：如果 is_active=False 则不启动）"""
        # 冷处理检查
        if not self.is_active:
            logger.info(
                "[DiscordBroker] 🌙 Expert System 处于静默模式 - "
                "跳过 Discord 连接初始化"
            )
            return False

        if self.running:
            logger.warning("[DiscordBroker] 已在运行中")
            return False

        if not self._validate_config():
            logger.error("[DiscordBroker] 配置验证失败")
            return False

        self.event_handler = event_handler
        self.running = True

        # 初始化 Discord 客户端
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True

        self.client = discord.Client(intents=intents)

        # 注册事件处理
        @self.client.event
        async def on_ready():
            logger.info(
                f"[DiscordBroker] 已启动: "
                f"{self.client.user} "
                f"监听频道={self.config['channel_id']}"
            )

        @self.client.event
        async def on_message(message: discord.Message):
            await self._handle_message(message)

        # 启动客户端
        try:
            await self.client.start(self.config["bot_token"])
        except Exception as e:
            logger.error(f"[DiscordBroker] 启动失败: {e}")
            self.running = False

    async def stop(self):
        """停止代理"""
        self.running = False
        if self.client:
            await self.client.close()
        logger.info("[DiscordBroker] 已停止")

    def _validate_config(self) -> bool:
        """验证配置"""
        required = ["bot_token", "channel_id", "clawdbot_user_id"]
        for key in required:
            if not self.config.get(key):
                logger.error(f"[DiscordBroker] 缺少必需配置: {key}")
                return False
        return True

    async def submit_analysis_request(self, request: AnalysisRequest):
        """
        提交分析请求到 Clawdbot（冷处理：如果 is_active=False 则跳过）

        Args:
            request: 分析请求
        """
        # 冷处理检查
        if not self.is_active:
            logger.debug(
                "[DiscordBroker] 🌙 Expert System 静默中 - "
                f"跳过分析请求: {request.ticker}"
            )
            return

        if not self.running or not self.client:
            logger.warning("[DiscordBroker] 代理未运行，无法提交请求")
            return

        if request.score < self.config["classification_threshold"]:
            logger.debug(
                f"[DiscordBroker] 评分 {request.score} 低于阈值 "
                f"({self.config['classification_threshold']})，跳过"
            )
            return

        try:
            # 构建标准 JSON 格式
            request_data = {
                "action": "analyze",
                "ticker": request.ticker,
                "event_description": request.event_description,
                "score": request.score,
                "valuation_level": request.valuation_level,
                "category": request.category,
                "sentiment": request.sentiment,
                "duration_estimate": request.duration_estimate,
                "source": request.source,
                "request_id": f"req_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "timestamp": datetime.now().isoformat(),
            }

            # 获取频道
            channel = self.client.get_channel(int(self.config["channel_id"]))
            if not channel:
                logger.error(f"[DiscordBroker] 频道 {self.config['channel_id']} 不存在")
                return

            # 发送 JSON（使用代码块保持格式）
            content = f"```json\n{json.dumps(request_data, indent=2, ensure_ascii=False)}\n```"
            await channel.send(content)

            # 记录待处理请求
            self.pending_requests[request_data["request_id"]] = request

            logger.info(
                f"[DiscordBroker] 已发送分析请求: {request.ticker} "
                f"(评分={request.score}, 级别={request.valuation_level})"
            )

        except Exception as e:
            logger.error(f"[DiscordBroker] 发送请求失败: {e}")

    async def _handle_message(self, message: discord.Message):
        """处理接收到的消息"""
        # 仅处理指定频道的消息
        if str(message.channel.id) != str(self.config["channel_id"]):
            return

        # 忽略 Bot 自己的消息
        if message.author.bot:
            return

        # 检查是否来自 Clawdbot
        if str(message.author.id) != str(self.config["clawdbot_user_id"]):
            return

        # 尝试解析 Clawdbot 的 JSON 响应
        await self._parse_clawdbot_response(message)

    async def _parse_clawdbot_response(self, message: discord.Message):
        """解析 Clawdbot 的估值响应"""
        try:
            content = message.content.strip()

            # 尝试提取 JSON
            if content.startswith("```json"):
                json_str = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                json_str = content.replace("```", "").strip()
            else:
                json_str = content

            data = json.loads(json_str)

            # 验证是 Clawdbot 响应（包含 analysis_id 或 ticker）
            if not data.get("ticker") and not data.get("analysis_id"):
                return

            # 解析估值数据
            valuation = ClawdbotValuationData(
                ticker=data.get("ticker", ""),
                fair_value_min=float(data.get("fair_value_range", {}).get("min", 0)),
                fair_value_max=float(data.get("fair_value_range", {}).get("max", 0)),
                current_price=float(data.get("current_price", 0)),
                pe_ratio=data.get("pe_ratio"),
                industry_pe=data.get("industry_pe"),
                growth_expectation=data.get("growth_expectation"),
                consensus=float(data.get("consensus", 50)),
                risk_factors=data.get("risk_factors", []),
                reasoning=data.get("reasoning", ""),
                projected_data=data.get("projected_data", {}),
                timestamp=data.get("timestamp", datetime.now().isoformat()),
            )

            logger.info(
                f"[DiscordBroker] 收到 Clawdbot 响应: "
                f"{valuation.ticker} "
                f"估值区间={valuation.fair_value_min}-{valuation.fair_value_max}"
            )

            # 触发事件处理
            if self.event_handler:
                await self.event_handler(valuation)

        except json.JSONDecodeError as e:
            logger.debug(f"[DiscordBroker] JSON 解析失败: {e}")
        except Exception as e:
            logger.error(f"[DiscordBroker] 处理响应异常: {e}")

    async def send_status_update(self, status: str, details: str = ""):
        """发送状态更新到频道"""
        if not self.running or not self.client:
            return

        try:
            channel = self.client.get_channel(int(self.config["channel_id"]))
            if not channel:
                return

            message = {
                "action": "status",
                "status": status,
                "details": details,
                "timestamp": datetime.now().isoformat(),
            }

            content = f"```json\n{json.dumps(message, indent=2, ensure_ascii=False)}\n```"
            await channel.send(content)

        except Exception as e:
            logger.error(f"[DiscordBroker] 发送状态失败: {e}")


# =============================================================================
# 全局单例
# =============================================================================

_discord_broker: Optional[DiscordBroker] = None


def get_discord_broker() -> DiscordBroker:
    """获取全局 Discord Broker 实例"""
    global _discord_broker
    if _discord_broker is None:
        _discord_broker = DiscordBroker()
    return _discord_broker


async def start_discord_broker(callback=None):
    """
    启动 Discord Broker（冷处理：如果未激活则跳过）

    Returns:
        bool: 是否成功启动（False 表示冷处理模式）
    """
    broker = get_discord_broker()
    result = await broker.start(event_handler=callback)
    return result if result is not None else broker.is_active


def is_discord_broker_active() -> bool:
    """
    检查 Discord Broker 是否处于激活状态

    Returns:
        bool: True=已激活，False=冷处理模式
    """
    broker = get_discord_broker()
    return broker.is_active


async def stop_discord_broker():
    """停止 Discord Broker"""
    global _discord_broker
    if _discord_broker:
        await _discord_broker.stop()


async def submit_analysis_request(
    ticker: str,
    score: float,
    valuation_level: str,
    event_description: str,
    source: str = "",
    category: str = "other",
    duration_estimate: str = "unknown",
    sentiment: str = "neutral",
):
    """提交分析请求"""
    broker = get_discord_broker()

    request = AnalysisRequest(
        ticker=ticker,
        score=score,
        valuation_level=valuation_level,
        event_description=event_description,
        source=source,
        category=category,
        duration_estimate=duration_estimate,
        sentiment=sentiment,
    )

    await broker.submit_analysis_request(request)


# =============================================================================
# 主程序（用于测试）
# =============================================================================

async def main():
    """主程序（用于测试）"""
    async def valuation_handler(valuation: ClawdbotValuationData):
        print(f"\n[收到估值数据]")
        print(f"  标的: {valuation.ticker}")
        print(f"  估值区间: {valuation.fair_value_min} - {valuation.fair_value_max}")
        print(f"  PE比率: {valuation.pe_ratio}")
        print(f"  增长预期: {valuation.growth_expectation}")
        print(f"  共识度: {valuation.consensus}%")
        print(f"  推理: {valuation.reasoning[:100]}...")
        print("-" * 50)

    # 启动 Broker
    await start_discord_broker(event_handler=valuation_handler)

    # 测试发送请求
    await asyncio.sleep(2)

    test_request = AnalysisRequest(
        ticker="600000.SH",
        score=8.5,
        valuation_level="high",
        event_description="测试：浦发银行发布重大资产重组公告",
        source="Tushare",
        category="m_and_a",
        duration_estimate="1-2周",
        sentiment="positive",
    )

    broker = get_discord_broker()
    await broker.submit_analysis_request(test_request)

    # 保持运行
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await stop_discord_broker()


if __name__ == "__main__":
    asyncio.run(main())
