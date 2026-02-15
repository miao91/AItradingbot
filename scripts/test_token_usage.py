"""
AI TradeBot - Token 使用量测试脚本

测试单次决策的 Prompt Tokens 消耗
目标：控制在 10,000 以下
"""
import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from perception.search import get_tavily_client
from shared.llm.clients import TokenCounter


async def test_tavily_token_usage():
    """测试 Tavily 搜索的 Token 消耗"""
    print("=" * 60)
    print("  Tavily AI 搜索 Token 测试")
    print("=" * 60)
    print()

    # 模拟股票事件
    ticker = "600519.SH"
    event_description = "贵州茅台签订50亿元战略合作协议，预计将对公司未来业绩产生积极影响"

    tavily = get_tavily_client()

    print(f"股票代码: {ticker}")
    print(f"事件描述: {event_description}")
    print()
    print("[Tavily] 开始搜索...")

    start_time = time.time()

    response = await tavily.search_for_stock_event(
        ticker=ticker,
        event_description=event_description
    )

    elapsed = time.time() - start_time

    if response.success:
        formatted_results = tavily.format_results_for_ai(response)
        token_count = TokenCounter.count_tokens(formatted_results)

        print(f"[Tavily] 搜索成功!")
        print(f"  - 结果数: {len(response.results)}")
        print(f"  - 压缩字符数: {response.total_compressed_chars}")
        print(f"  - 耗时: {elapsed:.2f}秒")
        print()
        print(f"[Token 估算]")
        print(f"  - 搜索结果 Token: {TokenCounter.format_token_count(token_count)}")
        print()
        print(f"[格式化结果预览]")
        print("-" * 60)
        print(formatted_results[:500] + "..." if len(formatted_results) > 500 else formatted_results)
        print("-" * 60)

        return {
            "success": True,
            "tokens": token_count,
            "results": len(response.results),
            "chars": response.total_compressed_chars
        }
    else:
        print(f"[Tavily] 搜索失败: {response.error_message}")
        return {"success": False, "error": response.error_message}


async def test_full_analysis_token_usage():
    """测试完整分析的 Token 消耗"""
    print()
    print("=" * 60)
    print("  完整分析流程 Token 测试")
    print("=" * 60)
    print()

    from decision.workflows.event_analyzer import analyze_event

    ticker = "600519.SH"
    event_description = "贵州茅台签订50亿元战略合作协议，预计将对公司未来业绩产生积极影响"

    print(f"股票代码: {ticker}")
    print(f"事件描述: {event_description}")
    print()
    print("[分析] 开始完整分析流程...")

    start_time = time.time()

    result = await analyze_event(
        ticker=ticker,
        event_description=event_description,
        event_type="announcement"
    )

    elapsed = time.time() - start_time

    print()
    print(f"[分析结果]")
    print(f"  - 成功: {result.success}")
    print(f"  - 完成步骤: {', '.join(result.steps_completed)}")
    print(f"  - 耗时: {elapsed:.2f}秒")
    print(f"  - Prompt Tokens: {TokenCounter.format_token_count(result.prompt_tokens_used)}")

    if result.error_message:
        print(f"  - 错误: {result.error_message}")

    print()
    print("=" * 60)
    print("  Token 消耗评估")
    print("=" * 60)
    print()

    if result.prompt_tokens_used > 0:
        status = "✅ PASS" if result.prompt_tokens_used < 10000 else "❌ FAIL"
        print(f"  Prompt Tokens: {result.prompt_tokens_used:,}")
        print(f"  目标上限: 10,000")
        print(f"  状态: {status}")
        print()
    else:
        print("  无法获取 Token 计数（可能是 API 未返回 usage 信息）")
        print()

    return result


async def main():
    """主函数"""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║     AI TradeBot - Token 使用量验证测试                  ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    # 测试 1: Tavily 搜索
    tavily_result = await test_tavily_token_usage()

    # 测试 2: 完整分析流程
    analysis_result = await test_full_analysis_token_usage()

    # 总结
    print()
    print("=" * 60)
    print("  测试总结")
    print("=" * 60)
    print()

    if tavily_result.get("success"):
        print(f"✅ Tavily 搜索: {tavily_result['tokens']} tokens ({tavily_result['chars']} 字符)")

    if analysis_result.prompt_tokens_used > 0:
        status = "✅ PASS" if analysis_result.prompt_tokens_used < 10000 else "❌ FAIL"
        print(f"{status} 完整分析: {analysis_result.prompt_tokens_used} tokens")
        print()
        print("目标达成!" if analysis_result.prompt_tokens_used < 10000 else "任务失败，需重新优化裁剪算法")
    else:
        print("⚠️ 无法验证 Token 消耗，请检查 API 配置")
        print()

    print("=" * 60)
    print()


if __name__ == "__main__":
    asyncio.run(main())
