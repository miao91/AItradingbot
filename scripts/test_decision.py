"""
AI TradeBot - 决策层测试脚本

演示完整流程：
1. 输入股票代码
2. AI 协同分析（Kimi -> GLM-4 -> MiniMax）
3. 生成决策包
4. 存储到数据库
5. 展示结果
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database.session import db_manager, get_db_context
from sqlalchemy import select

from decision.workflows.event_analyzer import EventAnalyzer, analyze_event
from decision.engine.exit_planner import check_all_positions
from storage.models.trade_event import TradeEvent, EventStatus
from shared.logging import setup_logging, get_logger


logger = get_logger(__name__)


# 模拟公告内容（用于演示）
SAMPLE_ANNOUNCEMENT = """
# 测试公告

## 标题
浦发银行股份有限公司2024年年度业绩预增公告

## 内容

### 一、业绩预告情况

经财务部门初步测算，预计2024年年度实现归属于母公司所有者的净利润与上年同期相比，将增加20%到30%。

### 二、主要原因

1. 资产质量持续改善，信用减值损失同比减少
2. 利息净收入稳步增长
3. 数字化转型成效显著

### 三、风险提示

本次预告数据仅为初步测算结果，具体准确的财务数据以公司正式披露的2024年年度报告为准。

## 日期
2025年1月15日
"""


async def test_decision_workflow(ticker: str = "600000"):
    """
    测试完整的决策工作流

    Args:
        ticker: 股票代码
    """
    logger.info("=" * 60)
    logger.info(f"决策层测试 - {ticker}")
    logger.info("=" * 60)

    # 初始化数据库
    await db_manager.initialize_engine()

    # 创建分析器
    analyzer = EventAnalyzer()

    # 执行分析
    logger.info("\n开始 AI 协同分析...\n")

    result = await analyzer.analyze_event(
        ticker=ticker,
        event_description=SAMPLE_ANNOUNCEMENT,
        event_type="announcement",
        fetch_web_content=False,  # 使用模拟公告，不抓取网页
        fetch_market_data=False,  # 使用模拟价格
        save_to_db=True,
    )

    # 显示结果
    await display_analysis_result(result, ticker)

    return result


async def display_analysis_result(result, ticker: str) -> None:
    """展示分析结果"""
    logger.info("\n" + "=" * 60)
    logger.info("分析结果")
    logger.info("=" * 60)

    logger.info(f"\n事件 ID: {result.event_id}")
    logger.info(f"股票代码: {ticker}")

    if result.success:
        logger.info(f"分析状态: 成功")
        logger.info(f"完成步骤: {', '.join(result.steps_completed)}")

        if result.decision_bundle:
            bundle = result.decision_bundle

            logger.info(f"\n【决策包】")
            logger.info(f"  动作: {bundle.action}")
            logger.info(f"  数量: {bundle.quantity} 股")
            logger.info(f"  置信度: {bundle.confidence:.0%}")

            logger.info(f"\n【入场计划】")
            for key, value in bundle.entry_plan.items():
                logger.info(f"  {key}: {value}")

            logger.info(f"\n【退出计划】")
            exit_plan = bundle.exit_plan

            if exit_plan.get("take_profit"):
                tp = exit_plan["take_profit"]
                logger.info(f"  止盈: {tp.get('price', 'N/A')} - {tp.get('logic', 'N/A')}")

            if exit_plan.get("stop_loss"):
                sl = exit_plan["stop_loss"]
                logger.info(f"  止损: {sl.get('price', 'N/A')} - {sl.get('logic', 'N/A')}")

            if exit_plan.get("expiration"):
                exp = exit_plan["expiration"]
                logger.info(f"  失效: {exp.get('expire_time', 'N/A')} - {exp.get('logic', 'N/A')}")

            logger.info(f"\n【AI 推理过程】")
            logger.info(f"  {bundle.reasoning[:200]}...")

        # 查询数据库中的事件
        logger.info(f"\n【数据库记录】")
        await display_event_from_db(result.event_id)

    else:
        logger.info(f"分析状态: 失败")
        logger.info(f"错误信息: {result.error_message}")

    logger.info("\n" + "=" * 60)


async def display_event_from_db(event_id: str) -> None:
    """从数据库中查询并展示事件"""
    try:
        async with get_db_context() as db:
            result = await db.execute(
                select(TradeEvent).where(TradeEvent.id == event_id)
            )
            event = result.scalar_one_or_none()

            if event:
                logger.info(f"  事件ID: {event.id}")
                logger.info(f"  标的: {event.ticker}")
                logger.info(f"  状态: {event.current_status}")
                logger.info(f"  置信度: {event.confidence}")
                logger.info(f"  创建时间: {event.created_at}")

                logger.info(f"\n  AI 参与者: {', '.join(event.ai_participants)}")

                if event.reasoning_log:
                    logger.info(f"\n  AI 推理链路:")
                    for log_entry in event.reasoning_log:
                        logger.info(f"    - {log_entry.get('step')}: {log_entry.get('action')}")

                logger.info(f"\n  逻辑摘要:")
                logger.info(f"    {event.logic_summary[:200] if event.logic_summary else 'N/A'}...")

            else:
                logger.info(f"  未找到事件记录")

    except Exception as e:
        logger.error(f"查询数据库失败: {e}")


async def test_exit_planner():
    """测试退出规划器"""
    logger.info("\n" + "=" * 60)
    logger.info("退出规划器测试")
    logger.info("=" * 60)

    # 检查所有持仓
    signals = await check_all_positions()

    if signals:
        logger.info(f"\n触发 {len(signals)} 个退出信号:")
        for signal in signals:
            logger.info(
                f"\n  - {signal.ticker} ({signal.event_id})"
                f"\n    类型: {signal.exit_type}"
                f"\n    价格: {signal.exit_price:.2f}"
                f"\n    原因: {signal.reason}"
                f"\n    盈亏: {signal.unrealized_pnl_ratio*100 if signal.unrealized_pnl_ratio else 0:+.2f}%"
            )
    else:
        logger.info("\n当前无持仓或未触发退出条件")


async def test_full_workflow_with_manual_status():
    """测试完整工作流（包括手动将状态改为持仓中）"""
    logger.info("\n" + "=" * 60)
    logger.info("完整工作流测试（含持仓状态变更）")
    logger.info("=" * 60)

    # 1. 运行决策工作流
    result = await test_decision_workflow()

    if result.success and result.decision_bundle:
        event_id = result.event_id

        # 2. 模拟入场（将状态改为持仓中）
        logger.info(f"\n模拟执行入场...")
        await simulate_entry(event_id)

        # 3. 运行退出规划器检查
        logger.info(f"\n运行退出规划器...")
        await test_exit_planner()

    else:
        logger.info("\n决策生成失败，跳过后续测试")


async def simulate_entry(event_id: str) -> None:
    """模拟入场执行"""
    try:
        async with get_db_context() as db:
            result = await db.execute(
                select(TradeEvent).where(TradeEvent.id == event_id)
            )
            event = result.scalar_one_or_none()

            if event:
                # 更新为持仓中状态
                event.current_status = EventStatus.POSITION_OPEN
                event.actual_entry_price = 10.00  # 模拟入场价
                event.actual_entry_time = datetime.now()
                event.actual_quantity = 1000

                await db.commit()

                logger.info(f"已模拟入场: {event_id} @ 10.00")
            else:
                logger.error(f"事件不存在: {event_id}")

    except Exception as e:
        logger.error(f"模拟入场失败: {e}")


async def show_all_events():
    """显示数据库中的所有事件"""
    logger.info("\n" + "=" * 60)
    logger.info("数据库中的所有事件")
    logger.info("=" * 60)

    try:
        async with get_db_context() as db:
            result = await db.execute(select(TradeEvent))
            events = result.scalars().all()

            if events:
                logger.info(f"\n共 {len(events)} 个事件:\n")

                for event in events:
                    logger.info(f"  - {event.id}")
                    logger.info(f"    标的: {event.ticker}")
                    logger.info(f"    状态: {event.current_status}")
                    logger.info(f"    创建时间: {event.created_at}")
                    logger.info(f"    逻辑: {event.logic_summary[:100] if event.logic_summary else 'N/A'}...")
                    logger.info("")
            else:
                logger.info("\n数据库中暂无事件")

    except Exception as e:
        logger.error(f"查询失败: {e}")


async def main():
    """主函数"""
    setup_logging()

    logger.info("\n")
    logger.info("=" * 60)
    logger.info("AI TradeBot - 决策层测试")
    logger.info("=" * 60)
    logger.info("\n")

    # 测试参数
    test_ticker = "600000"  # 浦发银行

    try:
        # 显示当前数据库中的事件
        await show_all_events()

        # 运行决策工作流
        await test_decision_workflow(test_ticker)

        # 可选：测试完整工作流（含持仓）
        # await test_full_workflow_with_manual_status()

        logger.info("\n" + "=" * 60)
        logger.info("测试完成!")
        logger.info("=" * 60)

        # 显示更新后的事件列表
        await show_all_events()

    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
