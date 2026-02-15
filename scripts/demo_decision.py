"""
AI TradeBot - 决策层简化演示

展示 AI 协同工作流的完整逻辑（不依赖真实 API）
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database.session import db_manager, get_db_context
from storage.models.trade_event import TradeEvent, EventStatus, Direction
from shared.logging import setup_logging, get_logger


logger = get_logger(__name__)


async def demo_decision_workflow():
    """演示完整的决策工作流"""
    logger.info("=" * 60)
    logger.info("AI 协同决策工作流演示")
    logger.info("=" * 60)

    # 初始化数据库
    await db_manager.initialize_engine()

    # 模拟 AI 协同流程的输出
    ticker = "600000"
    event_id = f"DEMO_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"\n标的: {ticker}")
    logger.info(f"事件 ID: {event_id}")

    # ========== 步骤 1: 感知层 ==========
    logger.info("\n[步骤 1] 感知层：获取数据")
    announcement = """
浦发银行2024年年度业绩预增公告

经测算，预计2024年净利润同比增长20%-30%。
主要原因：资产质量改善、利息收入增长、数字化转型见效。
"""
    current_price = 10.50
    logger.info(f"  当前价格: {current_price}")
    logger.info(f"  公告内容: {announcement[:50]}...")

    # ========== 步骤 2: Kimi 清洗 ==========
    logger.info("\n[步骤 2] Kimi：清洗摘要")
    summary = "浦发银行2024年业绩预增20%-30%，主要因资产质量改善和利息收入增长。"
    logger.info(f"  摘要: {summary}")

    # ========== 步骤 3: GLM-4 推演 ==========
    logger.info("\n[步骤 3] GLM-4：逻辑推演")
    logger.info("  逻辑成立: True")
    logger.info("  置信度: 0.75")

    reasoning = """
业绩预增逻辑成立：
1. 银行业整体复苏趋势明确
2. 资产质量改善带来利润释放
3. 数字化转型提升运营效率

目标价: 12.50 (基于1.2倍PB)
止损价: 9.80 (跌破则逻辑证伪)
时效: 3个月 (财报落地)
"""
    logger.info(f"  推理: {reasoning[:100]}...")

    # ========== 步骤 4: MiniMax 打包 ==========
    logger.info("\n[步骤 4] MiniMax：生成决策包")
    decision = {
        "action": "BUY",
        "quantity": 1000,
        "entry_plan": {
            "trigger_price": 10.50,
            "entry_condition": "当前价格附近入场"
        },
        "exit_plan": {
            "take_profit": {
                "price": 12.50,
                "logic": "估值修复至1.2倍PB"
            },
            "stop_loss": {
                "price": 9.80,
                "logic": "跌破支撑位说明逻辑证伪"
            },
            "expiration": {
                "expire_time": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                "logic": "3个月财报窗口期"
            }
        }
    }

    logger.info(f"  动作: {decision['action']}")
    logger.info(f"  数量: {decision['quantity']} 股")
    logger.info(f"  入场价: {decision['entry_plan']['trigger_price']}")
    logger.info(f"  止盈价: {decision['exit_plan']['take_profit']['price']}")
    logger.info(f"  止损价: {decision['exit_plan']['stop_loss']['price']}")
    logger.info(f"  失效时间: {decision['exit_plan']['expiration']['expire_time']}")

    # ========== 步骤 5: 存储到数据库 ==========
    logger.info("\n[步骤 5] 存储到数据库")

    async with get_db_context() as db:
        event = TradeEvent(
            id=event_id,
            ticker=ticker,
            ticker_name="浦发银行",
            direction=Direction.LONG,
            current_status=EventStatus.OBSERVING,
            event_description="2024年业绩预增公告",
            logic_summary=summary,
            confidence=0.75,
            source_type="ai_analysis",
            category="announcement",
            ai_participants=["kimi", "glm4", "minimax"],
            reasoning_log=[
                {
                    "step": "kimi",
                    "action": "summarize_announcement",
                    "input": announcement[:100],
                    "output": summary,
                    "timestamp": datetime.now().isoformat(),
                },
                {
                    "step": "glm4",
                    "action": "reason_event",
                    "logic_valid": True,
                    "confidence": 0.75,
                    "reasoning": reasoning.strip(),
                    "timestamp": datetime.now().isoformat(),
                },
                {
                    "step": "minimax",
                    "action": "generate_decision_bundle",
                    "final_action": decision["action"],
                    "timestamp": datetime.now().isoformat(),
                },
            ],
            entry_plan=decision["entry_plan"],
            exit_plan=decision["exit_plan"],
        )

        db.add(event)
        await db.commit()

        logger.info(f"  事件已存储: {event_id}")

    # ========== 展示完整推理链路 ==========
    logger.info("\n" + "=" * 60)
    logger.info("完整 AI 推理链路")
    logger.info("=" * 60)

    logger.info("\n[原始公告]")
    logger.info(announcement.strip())

    logger.info("\n[Kimi 清洗后]")
    logger.info(summary)

    logger.info("\n[GLM-4 推演]")
    logger.info(reasoning.strip())

    logger.info("\n[MiniMax 决策包]")
    import json
    logger.info(json.dumps(decision, indent=2, ensure_ascii=False))

    logger.info("\n" + "=" * 60)
    logger.info("演示完成！")
    logger.info("=" * 60)


async def demo_exit_planner():
    """演示退出规划器"""
    logger.info("\n" + "=" * 60)
    logger.info("退出规划器演示")
    logger.info("=" * 60)

    async with get_db_context() as db:
        from sqlalchemy import select

        # 查询观察中的事件
        result = await db.execute(
            select(TradeEvent).where(
                TradeEvent.current_status == EventStatus.OBSERVING
            ).limit(1)
        )
        event = result.scalar_one_or_none()

        if not event:
            logger.info("  无观察中的事件")
            return

        logger.info(f"\n事件: {event.id} - {event.ticker}")
        logger.info(f"退出计划:")
        logger.info(f"  止盈: {event.exit_plan.get('take_profit', {}).get('price', 'N/A')}")
        logger.info(f"  止损: {event.exit_plan.get('stop_loss', {}).get('price', 'N/A')}")
        logger.info(f"  失效: {event.exit_plan.get('expiration', {}).get('expire_time', 'N/A')}")

        # 模拟不同价格下的退出判断
        logger.info(f"\n模拟价格检查:")

        prices = [9.50, 10.50, 12.00, 13.00]
        for price in prices:
            exit_reason = event.should_exit(price, datetime.now())
            if exit_reason:
                logger.info(f"  价格 {price}: 触发退出 -> {exit_reason}")
            else:
                logger.info(f"  价格 {price}: 持仓中")


async def main():
    """主函数"""
    setup_logging()

    logger.info("\n")
    logger.info("=" * 60)
    logger.info("AI TradeBot - 决策层功能演示")
    logger.info("=" * 60)
    logger.info("\n")

    try:
        # 决策工作流演示
        await demo_decision_workflow()

        # 退出规划器演示
        await demo_exit_planner()

        logger.info("\n所有演示完成!")

    except KeyboardInterrupt:
        logger.info("\n演示被用户中断")
    except Exception as e:
        logger.error(f"演示过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
