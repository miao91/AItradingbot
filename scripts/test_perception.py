"""
AI TradeBot - 感知层测试脚本

演示功能：
1. 获取股票实时行情
2. 爬取东方财富公告页面
3. 转换为 Markdown 格式
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from perception.market_data import MarketDataManager, get_market_manager
from perception.openclaw.browser_engine import OpenClawEngine, deep_fetch
from perception.openclaw.formatter import html_to_markdown, CleanedContent
from shared.logging import setup_logging, get_logger


logger = get_logger(__name__)


async def test_realtime_quote(symbol: str = "600000"):
    """
    测试获取实时行情

    Args:
        symbol: 股票代码
    """
    logger.info("=" * 60)
    logger.info(f"[测试 1] 获取实时行情: {symbol}")
    logger.info("=" * 60)

    try:
        market_mgr = get_market_manager()

        # 获取实时行情
        quote = await market_mgr.get_realtime_quote(symbol)

        logger.info(f"股票: {quote.name} ({quote.symbol})")
        logger.info(f"最新价: {quote.current_price:.2f}")
        logger.info(f"涨跌幅: {(quote.current_price - quote.prev_close) / quote.prev_close * 100:.2f}%")
        logger.info(f"开盘: {quote.open_price:.2f}")
        logger.info(f"最高: {quote.high_price:.2f}")
        logger.info(f"最低: {quote.low_price:.2f}")
        logger.info(f"成交量: {quote.volume:,}")
        logger.info(f"成交额: {quote.amount:,.2f}")

        # 五档盘口
        if quote.bid1:
            logger.info("\n五档盘口:")
            logger.info(f"  买一: {quote.bid1:.2f} x {quote.bid1_volume or 0:,}")
            if quote.ask1:
                logger.info(f"  卖一: {quote.ask1:.2f} x {quote.ask1_volume or 0:,}")

        logger.info("\n[成功] 实时行情获取成功\n")
        return quote

    except Exception as e:
        logger.error(f"[失败] 实时行情获取失败: {e}\n")
        return None


async def test_daily_bars(symbol: str = "600000.SH"):
    """
    测试获取历史K线

    Args:
        symbol: 股票代码（Tushare 格式）
    """
    logger.info("=" * 60)
    logger.info(f"[测试 2] 获取历史K线: {symbol}")
    logger.info("=" * 60)

    try:
        market_mgr = get_market_manager()

        # 获取最近 10 天的K线
        bars = market_mgr.get_daily_bars(
            symbol=symbol,
            start_date="20250101",
            end_date="20250211",
        )

        logger.info(f"获取到 {len(bars)} 条K线数据")

        if bars:
            latest = bars[-1]
            logger.info(f"最新交易日: {latest.trade_date}")
            logger.info(f"  开: {latest.open:.2f}")
            logger.info(f"  高: {latest.high:.2f}")
            logger.info(f"  低: {latest.low:.2f}")
            logger.info(f"  收: {latest.close:.2f}")
            logger.info(f"  量: {latest.volume:,}")

            # 显示最近 5 天
            logger.info("\n最近 5 个交易日:")
            for bar in bars[-5:]:
                change = (bar.close - bar.open) / bar.open * 100
                logger.info(
                    f"  {bar.trade_date}: {bar.close:.2f} "
                    f"({change:+.2f}%)"
                )

        logger.info("\n[成功] 历史K线获取成功\n")
        return bars

    except Exception as e:
        logger.error(f"[失败] 历史K线获取失败: {e}\n")
        return None


async def test_web_scraping():
    """
    测试网页爬取和格式转换

    爬取浦发银行在东方财富的公告页面
    """
    logger.info("=" * 60)
    logger.info("[测试 3] 网页爬取与格式转换")
    logger.info("=" * 60)

    # 测试 URL（使用一个简单的财经新闻页面）
    test_url = "http://www.eastmoney.com/"

    try:
        # 使用 OpenClaw 抓取
        logger.info(f"正在访问: {test_url}")

        async with OpenClawEngine(headless=True) as engine:
            result = await engine.deep_fetch(
                url=test_url,
                wait_for_selector="body",
                screenshot=False,
            )

            if result.success:
                logger.info(f"抓取成功!")
                logger.info(f"  标题: {result.title}")
                logger.info(f"  内容长度: {len(result.content)} 字符")
                logger.info(f"  抓取耗时: {result.fetch_time:.2f} 秒")

                # 转换为 Markdown
                logger.info("\n正在转换为 Markdown...")

                cleaned = html_to_markdown(
                    result.html or "",
                    url=test_url,
                    style="jina",
                )

                logger.info(f"转换完成!")
                logger.info(f"  Markdown 长度: {cleaned.char_count} 字符")
                logger.info(f"  字数: {cleaned.word_count} 词")
                logger.info(f"  处理耗时: {cleaned.processing_time:.3f} 秒")
                logger.info(f"  压缩比: {cleaned.metadata.get('compression_ratio', 0):.1f}%")

                # 显示前 500 字符预览
                preview = cleaned.markdown[:500]
                if len(cleaned.markdown) > 500:
                    preview += "\n\n... (更多内容已省略)"

                logger.info("\nMarkdown 预览:")
                logger.info("-" * 60)
                logger.info(preview)
                logger.info("-" * 60)

                logger.info("\n[成功] 网页爬取与格式转换成功\n")
                return cleaned

            else:
                logger.error(f"抓取失败: {result.error_message}")
                logger.info(f"状态: {result.metadata.get('status', 'unknown')}\n")
                return None

    except Exception as e:
        logger.error(f"[失败] 网页爬取失败: {e}\n")
        import traceback
        traceback.print_exc()
        return None


async def test_announcement_scraping(symbol: str = "600000"):
    """
    测试爬取特定股票的公告页面

    Args:
        symbol: 股票代码
    """
    logger.info("=" * 60)
    logger.info(f"[测试 4] 爬取公告页面: {symbol}")
    logger.info("=" * 60)

    # 东方财富公告页 URL
    # 注意：实际 URL 可能需要根据具体公告调整
    test_url = f"http://data.eastmoney.com/notices/getlist.ashx?"

    try:
        # 股票基本信息
        market_mgr = get_market_manager()
        info = market_mgr.get_stock_info(f"{symbol}.SH")

        if info:
            logger.info(f"股票: {info.get('name')} ({info.get('symbol')})")

        # 这里演示爬取东方财富公告列表页
        logger.info(f"访问公告列表...")

        async with OpenClawEngine(headless=True) as engine:
            result = await engine.deep_fetch(
                url="http://www.eastmoney.com/",
                wait_for_selector="body",
            )

            if result.success:
                # 转换为 Markdown
                cleaned = html_to_markdown(result.html or "", url=result.url)

                logger.info(f"页面标题: {cleaned.title}")
                logger.info(f"获取内容: {cleaned.char_count} 字符")

                # 查找包含"公告"的段落
                if "公告" in cleaned.markdown:
                    # 提取包含公告的部分
                    lines = cleaned.markdown.split("\n")
                    announcement_lines = [
                        line for line in lines
                        if "公告" in line or "公告" in line.lower()
                    ]

                    if announcement_lines:
                        logger.info("\n找到的公告相关内容:")
                        for line in announcement_lines[:5]:
                            logger.info(f"  - {line[:100]}")

                logger.info("\n[成功] 公告页面爬取成功\n")
                return cleaned

        logger.info("[提示] 实际公告URL需要根据具体事件调整\n")
        return None

    except Exception as e:
        logger.error(f"[失败] 公告页面爬取失败: {e}\n")
        return None


async def main():
    """主测试函数"""
    setup_logging()
    logger.info("\n")
    logger.info("=" * 60)
    logger.info("AI TradeBot - 感知层测试")
    logger.info("=" * 60)
    logger.info("\n")

    # 测试参数
    test_symbol = "600000"  # 浦发银行

    try:
        # 测试 1: 实时行情
        quote = await test_realtime_quote(test_symbol)

        # 测试 2: 历史K线
        bars = await test_daily_bars(f"{test_symbol}.SH")

        # 测试 3: 网页爬取
        cleaned = await test_web_scraping()

        # 测试 4: 公告爬取
        await test_announcement_scraping(test_symbol)

        logger.info("=" * 60)
        logger.info("所有测试完成!")
        logger.info("=" * 60)
        logger.info("\n")

        # 测试结果总结
        logger.info("测试结果总结:")
        logger.info(f"  实时行情: {'✓ 成功' if quote else '✗ 失败'}")
        logger.info(f"  历史K线: {'✓ 成功' if bars else '✗ 失败'}")
        logger.info(f"  网页爬取: {'✓ 成功' if cleaned else '✗ 失败'}")

    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(main())
