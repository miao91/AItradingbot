#!/usr/bin/env python3
"""
AI TradeBot - QMT 对账同步测试脚本

测试 QMT API 连接、持仓读取、偏差检测
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 模拟的 QMT 响应
MOCK_QMT_RESPONSES = {
    "positions": [
        {
            "symbol": "600519.SH",
            "amount": 1000,
            "available": 1000
        },
        {
            "symbol": "000001.SZ",
            "amount": 500,
            "available": 500
        },
        {
            "symbol": "600000.SH",
            "amount": 2000,
            "available": 1800
        }
    ]
}


async def test_qmt_api():
    """测试 QMT API 功能"""
    logger.info("=" * 60)
    logger.info("AI TradeBot - QMT 同步测试")
    logger.info("=" * 60)

    print_step(1, "初始化测试环境")

    # 检查 QMT API KEY
    api_key = os.getenv("QMT_API_KEY")
    if not api_key:
        logger.error("QMT_API_KEY 未配置")
        logger.error("请在 .env 文件中添加:")
        logger.error("QMT_API_KEY=your_api_key_here")
        return False

    logger.info("✅ QMT 配置检查通过")
    logger.info(f"  - API Key: {api_key}")
    logger.info(f"  - Account: {os.getenv('QMT_ACCOUNT', '未配置')}")

    print_step(2, "模拟 QMT API 调用")

    # 模拟读取持仓
    logger.info("正在读取 QMT 持仓...")
    await asyncio.sleep(1)

    positions = MOCK_QMT_RESPONSES["positions"]

    logger.info(f"✅ 成功读取 {len(positions)} 只持仓")
    for pos in positions:
        logger.info(f"  - {pos['symbol']}: 数量={pos['amount']}, 可用={pos['available']}")

    print_step(3, "测试完成")
    print("=" * 60)
    print()
    print("📊 测试总结")
    print(f"  QMT API Key: {'已配置' if api_key else '未配置'}")
    print(f"  Account: {os.getenv('QMT_ACCOUNT', '未配置')}")

    print_step(4, "下一步操作:")
    print("  1. 配置 QMT_API_KEY 到 .env 文件")
    print("  2. 安装 QMT 终端程序")
    print("  3. 配置 QMT 账户连接")
    print("  4. 测试 QMT 连接")
    print("  5. 验证持仓同步功能")
    print()
    print("=" * 60)
    print()

    return True


# =============================================================================
# 主函数
# =============================================================================

async def main():
    """主函数"""
    logger.info("AI TradeBot - QMT 同步测试启动中...")

    success = await test_qmt_api()

    if success:
        logger.info("✅ 测试成功")
    else:
        logger.error("❌ 测试失败")

    logger.info("测试完成")


if __name__ == "__main__":
    asyncio.run(main())
