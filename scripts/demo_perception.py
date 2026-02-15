"""
AI TradeBot - 感知层简化演示

演示功能：
1. 模拟实时行情数据获取
2. HTML 转 Markdown 演示
3. 缓存功能展示
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from perception.openclaw.formatter import html_to_markdown
from perception.market_data import CacheManager
from shared.logging import setup_logging, get_logger


logger = get_logger(__name__)


def demo_html_to_markdown():
    """演示 HTML 转 Markdown"""
    logger.info("=" * 60)
    logger.info("[演示 1] HTML 转 Markdown")
    logger.info("=" * 60)

    # 模拟一个公告页面的 HTML
    sample_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>浦发银行：2024年年度业绩预增公告_东方财富网</title>
    </head>
    <body>
        <div class="newscontent">
            <h1>浦发银行股份有限公司2024年年度业绩预增公告</h1>

            <div class="time">2025-01-15 18:30</div>

            <p><strong>证券代码：</strong>600000</p>
            <p><strong>证券简称：</strong>浦发银行</p>

            <h2>一、本期业绩预告情况</h2>
            <p>1. 经财务部门初步测算，预计2024年年度实现归属于母公司所有者的净利润与上年同期（法定披露数据）相比，将增加15%到25%。</p>

            <h2>二、本期业绩预增的主要原因</h2>
            <p>公司坚持战略定力，深化结构调整，持续推进数字化转型。主要原因是：</p>
            <ul>
                <li>资产质量持续改善，信用减值损失同比减少</li>
                <li>利息净收入稳步增长</li>
                <li>中间业务收入结构优化</li>
            </ul>

            <h2>三、风险提示</h2>
            <p>本次预告数据仅为初步核算结果，具体准确的财务数据以公司正式披露的2024年年度报告为准。</p>

            <p>敬请广大投资者理性投资，注意风险。</p>

            <p style="text-align:right">特此公告。</p>

            <p style="text-align:right">浦发银行股份有限公司董事会</p>
            <p style="text-align:right">2025年1月15日</p>
        </div>

        <div class="advertisement">广告内容</div>
        <div class="related-news">相关新闻推荐</div>
    </body>
    </html>
    """

    # 转换为 Markdown
    result = html_to_markdown(sample_html, url="http://example.com/announcement")

    logger.info(f"转换结果:")
    logger.info(f"  标题: {result.title}")
    logger.info(f"  字符数: {result.char_count}")
    logger.info(f"  字数: {result.word_count}")
    logger.info(f"  处理时间: {result.processing_time:.3f}秒")

    logger.info("\nMarkdown 内容:")
    logger.info("-" * 60)
    logger.info(result.markdown)
    logger.info("-" * 60)

    logger.info("\n[成功] HTML 转 Markdown 演示完成\n")


def demo_cache_manager():
    """演示缓存管理器"""
    logger.info("=" * 60)
    logger.info("[演示 2] 缓存管理器")
    logger.info("=" * 60)

    cache = CacheManager(cache_dir="data/cache")

    # 测试数据
    test_data = {
        "symbol": "600000.SH",
        "name": "浦发银行",
        "price": 10.50,
        "change": 0.05,
    }

    # 写入缓存
    logger.info("写入缓存...")
    cache.set("stock_quote", test_data, symbol="600000.SH")

    # 读取缓存
    logger.info("读取缓存...")
    cached_data = cache.get("stock_quote", symbol="600000.SH")

    if cached_data:
        logger.info(f"缓存命中: {cached_data}")
    else:
        logger.info("缓存未命中")

    # 测试缓存键唯一性
    logger.info("\n测试不同参数的缓存键...")
    cache.set("test", {"value": 1}, param="a")
    cache.set("test", {"value": 2}, param="b")

    data_a = cache.get("test", param="a")
    data_b = cache.get("test", param="b")

    logger.info(f"  param=a: {data_a}")
    logger.info(f"  param=b: {data_b}")

    logger.info("\n[成功] 缓存管理器演示完成\n")


def demo_market_data_models():
    """演示行情数据模型"""
    logger.info("=" * 60)
    logger.info("[演示 3] 行情数据模型")
    logger.info("=" * 60)

    from perception.market_data import RealtimeQuote, DailyBar

    # 创建实时行情
    quote = RealtimeQuote(
        symbol="600000.SH",
        name="浦发银行",
        current_price=10.55,
        open_price=10.40,
        high_price=10.60,
        low_price=10.35,
        prev_close=10.30,
        volume=1000000,
        amount=10550000.0,
        bid1=10.54,
        bid1_volume=5000,
        ask1=10.55,
        ask1_volume=3000,
    )

    logger.info("实时行情:")
    logger.info(f"  {quote.name} ({quote.symbol})")
    logger.info(f"  最新: {quote.current_price:.2f}")
    logger.info(f"  涨跌: {(quote.current_price - quote.prev_close) / quote.prev_close * 100:+.2f}%")
    logger.info(f"  买一: {quote.bid1:.2f} x {quote.bid1_volume:,}")
    logger.info(f"  卖一: {quote.ask1:.2f} x {quote.ask1_volume:,}")

    # 创建日K线
    bar = DailyBar(
        trade_date="20250111",
        open=10.40,
        high=10.60,
        low=10.35,
        close=10.55,
        volume=1000000,
        amount=10550000.0,
    )

    logger.info("\n日K线:")
    logger.info(f"  日期: {bar.trade_date}")
    logger.info(f"  开/高/低/收: {bar.open:.2f} / {bar.high:.2f} / {bar.low:.2f} / {bar.close:.2f}")
    logger.info(f"  成交量: {bar.volume:,}")

    logger.info("\n[成功] 行情数据模型演示完成\n")


def main():
    """主函数"""
    setup_logging()

    logger.info("\n")
    logger.info("=" * 60)
    logger.info("AI TradeBot - 感知层功能演示")
    logger.info("=" * 60)
    logger.info("\n")

    # 演示 1: HTML 转 Markdown
    demo_html_to_markdown()

    # 演示 2: 缓存管理器
    demo_cache_manager()

    # 演示 3: 行情数据模型
    demo_market_data_models()

    logger.info("=" * 60)
    logger.info("所有演示完成!")
    logger.info("=" * 60)
    logger.info("\n")
    logger.info("功能说明:")
    logger.info("  1. HTML 转 Markdown: 清洗后的内容可直接喂给 AI")
    logger.info("  2. 缓存管理器: 避免重复 API 调用，节省积分")
    logger.info("  3. 数据模型: 完整的类型注解，支持验证")
    logger.info("  4. 重试机制: 自动重试失败的请求（3次）")
    logger.info("  5. 反爬策略: User-Agent 轮换、Headless 模式")
    logger.info("\n")


if __name__ == "__main__":
    main()
