"""
测试 TradeEvent ORM 模型的 CRUD 操作
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, delete
from core.database.session import get_db_context, db_manager
from storage.models.trade_event import (
    TradeEvent,
    EventStatus,
    Direction,
    ExitPlan,
    EntryPlan,
)
from shared.logging import setup_logging, get_logger, track_ai_call


async def test_create_event():
    """测试创建事件"""
    logger = get_logger(__name__)

    async with get_db_context() as db:
        # 创建测试事件
        event = TradeEvent(
            id="TEV_20250211_001",
            ticker="600000.SH",
            ticker_name="浦发银行",
            direction=Direction.LONG,
            current_status=EventStatus.OBSERVING,
            event_description="测试事件：发布年报预增公告",
            logic_summary="年报预增，预计股价上涨",
            confidence=0.75,
            source_type="test",
            category="announcement",
            ai_participants=["kimi", "glm4", "minimax"],
            reasoning_log=[
                {
                    "model": "kimi",
                    "timestamp": datetime.now().isoformat(),
                    "input": "年报预增公告",
                    "output": "利好消息，建议做多",
                    "duration_ms": 1250.5,
                }
            ],
            # 入场计划
            entry_plan=EntryPlan(
                trigger_price=10.50,
                limit_price=10.55,
                entry_condition="回踩至5日均线附近",
                quantity=1000,
            ).model_dump(),
            # 退出计划（核心）
            exit_plan=ExitPlan(
                take_profit={
                    "price": 12.50,
                    "logic": "基于估值修复预期，目标市盈率回归至15倍",
                    "confidence": 0.75
                },
                stop_loss={
                    "price": 9.80,
                    "logic": "逻辑证伪线：若跌破此价格则利好消息已消化",
                    "falsification_point": "支撑位跌破"
                },
                expiration={
                    "expire_time": (datetime.now() + timedelta(days=90)).isoformat(),
                    "logic": "年报落地时间窗口，预期3个月见效",
                    "event_end": "2025年Q1财报发布"
                }
            ).model_dump(),
        )

        db.add(event)
        await db.commit()

        logger.info(f"创建事件: {event.id}")
        logger.info(f"  标的: {event.ticker} {event.ticker_name}")
        logger.info(f"  状态: {event.current_status}")
        logger.info(f"  止盈: {event.exit_plan['take_profit']['price']}")
        logger.info(f"  止损: {event.exit_plan['stop_loss']['price']}")

        return event


async def test_query_event():
    """测试查询事件"""
    logger = get_logger(__name__)

    async with get_db_context() as db:
        # 查询所有事件
        result = await db.execute(select(TradeEvent))
        events = result.scalars().all()

        logger.info(f"查询到 {len(events)} 个事件")

        for event in events:
            logger.info(f"  - {event.id}: {event.ticker} ({event.current_status})")

        return events


async def test_update_event():
    """测试更新事件"""
    logger = get_logger(__name__)

    async with get_db_context() as db:
        # 查询事件
        result = await db.execute(
            select(TradeEvent).where(TradeEvent.id == "TEV_20250211_001")
        )
        event = result.scalar_one_or_none()

        if event:
            # 更新状态为持仓中
            event.current_status = EventStatus.POSITION_OPEN
            event.actual_entry_price = 10.55
            event.actual_entry_time = datetime.now()
            event.actual_quantity = 1000

            await db.commit()

            logger.info(f"更新事件: {event.id}")
            logger.info(f"  新状态: {event.current_status}")
            logger.info(f"  入场价: {event.actual_entry_price}")


async def test_should_exit():
    """测试退出逻辑"""
    logger = get_logger(__name__)

    async with get_db_context() as db:
        result = await db.execute(
            select(TradeEvent).where(TradeEvent.id == "TEV_20250211_001")
        )
        event = result.scalar_one_or_none()

        if event:
            # 测试止盈触发
            exit_reason = event.should_exit(13.00, datetime.now())
            logger.info(f"当前价格 13.00: {exit_reason or '未触发退出'}")

            # 测试止损触发
            exit_reason = event.should_exit(9.50, datetime.now())
            logger.info(f"当前价格 9.50: {exit_reason or '未触发退出'}")

            # 测试未触发
            exit_reason = event.should_exit(11.00, datetime.now())
            logger.info(f"当前价格 11.00: {exit_reason or '未触发退出'}")


async def test_delete_events():
    """测试删除所有测试数据"""
    logger = get_logger(__name__)

    async with get_db_context() as db:
        await db.execute(delete(TradeEvent))
        await db.commit()
        logger.info("已删除所有测试数据")


async def test_ai_call_tracking():
    """测试 AI 调用追踪"""
    logger = get_logger(__name__)

    # 使用装饰器模式
    @track_ai_call("kimi", "测试长文处理")
    async def mock_kimi_call(text: str) -> str:
        await asyncio.sleep(0.1)
        return f"处理结果: {text[:20]}..."

    # 使用上下文管理器模式
    with track_ai_call("glm4", "测试逻辑推演"):
        await asyncio.sleep(0.05)
        logger.info("GLM-4 推演完成")

    # 调用装饰器函数
    result = await mock_kimi_call("这是一段很长的文本，需要 KIMI 来处理...")
    logger.info(result)


async def main():
    """主测试函数"""
    setup_logging()
    logger = get_logger(__name__)

    logger.info("=" * 60)
    logger.info("AI TradeBot - TradeEvent 模型测试")
    logger.info("=" * 60)

    # 初始化数据库
    await db_manager.initialize_engine()

    try:
        # 测试 1: 创建事件
        logger.info("\n[测试 1] 创建事件")
        await test_create_event()

        # 测试 2: 查询事件
        logger.info("\n[测试 2] 查询事件")
        await test_query_event()

        # 测试 3: 更新事件
        logger.info("\n[测试 3] 更新事件")
        await test_update_event()

        # 测试 4: 退出逻辑
        logger.info("\n[测试 4] 退出逻辑检查")
        await test_should_exit()

        # 测试 5: AI 调用追踪
        logger.info("\n[测试 5] AI 调用追踪")
        await test_ai_call_tracking()

        # 清理
        logger.info("\n[清理] 删除测试数据")
        await test_delete_events()

        logger.info("\n" + "=" * 60)
        logger.info("所有测试通过!")
        logger.info("=" * 60)

        # 关闭数据库连接
        await db_manager.close()

    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        await db_manager.close()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
