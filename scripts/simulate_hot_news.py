"""
AI TradeBot - 模拟突发新闻脚本

模拟一条突发利好消息，验证实时监测到网站接口更新的完整流程
预期：10秒内完成从"抓取"到"网站接口更新"
"""
import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from perception.openclaw.live_monitor import NewsItem
from decision.workflows.realtime_router import on_live_news
from core.database.session import get_db_context
from storage.models.trade_event import TradeEvent, EventStatus
from sqlalchemy import select, desc


# =============================================================================
# 模拟新闻模板
# =============================================================================

MOCK_NEWS_TEMPLATES = [
    {
        "title": "重大利好！{ticker}签订50亿元战略合作协议",
        "content": "{ticker}今日公告，公司与某大型央企签订战略合作协议，涉及金额50亿元，预计将对公司未来业绩产生积极影响。市场分析人士认为，此举将显著提升公司的行业地位和盈利能力。",
        "ticker": "600519.SH",
        "source": "simulation"
    },
    {
        "title": "{ticker}半年度业绩预增150%，超市场预期",
        "content": "{ticker}发布业绩预告，预计2024年上半年净利润同比增长150%-180%，远超市场预期。公司表示业绩大幅增长主要受益于主营业务强劲增长和新产品市场表现优异。",
        "ticker": "300750.SZ",
        "source": "simulation"
    },
    {
        "title": "政策利好！{ticker}所在行业获国家重点支持",
        "content": "国务院今日发布政策文件，将{ticker}所在的新能源行业列为国家重点支持产业，未来三年将投入超过1000亿元支持产业发展。行业龙头上市公司将直接受益。",
        "ticker": "300014.SZ",
        "source": "simulation"
    },
    {
        "title": "紧急公告：{ticker}控股股东拟增持5亿元",
        "content": "{ticker}公告，公司控股股东基于对公司未来发展的信心，计划在未来6个月内增持公司股份，增持金额不低于5亿元。这是近年最大规模的增持计划。",
        "ticker": "601318.SH",
        "source": "simulation"
    }
]


# =============================================================================
# 工具函数
# =============================================================================

def print_banner(text: str):
    """打印横幅"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_step(step: int, text: str):
    """打印步骤"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] 步骤 {step}: {text}")


async def check_database_for_new_event() -> dict:
    """检查数据库中的最新事件"""
    async with get_db_context() as db:
        result = await db.execute(
            select(TradeEvent)
            .order_by(desc(TradeEvent.created_at))
            .limit(1)
        )
        event = result.scalar_one_or_none()

        if event:
            return {
                "id": event.id,
                "ticker": event.ticker,
                "status": event.current_status.value,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "summary": event.event_description or event.logic_summary or ""
            }
        return None


async def check_public_api() -> dict:
    """检查公共 API 接口"""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/api/v1/public/active_events") as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # 获取最新的事件
                    if data.get("events") and len(data["events"]) > 0:
                        latest = data["events"][0]
                        return {
                            "found": True,
                            "event_id": latest.get("id"),
                            "ticker": latest.get("ticker"),
                            "status": latest.get("current_status"),
                            "status_display": latest.get("status_display"),
                            "summary": latest.get("event_summary", "")
                        }
                    else:
                        return {"found": False}
        return {"error": "API 请求失败"}
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# 主流程
# =============================================================================

async def run_simulation(news_template: dict = None):
    """运行完整模拟流程"""

    print_banner("AI TradeBot - 实时监测全流程模拟测试")

    # 使用提供的模板或默认模板
    if news_template is None:
        news_template = MOCK_NEWS_TEMPLATES[0]

    ticker = news_template["ticker"]

    # 步骤 1: 显示模拟新闻
    print_step(1, "生成模拟新闻")
    print(f"  标题: {news_template['title'].format(ticker=ticker)}")
    print(f"  来源: {news_template['source']}")
    print(f"  时间: {datetime.now().strftime('%H:%M:%S')}")
    print()

    # 创建 NewsItem
    start_time = time.time()

    news = NewsItem(
        title=news_template["title"].format(ticker=ticker),
        url="simulation://local/test",
        publish_time=datetime.now().strftime("%H:%M:%S"),
        source=news_template["source"],
        content=news_template["content"].format(ticker=ticker),
        ticker=ticker
    )

    # 步骤 2: 触发路由处理
    print_step(2, "触发实时路由处理")
    print(f"  调用 on_live_news(news)...")
    print()

    try:
        event_id = await on_live_news(news)

        elapsed_route = time.time() - start_time
        print(f"  ✓ 路由完成，耗时: {elapsed_route:.2f}秒")

        if event_id:
            print(f"  ✓ 事件ID: {event_id}")
        else:
            print(f"  ! 事件被初筛过滤或创建失败")

    except Exception as e:
        print(f"  ✗ 路由异常: {e}")
        return False

    print()

    # 步骤 3: 检查数据库
    print_step(3, "验证数据库存储")
    await asyncio.sleep(1)  # 等待数据库写入

    db_event = await check_database_for_new_event()

    if db_event:
        elapsed_db = time.time() - start_time
        print(f"  ✓ 数据库验证成功，总耗时: {elapsed_db:.2f}秒")
        print(f"    事件ID: {db_event['id']}")
        print(f"    股票代码: {db_event['ticker']}")
        print(f"    当前状态: {db_event['status']}")
        print(f"    创建时间: {db_event['created_at']}")
    else:
        print(f"  ! 数据库中未找到新事件")
        elapsed_db = time.time() - start_time

    print()

    # 步骤 4: 检查公共 API
    print_step(4, "验证公共 API 接口")
    await asyncio.sleep(1)  # 等待 API 更新

    api_result = await check_public_api()

    elapsed_api = time.time() - start_time
    print(f"  总耗时: {elapsed_api:.2f}秒")
    print()

    if api_result.get("found"):
        print(f"  ✓ API 接口验证成功")
        print(f"    事件ID: {api_result['event_id']}")
        print(f"    股票代码: {api_result['ticker']}")
        print(f"    状态: {api_result['status_display']}")
        print(f"    摘要: {api_result['summary'][:80]}...")
    else:
        print(f"  ! API 未返回事件（可能被初筛过滤）")
        if api_result.get("error"):
            print(f"  错误: {api_result['error']}")

    print()

    # 步骤 5: 总结
    print_step(5, "测试总结")
    print(f"  总耗时: {elapsed_api:.2f}秒")
    print(f"  目标: 10秒内完成")

    if elapsed_api <= 10:
        print(f"  ✓ 性能达标！")
    else:
        print(f"  ! 性能未达标，超出 {elapsed_api - 10:.2f}秒")

    print()
    print(f"  验证结果:")
    print(f"    {'✓' if db_event else '✗'} 数据库写入: {'成功' if db_event else '失败'}")
    print(f"    {'✓' if api_result.get('found') else '✗'} API 接口: {'成功' if api_result.get('found') else '失败'}")

    print()
    print("=" * 60)
    print()

    return elapsed_api <= 10 and db_event is not None


# =============================================================================
# 命令行入口
# =============================================================================

async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="模拟突发新闻测试实时监测")
    parser.add_argument(
        "--template",
        type=int,
        choices=range(len(MOCK_NEWS_TEMPLATES)),
        default=0,
        help="使用指定的新闻模板 (0-{})".format(len(MOCK_NEWS_TEMPLATES) - 1)
    )
    parser.add_argument(
        "--custom",
        type=str,
        help="自定义新闻标题"
    )
    parser.add_argument(
        "--ticker",
        type=str,
        help="股票代码（用于自定义新闻）"
    )

    args = parser.parse_args()

    # 检查 API 服务是否运行
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status != 200:
                    print("错误: API 服务未正常运行")
                    print("请先启动服务: python run_all.py")
                    return
    except Exception:
        print("错误: 无法连接到 API 服务")
        print("请先启动服务: python run_all.py")
        return

    # 选择新闻模板
    if args.custom:
        # 自定义新闻
        template = {
            "title": args.custom,
            "content": f"{args.custom}（模拟内容）",
            "ticker": args.ticker or "600519.SH",
            "source": "simulation"
        }
    else:
        template = MOCK_NEWS_TEMPLATES[args.template]

    # 运行模拟
    success = await run_simulation(template)

    # 退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
