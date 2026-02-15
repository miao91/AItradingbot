"""
AI TradeBot - 执行层测试脚本

演示：
1. 硬风控检查
2. 订单路由
3. 模拟交易
4. 紧急制动
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database.session import db_manager, get_db_context
from storage.models.trade_event import TradeEvent, EventStatus
from execution.qmt.client import QMTClient, OrderType, OrderSide
from execution.order.router import (
    OrderRouter,
    OrderSignal,
    process_decision_bundle,
    emergency_stop,
)
from shared.logging import setup_logging, get_logger


logger = get_logger(__name__)


async def test_safety_check():
    """测试风控检查"""
    logger.info("=" * 60)
    logger.info("测试 1: 风控检查")
    logger.info("=" * 60)

    router = OrderRouter()

    # 测试场景 1: 正常订单
    logger.info("\n[场景 1] 正常订单")
    signal = OrderSignal(
        event_id="TEST_001",
        ticker="600000.SH",
        action="BUY",
        quantity=1000,
        price=10.50,
    )

    result = await router._safety_check(signal)
    logger.info(f"  通过: {result.passed}")
    logger.info(f"  原因: {result.reason}")
    if result.details:
        logger.info(f"  详情: {result.details}")

    # 测试场景 2: 超过单笔限制
    logger.info("\n[场景 2] 超过单笔限制 (买入过多)")
    signal = OrderSignal(
        event_id="TEST_002",
        ticker="600000.SH",
        action="BUY",
        quantity=100000,  # 大额订单
        price=10.50,
    )

    result = await router._safety_check(signal)
    logger.info(f"  通过: {result.passed}")
    logger.info(f"  原因: {result.reason}")

    # 测试场景 3: 超过总仓位限制
    logger.info("\n[场景 3] 超过总仓位限制")
    # 先模拟已有高仓位
    logger.info("  (模拟已持有70%仓位)")

    signal = OrderSignal(
        event_id="TEST_003",
        ticker="600001.SH",
        action="BUY",
        quantity=10000,
        price=10.0,
    )

    result = await router._safety_check(signal)
    logger.info(f"  通过: {result.passed}")
    logger.info(f"  原因: {result.reason}")


async def test_order_execution():
    """测试订单执行"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: 订单执行")
    logger.info("=" * 60)

    client = QMTClient(simulation_mode=True)
    await client.connect()

    logger.info(f"  模拟模式: {client.simulation_mode}")
    logger.info(f"  已连接: {client.is_connected}")

    # 测试市价单
    logger.info("\n[市价单测试]")
    order = await client.execute_order(
        symbol="600000.SH",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=1000,
    )

    logger.info(f"  订单ID: {order.order_id}")
    logger.info(f"  状态: {order.status.value}")
    logger.info(f"  成交量: {order.filled_quantity}")

    # 测试限价单
    logger.info("\n[限价单测试]")
    order = await client.execute_order(
        symbol="600000.SH",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=500,
        price=10.30,
    )

    logger.info(f"  订单ID: {order.order_id}")
    logger.info(f"  状态: {order.status.value}")
    logger.info(f"  成交量: {order.filled_quantity}")

    await client.disconnect()


async def test_account_query():
    """测试账户查询"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: 账户查询")
    logger.info("=" * 60)

    client = QMTClient(simulation_mode=True)
    await client.connect()

    # 查询账户
    account = await client.get_account_info()
    if account:
        logger.info("\n[账户信息]")
        logger.info(f"  总资产: {account.total_assets:,.2f}")
        logger.info(f"  可用资金: {account.available_cash:,.2f}")
        logger.info(f"  证券市值: {account.market_value:,.2f}")
        logger.info(f"  持仓盈亏: {account.position_profit:,.2f}")

    # 查询持仓
    positions = await client.get_positions()
    logger.info(f"\n[持仓信息] 共 {len(positions)} 只")

    for pos in positions:
        logger.info(
            f"  {pos.symbol} {pos.symbol_name}: "
            f"{pos.quantity}股 "
            f"@{pos.cost_price:.2f} "
            f"(盈亏: {pos.profit_loss_ratio*100:+.2f}%)"
        )

    await client.disconnect()


async def test_full_workflow():
    """测试完整工作流"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 4: 完整工作流（决策 -> 风控 -> 下单）")
    logger.info("=" * 60)

    # 初始化数据库
    await db_manager.initialize_engine()

    # 创建一个测试事件
    event_id = f"TEST_EVT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async with get_db_context() as db:
        event = TradeEvent(
            id=event_id,
            ticker="600000.SH",
            ticker_name="浦发银行",
            direction="long",
            current_status=EventStatus.OBSERVING,
            event_description="测试事件",
            logic_summary="测试逻辑摘要",
            confidence=0.75,
            source_type="test",
            category="test",
            ai_participants=["test"],
            entry_plan={"trigger_price": 10.50, "quantity": 1000},
            exit_plan={
                "take_profit": {"price": 12.00},
                "stop_loss": {"price": 9.80},
                "expiration": {"expire_time": "2025-05-11"},
            },
        )
        db.add(event)
        await db.commit()

    logger.info(f"\n创建测试事件: {event_id}")

    # 处理决策
    logger.info("\n处理决策信号...")
    result = await process_decision_bundle(
        event_id=event_id,
        ticker="600000.SH",
        action="BUY",
        quantity=1000,
        price=10.50,
    )

    logger.info(f"\n风控结果:")
    logger.info(f"  通过: {result.passed}")
    logger.info(f"  原因: {result.reason}")

    # 查询事件状态
    async with get_db_context() as db:
        from sqlalchemy import select

        result = await db.execute(select(TradeEvent).where(TradeEvent.id == event_id))
        event = result.scalar_one_or_none()

        if event:
            logger.info(f"\n事件状态:")
            logger.info(f"  当前状态: {event.current_status}")
            logger.info(f"  订单ID: {event.order_id}")
            logger.info(f"  入场价: {event.actual_entry_price}")
            logger.info(f"  入场量: {event.actual_quantity}")


async def test_emergency_stop():
    """测试紧急制动"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 5: 紧急制动")
    logger.info("=" * 60)

    # 先创建一些测试事件
    await db_manager.initialize_engine()

    async with get_db_context() as db:
        # 创建观察中的事件
        for i in range(3):
            event = TradeEvent(
                id=f"EMERGENCY_TEST_{i}",
                ticker=f"60000{i}.SH",
                current_status=EventStatus.OBSERVING,
                event_description="紧急制动测试",
                source_type="test",
                entry_plan={},
                exit_plan={},
            )
            db.add(event)
            await db.commit()

    logger.info("创建 3 个测试事件")

    # 查询事件数量
    async with get_db_context() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(TradeEvent).where(
                TradeEvent.current_status.in_([
                    EventStatus.OBSERVING,
                    EventStatus.POSITION_OPEN,
                ])
            )
        )
        count = len(result.scalars().all())

    logger.info(f"当前在途事件: {count} 个")

    # 触发紧急制动
    logger.info("\n触发紧急制动...")
    await emergency_stop("测试紧急制动")

    # 查询后数量
    async with get_db_context() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(TradeEvent).where(
                TradeEvent.current_status.in_([
                    EventStatus.OBSERVING,
                    EventStatus.POSITION_OPEN,
                ])
            )
        )
        count_after = len(result.scalars().all())

    logger.info(f"紧急制动后在途事件: {count_after} 个")
    logger.info("✓ 紧急制动测试完成")


async def test_risk_limits():
    """测试各类风控限制"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 6: 风控限制演示")
    logger.info("=" * 60)

    router = OrderRouter()

    # 显示硬编码的风控参数
    config = router.safety_config
    logger.info("\n[硬编码风控参数]")
    logger.info(f"  单笔上限: {config.MAX_SINGLE_ORDER_RATIO*100}% 总资产")
    logger.info(f"  总仓位上限: {config.MAX_TOTAL_POSITION_RATIO*100}%")
    logger.info(f"  现金储备: {config.MAX_CASH_RESERVE_RATIO*100}%")
    logger.info(f"  单只股票上限: {config.MAX_SINGLE_STOCK_RATIO*100}%")
    logger.info(f"  最大持仓数: {config.MAX_POSITIONS_COUNT} 只")
    logger.info(f"  日订单上限: {config.MAX_ORDERS_PER_DAY} 笔")
    logger.info(f"  日亏损熔断: {config.DAILY_LOSS_LIMIT_RATIO*100}%")

    # 测试不同限制场景
    tests = [
        ("单笔超限", {"quantity": 200000, "price": 10.0}),
        ("现金储备", {"quantity": 900000, "price": 10.0}),
    ]

    for test_name, params in tests:
        logger.info(f"\n[{test_name}]")
        signal = OrderSignal(
            event_id=f"TEST_{test_name}",
            ticker="600000.SH",
            action="BUY",
            quantity=params["quantity"],
            price=params["price"],
        )

        result = await router._safety_check(signal)
        logger.info(f"  结果: {'通过' if result.passed else '拒绝'}")
        logger.info(f"  原因: {result.reason}")


async def main():
    """主测试函数"""
    setup_logging()

    logger.info("\n")
    logger.info("=" * 60)
    logger.info("AI TradeBot - 执行层测试")
    logger.info("=" * 60)
    logger.info("\n")

    try:
        # 测试 1: 风控检查
        await test_safety_check()

        # 测试 2: 订单执行
        await test_order_execution()

        # 测试 3: 账户查询
        await test_account_query()

        # 测试 4: 完整工作流
        await test_full_workflow()

        # 测试 5: 紧急制动
        await test_emergency_stop()

        # 测试 6: 风控限制
        await test_risk_limits()

        logger.info("\n" + "=" * 60)
        logger.info("所有测试完成!")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
