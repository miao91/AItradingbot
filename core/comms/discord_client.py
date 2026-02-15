"""
AI TradeBot - Discord Bot 通讯桥接 (OpenClaw 集成版)

基于 OpenClaw 提供的 AItradingBot 逻辑，实现与 Clawdbot 的闭环对话
核心功能：
1. 监听 @AItradingBot analyze 命令
2. 通过 @提及方式转发给 CLAWDBOT_USER_ID
3. 捕获并解析 Clawdbot 的 JSON 响应
4. 格式化输出并同步到事件总线
"""
import asyncio
import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field

import discord
from discord.ext import commands
from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

DISCORD_CONFIG = {
    "bot_token": os.getenv("DISCORD_BOT_TOKEN", ""),
    "client_id": os.getenv("DISCORD_CLIENT_ID", ""),
    "client_secret": os.getenv("DISCORD_CLIENT_SECRET", ""),
    "channel_id": os.getenv("DISCORD_CHANNEL_ID", ""),
    "clawdbot_user_id": os.getenv("CLAWDBOT_USER_ID", "975399077120466965"),
    "guild_id": os.getenv("DISCORD_GUILD_ID", ""),
    "command_prefix": os.getenv("DISCORD_COMMAND_PREFIX", "@AItradingBot"),
    "analysis_trigger": os.getenv("ANALYSIS_TRIGGER", "analyze"),
}


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class ClawdbotAnalysisData:
    """Clawdbot 分析数据"""
    ticker: str
    fair_value_range: Dict[str, float]
    pe_ratio: Optional[float] = None
    industry_pe: Optional[float] = None
    growth_expectation: Optional[str] = None
    consensus: Optional[float] = None
    risk_factors: List[str] = field(default_factory=list)
    reasoning: Optional[str] = None
    projected_data: Dict[str, Any] = field(default_factory=dict)
    key_events: List[str] = field(default_factory=list)
    analysis_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AnalysisRequest:
    """分析请求"""
    ticker: str
    user_id: int
    username: str
    channel_id: int
    message_id: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# OpenClaw 风格的 Discord Bot 客户端
# =============================================================================

class AItradingBotClient(commands.Bot):
    """
    AI TradeBot Discord 客户端 (OpenClaw 集成版)

    实现：
    1. 监听 @AItradingBot analyze 命令
    2. 转发给 Clawdbot (CLAWDBOT_USER_ID)
    3. 捕获并解析响应
    4. 格式化输出并同步到事件总线
    """

    def __init__(self):
        # 配置 Intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True

        # 初始化 Bot
        super().__init__(
            command_prefix=DISCORD_CONFIG["command_prefix"],
            intents=intents,
            help_command=None,
        )

        self.config = DISCORD_CONFIG
        self.running = False
        self.event_handler = None
        self.pending_requests: Dict[str, AnalysisRequest] = {}

        # Clawdbot 用户引用
        self.clawdbot_user_id = int(self.config["clawdbot_user_id"])

        logger.info(
            f"[DiscordBot] 初始化 OpenClaw 客户端: "
            f"Clawdbot ID={self.clawdbot_user_id}"
        )

    async def start(self, event_handler=None):
        """启动机器人"""
        if self.running:
            logger.warning("[DiscordBot] 已在运行中")
            return

        self.event_handler = event_handler
        self.running = True

        try:
            await self.start(self.config["bot_token"])
            logger.info("[DiscordBot] Bot 已启动")

        except Exception as e:
            logger.error(f"[DiscordBot] 启动失败: {e}")
            self.running = False

    async def setup_hook(self):
        """Bot 启动后的钩子"""
        await self.tree.sync()

        # 设置自定义状态
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for @AItradingBot analyze"
            )
        )

        logger.info(
            f"[DiscordBot] Bot 就绪: "
            f"{self.user} (ID: {self.user.id})"
        )

    async def on_ready(self):
        """Bot 就绪事件"""
        logger.info(
            f"[DiscordBot] 已登录: {self.user} | "
            f"服务器: {len(self.guilds)} 个"
        )

    async def on_message(self, message: discord.Message):
        """
        处理消息事件（OpenClaw 风格）

        核心逻辑：
        1. 检测 @AItradingBot analyze 命令
        2. 提取股票代码
        3. @提及 Clawdbot 并转发请求
        4. 等待并捕获响应
        """
        # 忽略自己的消息
        if message.author == self.user or message.author.bot:
            return

        # 检查是否在指定频道
        if self.config["channel_id"]:
            try:
                if str(message.channel.id) != self.config["channel_id"]:
                    return
            except ValueError:
                pass  # channel_id 可能不是数字

        content = message.content.strip()

        # 检测命令：@AItradingBot analyze <TICKER>
        if self._is_analyze_command(content):
            ticker = self._extract_ticker(content)

            if ticker:
                await self._handle_analysis_request(message, ticker)
            else:
                await message.reply(
                    "❌ 请提供股票代码\n"
                    "用法: `@AItradingBot analyze 600000.SH`"
                )

        # 处理普通命令
        await self.process_commands(message)

    def _is_analyze_command(self, content: str) -> bool:
        """检查是否是分析命令"""
        trigger = self.config["analysis_trigger"]
        patterns = [
            f"{self.config['command_prefix']} {trigger}",
            f"{self.config['command_prefix']} {trigger} ".lower(),
        ]

        content_lower = content.lower()
        return any(pattern in content_lower for pattern in patterns)

    def _extract_ticker(self, content: str) -> Optional[str]:
        """从命令中提取股票代码"""
        parts = content.split()

        # 尝试提取分析命令后的代码
        trigger_idx = -1
        for i, part in enumerate(parts):
            if self.config["analysis_trigger"].lower() in part.lower():
                trigger_idx = i
                break

        if trigger_idx >= 0 and trigger_idx + 1 < len(parts):
            return parts[trigger_idx + 1].upper()

        return None

    async def _handle_analysis_request(self, message: discord.Message, ticker: str):
        """
        处理分析请求

        流程：
        1. 创建请求记录
        2. @提及 Clawdbot 并转发
        3. 等待响应（通过 on_message 检测）
        """
        request = AnalysisRequest(
            ticker=ticker,
            user_id=message.author.id,
            username=message.author.name,
            channel_id=message.channel.id,
            message_id=message.id,
        )

        # 记录待处理请求
        request_key = f"{ticker}_{message.author.id}_{int(datetime.now().timestamp())}"
        self.pending_requests[request_key] = request

        try:
            # 获取 Clawdbot 用户
            clawdbot_user = self.get_user(self.clawdbot_user_id)

            if not clawdbot_user:
                await message.reply(f"⚠️ 无法找到 Clawdbot (ID: {self.clawdbot_user_id})")
                return

            # 构建请求消息（OpenClaw 格式）
            request_content = (
                f"**分析请求**\n"
                f"```\n"
                f"{{\n"
                f'  "action": "analyze",\n'
                f'  "ticker": "{ticker}",\n'
                f'  "request_id": "{request_key}",\n'
                f'  "timestamp": "{request.timestamp}",\n'
                f'  "requested_by": "{request.username}"\n'
                f"}}\n"
                f"```\n"
            )

            # 发送请求，@提及 Clawdbot
            await message.channel.send(
                f"{clawdbot_user.mention} 请分析以下标的：\n"
                f"{request_content}"
            )

            logger.info(
                f"[DiscordBot] 已发送分析请求: {ticker} "
                f"(请求者: {request.username})"
            )

            # 发送确认消息
            confirm_msg = await message.reply(
                f"🔍 已将 **{ticker}** 转发给 Clawdbot 分析...\n"
                f"请稍候片刻，回复将在此频道显示。"
            )

            # 触发事件（通知系统）
            if self.event_handler:
                await self.event_handler({
                    "type": "analysis_requested",
                    "data": {
                        "ticker": ticker,
                        "request_id": request_key,
                        "user": request.username,
                        "timestamp": request.timestamp,
                    }
                })

        except Exception as e:
            logger.error(f"[DiscordBot] 发送分析请求失败: {e}")
            await message.reply(f"❌ 发送请求失败: {str(e)}")

    async def process_clawdbot_response(self, message: discord.Message):
        """
        处理 Clawdbot 的响应消息

        检测并解析来自 Clawdbot 的 JSON 响应
        """
        # 确认消息来自 Clawdbot
        if message.author.id != self.clawdbot_user_id:
            return

        content = message.content.strip()

        try:
            # 尝试提取 JSON（支持多种格式）
            analysis_data = self._parse_clawdbot_response(content)

            if analysis_data:
                # 格式化并发送回复
                await self._format_and_send_analysis(message, analysis_data)

                # 同步到事件总线
                if self.event_handler:
                    await self.event_handler({
                        "type": "clawdbot_analysis_complete",
                        "data": {
                            "ticker": analysis_data.ticker,
                            "fair_value_min": analysis_data.fair_value_range.get("min"),
                            "fair_value_max": analysis_data.fair_value_range.get("max"),
                            "pe_ratio": analysis_data.pe_ratio,
                            "industry_pe": analysis_data.industry_pe,
                            "growth_expectation": analysis_data.growth_expectation,
                            "consensus": analysis_data.consensus,
                            "risk_factors": analysis_data.risk_factors,
                            "reasoning": analysis_data.reasoning,
                            "projected_data": analysis_data.projected_data,
                            "key_events": analysis_data.key_events,
                        }
                    })

                logger.info(
                    f"[DiscordBot] Clawdbot 响应已处理: {analysis_data.ticker} "
                    f"估值: {analysis_data.fair_value_range}"
                )

        except json.JSONDecodeError as e:
            logger.error(f"[DiscordBot] JSON 解析失败: {e}")
            # 在 Showcase 显示错误
            if self.event_handler:
                await self.event_handler({
                    "type": "clawdbot_parse_error",
                    "data": {
                        "error": "研报格式异常",
                        "raw_content": content[:200],
                    }
                })

        except Exception as e:
            logger.error(f"[DiscordBot] 处理 Clawdbot 响应失败: {e}")

    def _parse_clawdbot_response(self, content: str) -> Optional[ClawdbotAnalysisData]:
        """
        解析 Clawdbot 的 JSON 响应

        支持多种格式：
        1. ```json ... ```
        2. ``` ... ```
        3. 直接的 JSON 对象
        """
        # 尝试提取代码块
        if "```" in content:
            # 移除代码块标记
            json_str = content
            json_str = json_str.replace("```json", "")
            json_str = json_str.replace("```", "")
            json_str = json_str.strip()
        else:
            json_str = content.strip()

        # 解析 JSON
        try:
            data = json.loads(json_str)

            # 验证必需字段
            if not data.get("ticker"):
                return None

            # 构建分析数据
            return ClawdbotAnalysisData(
                ticker=data.get("ticker", ""),
                fair_value_range=data.get("fair_value_range", {}),
                pe_ratio=data.get("pe_ratio"),
                industry_pe=data.get("industry_pe"),
                growth_expectation=data.get("growth_expectation"),
                consensus=data.get("consensus"),
                risk_factors=data.get("risk_factors", []),
                reasoning=data.get("reasoning"),
                projected_data=data.get("projected_data", {}),
                key_events=data.get("key_events", []),
            )

        except json.JSONDecodeError:
            # 尝试查找 JSON 对象
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    if data.get("ticker"):
                        return ClawdbotAnalysisData(
                            ticker=data.get("ticker", ""),
                            fair_value_range=data.get("fair_value_range", {}),
                            pe_ratio=data.get("pe_ratio"),
                            industry_pe=data.get("industry_pe"),
                            growth_expectation=data.get("growth_expectation"),
                            consensus=data.get("consensus"),
                            risk_factors=data.get("risk_factors", []),
                            reasoning=data.get("reasoning"),
                            projected_data=data.get("projected_data", {}),
                            key_events=data.get("key_events", []),
                        )
                except:
                    pass

        return None

    async def _format_and_send_analysis(
        self,
        original_message: discord.Message,
        analysis: ClawdbotAnalysisData
    ):
        """
        格式化并发送分析结果（OpenClaw Markdown 风格）

        包含：
        1. 估值结果（带颜色条）
        2. PE 分析
        3. 增长预期
        4. 机构共识
        5. 风险因素
        6. 关键事件
        7. 推理逻辑
        """
        # 构建响应消息
        response_parts = []

        # 标题
        response_parts.append(
            f"## 📊 {analysis.ticker} 分析报告\n"
        )

        # 估值范围
        fv_min = analysis.fair_value_range.get("min", 0)
        fv_max = analysis.fair_value_range.get("max", 0)
        response_parts.append(
            f"**💰 合理估值区间**: `{fv_min:.2f} - {fv_max:.2f}`\n"
        )

        # PE 分析
        if analysis.pe_ratio:
            pe_text = f"**📈 PE 比率**: `{analysis.pe_ratio:.2f}`"
            if analysis.industry_pe:
                diff_pct = ((analysis.pe_ratio - analysis.industry_pe) / analysis.industry_pe) * 100
                diff_emoji = "🔺" if diff_pct > 0 else "🔻"
                pe_text += f" (行业: `{analysis.industry_pe:.2f}`, {diff_emoji} `{diff_pct:+.1f}%`)"
            response_parts.append(f"{pe_text}\n")

        # 增长预期
        if analysis.growth_expectation:
            growth_icons = {"high": "🚀", "medium": "📈", "low": "📊"}
            growth_icon = growth_icons.get(analysis.growth_expectation, "📊")
            growth_labels = {"high": "高增长", "medium": "中等增长", "low": "低增长"}
            growth_label = growth_labels.get(analysis.growth_expectation, analysis.growth_expectation)
            response_parts.append(f"**{growth_icon} 增长预期**: `{growth_label}`\n")

        # 机构共识
        if analysis.consensus:
            consensus_bar = self._create_consensus_bar(analysis.consensus)
            response_parts.append(f"**🤝 机构共识**: `{analysis.consensus:.0f}%`\n{consensus_bar}\n")

        # 风险因素
        if analysis.risk_factors:
            response_parts.append("**⚠️ 风险因素**:\n")
            for risk in analysis.risk_factors[:5]:  # 限制显示数量
                response_parts.append(f"  • {risk}\n")
            response_parts.append("\n")

        # 关键事件
        if analysis.key_events:
            response_parts.append("**🎯 关键事件**:\n")
            for event in analysis.key_events[:5]:
                response_parts.append(f"  • {event}\n")
            response_parts.append("\n")

        # 推理逻辑（折叠）
        if analysis.reasoning:
            response_parts.append("**🤔 AI 推理**:\n")
            response_parts.append(f"> {analysis.reasoning[:300]}...\n\n")

        # 风险提示（OpenClaw 要求）
        response_parts.append(
            "---\n"
            "⚠️ *免责声明：以上分析仅供参考，不构成投资建议。投资有风险，决策需谨慎。*"
        )

        # 发送响应
        full_response = "".join(response_parts)

        try:
            await original_message.reply(full_response)
            logger.info(f"[DiscordBot] 已发送分析回复: {analysis.ticker}")
        except Exception as e:
            logger.error(f"[DiscordBot] 发送回复失败: {e}")

    def _create_consensus_bar(self, consensus: float, length: int = 20) -> str:
        """创建机构共识可视化条"""
        filled = int((consensus / 100) * length)
        bar = "█" * filled + "░" * (length - filled)

        # 根据共识度选择颜色
        if consensus >= 75:
            color = "🟢"  # 高共识
        elif consensus >= 50:
            color = "🟡"  # 中等共识
        else:
            color = "🔴"  # 低共识

        return f"{color} `{bar}`"


# =============================================================================
# 全局单例
# =============================================================================

_discord_client: Optional[AItradingBotClient] = None


def get_discord_client() -> AItradingBotClient:
    """获取全局 Discord 客户端实例"""
    global _discord_client
    if _discord_client is None:
        _discord_client = AItradingBotClient()
    return _discord_client


# =============================================================================
# 便捷函数
# =============================================================================

async def start_discord_bot(event_handler=None):
    """启动 Discord Bot"""
    client = get_discord_client()

    if not client.config["bot_token"]:
        logger.warning("[DiscordBot] DISCORD_BOT_TOKEN 未设置")
        return None

    client.event_handler = event_handler
    await client.start(client.config["bot_token"])

    return client


async def stop_discord_bot():
    """停止 Discord Bot"""
    global _discord_client
    if _discord_client:
        await _discord_client.close()
        _discord_client = None


# =============================================================================
# 主程序（用于测试）
# =============================================================================

async def main():
    """主程序（用于测试）"""
    # 定义事件处理
    async def event_handler(event: Dict[str, Any]):
        print(f"\n[事件总线] {event['type']}")
        print(f"数据: {json.dumps(event['data'], indent=2, ensure_ascii=False)}")

    client = get_discord_client()
    client.event_handler = event_handler

    async with client:
        print(f"Bot 已启动: {client.user}")
        print(f"监听命令: {client.config['command_prefix']} analyze")
        print(f"Clawdbot ID: {client.clawdbot_user_id}")

        # 保持运行
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
