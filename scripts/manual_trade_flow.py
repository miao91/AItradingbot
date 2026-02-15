"""
AI TradeBot - 手动交易流程演示

演示完整的手动确认流程：
1. 创建交易事件
2. AI 生成决策信号
3. 进入待确认状态（PENDING_CONFIRM）
4. 人工在券商下单后回填
5. 自动启动退出规划器监控
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
from execution.order.router import OrderRouter, OrderSignal
from execution.order.manual_handler import (
    ManualTradeHandler,
    confirm_manual_trade,
    get_pending_trades,
)
from shared.logging import setup_logging, get_logger
from shared.constants import ExecutionMode


logger = get_logger(__name__)


async def step1_create_event():
    """步骤 1: 创建交易事件"""
    logger.info("=" * 60)
    logger.info("步骤 1: 创建交易事件")
    logger.info("=" * 60)

    await db_manager.initialize_engine()

    event_id = f"TEV_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async with get_db_context() as db:
        event = TradeEvent(
            id=event_id,
            ticker="600519.SH",
            ticker_name="贵州茅台",
            direction="long",
            current_status=EventStatus.OBSERVING,
            event_description="2024年Q3财报超预期，净利润同比增长25%，受主力资金关注",
            logic_summary="白酒龙头业绩超预期，估值修复空间打开",
            confidence=0.78,
            source_type="tushare",
            category="earnings",
            ai_participants=["kimi", "glm4", "minimax"],
            entry_plan={
                "trigger_price": 1680.00,
                "limit_price": 1685.00,
                "entry_condition": "回踩至5日均线附近且成交量放大",
                "quantity": 10,  # 降低到10股以便通过风控（约1.68万，约1.7%）
            },
            exit_plan={
                "take_profit": {
                    "price": 1850.00,
                    "logic": "基于估值修复预期，目标市盈率回归至35倍",
                    "confidence": 0.75
                },
                "stop_loss": {
                    "price": 1600.00,
                    "logic": "逻辑证伪线：若跌破此价格则利好消息已消化",
                    "falsification_point": "关键技术支撑位跌破"
                },
                "expiration": {
                    "expire_time": (datetime.now() + timedelta(days=90)).isoformat(),
                    "logic": "年报落地时间窗口，预期3个月见效",
                    "event_end": "2025年Q1财报发布"
                }
            },
        )
        db.add(event)
        await db.commit()

    logger.info(f"\n事件创建成功: {event_id}")
    logger.info(f"  标的: {event.ticker_name} ({event.ticker})")
    logger.info(f"  逻辑: {event.logic_summary}")
    logger.info(f"  入场计划: {event.entry_plan}")
    logger.info(f"  止盈: {event.exit_plan['take_profit']['price']}")
    logger.info(f"  止损: {event.exit_plan['stop_loss']['price']}")

    return event_id


async def step2_ai_decision_signal(event_id: str):
    """步骤 2: AI 生成决策信号"""
    logger.info("\n" + "=" * 60)
    logger.info("步骤 2: AI 生成决策信号")
    logger.info("=" * 60)

    # 在实际系统中，这里会调用 decision.workflows.event_analyzer
    # 演示中我们直接构造信号
    signal = OrderSignal(
        event_id=event_id,
        ticker="600519.SH",
        action="BUY",
        quantity=10,  # 降低到10股以便通过风控
        price=1680.00,
        order_type="limit",
        reason="AI 协调决策: Kimi分析财报 + GLM4推理 + MiniMax生成结构化输出",
    )

    logger.info(f"\nAI 决策信号:")
    logger.info(f"  动作: {signal.action}")
    logger.info(f"  标的: {signal.ticker}")
    logger.info(f"  数量: {signal.quantity}股")
    logger.info(f"  价格: {signal.price}")
    logger.info(f"  原因: {signal.reason}")

    return signal


async def step3_process_with_manual_mode(event_id: str, signal: OrderSignal):
    """步骤 3: 处理信号（手动模式）"""
    logger.info("\n" + "=" * 60)
    logger.info("步骤 3: 处理信号（手动确认模式）")
    logger.info("=" * 60)

    # 使用 MANUAL 模式创建路由器
    router = OrderRouter(execution_mode=ExecutionMode.MANUAL)

    # 处理信号（会触发硬风控检查）
    result = await router.process_signal(signal)

    logger.info(f"\n处理结果:")
    logger.info(f"  风控通过: {result.passed}")
    logger.info(f"  原因: {result.reason}")

    if result.details:
        logger.info(f"  详情: {result.details}")

    # 如果风控未通过，提前返回
    if not result.passed:
        logger.info("\n风控未通过，无法进入待确认状态")
        return

    # 查询当前事件状态
    async with get_db_context() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(TradeEvent).where(TradeEvent.id == event_id)
        )
        event = result.scalar_one_or_none()

        if event:
            logger.info(f"\n事件当前状态: {event.current_status}")

            if event.current_status == EventStatus.PENDING_CONFIRM:
                logger.info("\n[高亮提示]")
                logger.info("==========================================")
                logger.info("[信号待确认] 请在券商APP手动买入 600519.SH")
                logger.info("[信号待确认] 建议价格: 1680.00")
                logger.info(f"[信号待确认] 建议数量: {signal.quantity}股")
                logger.info(f"[信号待确认] 事件ID: {event_id}")
                logger.info("[信号待确认] 买入后请使用以下命令回填:")
                logger.info(f"  python scripts/manual_trade_flow.py --confirm {event_id} --price 1680.50 --qty {signal.quantity}")
                logger.info("==========================================")


async def step4_manual_backfill(event_id: str, actual_price: float, actual_qty: int):
    """步骤 4: 人工回填"""
    logger.info("\n" + "=" * 60)
    logger.info("步骤 4: 人工回填实际成交")
    logger.info("=" * 60)

    logger.info(f"\n用户已手动下单，正在回填...")
    logger.info(f"  事件ID: {event_id}")
    logger.info(f"  实际成交价: {actual_price}")
    logger.info(f"  实际成交量: {actual_qty}股")

    # 调用手动确认
    result = await confirm_manual_trade(
        event_id=event_id,
        actual_price=actual_price,
        actual_quantity=actual_qty,
        notes="用户在券商APP手动下单完成",
    )

    logger.info(f"\n回填结果:")
    logger.info(f"  成功: {result.success}")
    logger.info(f"  原状态: {result.old_status}")
    logger.info(f"  新状态: {result.new_status}")
    logger.info(f"  消息: {result.message}")
    logger.info(f"  退出监控已启动: {result.exit_monitoring_started}")

    # 查询更新后的事件
    async with get_db_context() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(TradeEvent).where(TradeEvent.id == event_id)
        )
        event = result.scalar_one_or_none()

        if event:
            logger.info(f"\n事件详情:")
            logger.info(f"  当前状态: {event.current_status}")
            logger.info(f"  实际入场价: {event.actual_entry_price}")
            logger.info(f"  实际入场量: {event.actual_quantity}")
            logger.info(f"  实际入场时间: {event.actual_entry_time}")

            # 仅在成功开仓时计算盈亏
            if event.actual_entry_price and event.exit_plan.get("take_profit"):
                tp = event.exit_plan["take_profit"]["price"]
                current_pnl_ratio = (actual_price - event.actual_entry_price) / event.actual_entry_price * 100
                tp_ratio = (tp - event.actual_entry_price) / event.actual_entry_price * 100
                logger.info(f"\n  目标止盈: {tp} (+{tp_ratio:.2f}%)")
                logger.info(f"  当前盈亏: {current_pnl_ratio:+.2f}%")


async def demo_query_pending():
    """演示: 查询待确认事件"""
    logger.info("\n" + "=" * 60)
    logger.info("演示: 查询待确认事件")
    logger.info("=" * 60)

    pending = await get_pending_trades()

    if not pending:
        logger.info("\n当前没有待确认的交易")
    else:
        logger.info(f"\n待确认交易: {len(pending)} 个")
        for i, trade in enumerate(pending, 1):
            logger.info(f"\n  [{i}] {trade['event_id']}")
            logger.info(f"      标的: {trade['ticker']} {trade.get('ticker_name', '')}")
            logger.info(f"      逻辑: {trade.get('logic_summary', 'N/A')}")
            logger.info(f"      入场计划: {trade.get('entry_plan', {})}")


async def main():
    """主函数"""
    setup_logging()

    logger.info("\n")
    logger.info("=" * 60)
    logger.info("AI TradeBot - 手动交易流程演示")
    logger.info("=" * 60)
    logger.info("\n")

    try:
        # 完整流程演示
        event_id = await step1_create_event()
        signal = await step2_ai_decision_signal(event_id)
        await step3_process_with_manual_mode(event_id, signal)

        # 检查事件是否进入待确认状态
        async with get_db_context() as db:
            from sqlalchemy import select
            result = await db.execute(select(TradeEvent).where(TradeEvent.id == event_id))
            event = result.scalar_one_or_none()

            if event and event.current_status == EventStatus.PENDING_CONFIRM:
                # 模拟用户在券商下单后回填
                logger.info("\n[模拟用户操作] 等待 3 秒后自动回填...")
                await asyncio.sleep(3)

                await step4_manual_backfill(
                    event_id=event_id,
                    actual_price=1680.50,  # 模拟实际成交价
                    actual_qty=10,  # 10股
                )
            else:
                logger.info("\n事件未进入待确认状态，跳过回填步骤")

        # 查询待确认事件
        await demo_query_pending()

        logger.info("\n" + "=" * 60)
        logger.info("手动交易流程演示完成!")
        logger.info("=" * 60)
        logger.info("\n关键特性:")
        logger.info("  1. AI 信号生成后进入 PENDING_CONFIRM 状态")
        logger.info("  2. 硬风控检查在进入待确认前执行")
        logger.info("  3. 人工下单后回填触发状态更新为 POSITION_OPEN")
        logger.info("  4. 回填成功自动启动退出规划器监控")
        logger.info("  5. 所有操作可追溯，有完整日志")

    except KeyboardInterrupt:
        logger.info("\n演示被用户中断")
    except Exception as e:
        logger.error(f"演示过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 支持命令行参数
    import argparse

    parser = argparse.ArgumentParser(description="手动交易流程演示")
    parser.add_argument(
        "--confirm",
        metavar="EVENT_ID",
        help="确认手动交易（回填实际成交）"
    )
    parser.add_argument(
        "--price",
        type=float,
        metavar="PRICE",
        help="实际成交价格"
    )
    parser.add_argument(
        "--qty",
        type=int,
        metavar="QTY",
        help="实际成交数量"
    )
    parser.add_argument(
        "--query",
        action="store_true",
        help="查询待确认交易"
    )

    args = parser.parse_args()

    if args.confirm:
        # 回填模式
        if not args.price or not args.qty:
            print("错误: 回填模式需要 --price 和 --qty 参数")
            sys.exit(1)

        async def backfill():
            setup_logging()
            result = await confirm_manual_trade(
                event_id=args.confirm,
                actual_price=args.price,
                actual_quantity=args.qty,
            )
            print(f"\n回填结果: {result.message}")

        asyncio.run(backfill())

    elif args.query:
        # 查询模式
        async def query():
            setup_logging()
            await demo_query_pending()

        asyncio.run(query())

    else:
        # 演示模式
        asyncio.run(main())
