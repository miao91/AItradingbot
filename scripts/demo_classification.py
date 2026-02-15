"""
AI TradeBot - AI 驱动的新闻分类演示

展示三级过滤机制的实际效果：
1. 自动跳过低价值新闻（"某博主看好某币"）
2. 精准捕捉高价值新闻（"SEC 批准以太坊质押方案"）
3. 展示完整的估值分析流程
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from decision.engine import classify_news, get_batch_processor, NewsItem


async def demo_classification():
    """演示新闻分类功能"""
    print()
    print("=" * 70)
    print("  AI 驱动的新闻分类 - 三级过滤机制演示")
    print("=" * 70)
    print()

    # 测试用例
    test_cases = [
        {
            "title": "某知名博主发帖：比特币本周有望突破10万美元大关",
            "content": "知名加密货币分析师在社交媒体表示，根据当前走势，比特币有望在本周突破10万美元大关，建议投资者密切关注。",
            "source": "Twitter博主",
            "ticker": "BTC",
            "expected_score": 2.5,
            "expected_category": "忽略",
        },
        {
            "title": "SEC 批准以太坊质押方案，开启机构投资新时代",
            "content": "美国证券交易委员会（SEC）正式批准现货以太坊ETF，标志着以太坊质押服务获得监管认可，为机构投资者打开了大门。这一决定被视为加密货币行业的重大里程碑。",
            "source": "SEC官方公告",
            "ticker": "ETH",
            "expected_score": 9.0,
            "expected_category": "关键",
        },
        {
            "title": "某DeFi项目宣布与知名交易所合作",
            "content": "今日，某DeFi项目宣布与一家知名加密货币交易所建立战略合作伙伴关系，共同推动DeFi普及。",
            "source": "项目公告",
            "ticker": "UNKNOWN",
            "expected_score": 5.0,
            "expected_category": "跟踪",
        },
        {
            "title": "美联储主席鲍威尔：正在研究数字货币",
            "content": "美联储主席鲍威尔在国会听证会上表示，美联储正在继续研究数字货币，但暂无发行数字美元的计划。这一表态引发市场广泛关注。",
            "source": "国会听证会",
            "ticker": "USD/BTC",
            "expected_score": 7.5,
            "expected_category": "分析",
        },
        {
            "title": "比特币减半倒计时：还有100天",
            "content": "根据比特币网络协议，下一次减半事件预计在100天后发生，历史上减半事件往往对价格产生重大影响。",
            "source": "区块链数据",
            "ticker": "BTC",
            "expected_score": 8.5,
            "expected_category": "分析",
        },
        {
            "title": "某分析师预测：狗狗币将涨到1美元",
            "content": "某加密货币分析师在社交媒体发文，预测狗狗币（DOGE）将在未来几周内涨到1美元，引发社区热议。",
            "source": "分析师预测",
            "ticker": "DOGE",
            "expected_score": 2.0,
            "expected_category": "忽略",
        },
    ]

    print(f"{'序号':<5} {'标题':<50} {'评分':>6} {'类别':<8} {'估值级别':<12} {'影响时长':<10} {'理由'}")
    print("-" * 90)
    print()

    classifier = get_news_classifier()

    for i, case in enumerate(test_cases, 1):
        # 执行分类
        news = NewsItem(
            title=case["title"],
            content=case["content"],
            source=case["source"],
            ticker=case["ticker"],
        )

        print(f"[{i}] {case['title'][:45]}...")
        print(f"    来源: {case['source']}")
        print(f"    资产: {case['ticker']}")

        result = await classifier.classify(news)

        # 显示结果
        print(f"    实际评分: {result.total_score:.1f}/10.0")
        print(f"    细分得分:")
        print(f"      - 估值重塑: {result.valuation_reshaping:.1f}/10")
        print(f"      - 持续性: {result.sustainability:.1f}/10")
        print(f"      - 资产相关: {result.asset_relevance:.1f}/10")
        print(f"    类别: {result.category.value}")
        print(f"    估值级别: {result.valuation_level.value}")
        print(f"    影响时长: {result.duration_estimate.value}")
        print(f"    推理: {result.reasoning}")
        print(f"    耗时: {result.processing_time_ms:.0f}ms")

        # 验证是否符合预期
        expected_score = case.get("expected_score", 0)
        expected_category = case.get("expected_category", "")

        score_match = abs(result.total_score - expected_score) < 1.5
        category_match = result.category.value.lower() == expected_category.lower() if expected_category else True

        status = "✅" if (score_match and category_match) else "⚠️"
        print(f"    验证: {status} (预期: {expected_category}, {expected_score}分)")

        # 判断是否启动深度分析
        if result.total_score >= 7.0:
            print(f"    >>> 🔥 评分 >= 7.0，启动 Tavily 深度搜索 + 估值分析")
        else:
            print(f"    >>> ⏭️  评分 < 7.0，跳过深度分析（节省API调用）")

        print("-" * 90)
        print()

    # 总结统计
    print()
    print("=" * 70)
    print("  演示总结")
    print("=" * 70)
    print()
    print("三级过滤机制效果：")
    print("  1. 快速分类：GLM-4-Flash (< 100ms)")
    print("  2. 深度筛选：仅对 >7 分新闻启动 Tavily 搜索")
    print("  3. 估值分析：对高分新闻进行估值重塑分析")
    print()
    print("批处理优化：")
    print("  每 30 秒聚合一批消息")
    print("  统一交给 AI 批处理分类")
    print("  预计节省 70% 的 API 调用次数")
    print()
    print("=" * 70)


async def main():
    """主函数"""
    asyncio.run(demo_classification())


if __name__ == "__main__":
    main()
