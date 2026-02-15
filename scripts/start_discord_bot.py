"""
AI TradeBot - Discord Bot 独立启动脚本

启动 Discord Bot 服务，实现与 Clawdbot 的闭环通讯
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def main():
    """主函数"""
    print("=" * 60)
    print("AI TradeBot - Discord Bot 启动脚本")
    print("=" * 60)
    print()

    # 检查环境配置
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    if not bot_token or bot_token.startswith("YOUR_") or bot_token == "your_discord_bot_token_here":
        print("❌ 错误: DISCORD_BOT_TOKEN 未正确配置")
        print()
        print("请在 .env 文件中设置你的 Discord Bot Token:")
        print("  DISCORD_BOT_TOKEN=<你的 Discord Bot Token>")
        print()
        print("💡 如何获取 Token:")
        print("  1. 访问 https://discord.com/developers/applications")
        print("  2. 创建或选择你的应用")
        print("  3. 在 Bot 页面获取 Token")
        print()
        return

    clawdbot_id = os.getenv("CLAWDBOT_USER_ID")
    channel_id = os.getenv("DISCORD_CHANNEL_ID")

    print("✅ Discord 配置检查:")
    print(f"  Bot Token: {bot_token[:20]}...")
    print(f"  Clawdbot ID: {clawdbot_id}")
    print(f"  频道 ID: {channel_id or '未设置（将监听所有频道）'}")
    print()

    # 导入 Discord 客户端
    try:
        from core.comms.discord_client import AItradingBotClient, get_discord_client
        from shared.logging import get_logger

        logger = get_logger(__name__)
    except ImportError as e:
        print(f"❌ 导入错误: {e}")
        print("请确保已安装依赖: pip install discord.py")
        return

    # 定义事件处理（连接到系统）
    async def event_handler(event):
        """处理 Discord 事件并同步到系统"""
        print(f"\n[事件] {event['type']}: {event.get('data', {})}")

        # 这里可以通过 WebSocket 推送到前端
        # 或更新数据库
        pass

    # 创建并启动 Bot
    client = get_discord_client()
    client.event_handler = event_handler

    print("🤖 正在启动 Discord Bot...")
    print()

    try:
        async with client:
            # Bot 就绪
            await client.wait_until_ready()

            print("=" * 60)
            print("  Discord Bot 已启动!")
            print("=" * 60)
            print()
            print(f"  Bot 名称: {client.user.name}")
            print(f"  Bot ID: {client.user.id}")
            print(f"  Clawdbot ID: {client.clawdbot_user_id}")
            print()
            print("  使用方法:")
            print(f"    在 Discord 中输入: @AItradingBot analyze <股票代码>")
            print("    例如: @AItradingBot analyze 600000.SH")
            print()
            print("  Clawdbot 将自动分析并返回结果")
            print()
            print("  按 Ctrl+C 停止 Bot")
            print("=" * 60)
            print()

            # 保持运行
            await asyncio.Event().wait()

    except KeyboardInterrupt:
        print()
        print("=" * 60)
        print("正在停止 Discord Bot...")
        print("=" * 60)
        print()
        print("Bot 已停止")

    except Exception as e:
        print()
        print(f"❌ 启动失败: {e}")
        print()


if __name__ == "__main__":
    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv()

    asyncio.run(main())
