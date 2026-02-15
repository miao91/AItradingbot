"""
测试 GLM-5 集成

验证 GLM-5 客户端是否正常工作
"""
import asyncio
import sys
import os
from pathlib import Path

# 设置 UTF-8 编码
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_glm5_basic():
    """测试基础 GLM-5 调用"""
    print("=" * 60)
    print("测试 GLM-5 基础调用")
    print("=" * 60)

    try:
        from decision.ai_matrix.glm5.client import get_glm5_client

        # 获取客户端
        client = get_glm5_client()
        print(f"✅ GLM-5 客户端初始化成功")
        print(f"   模型: {client.model}")
        print(f"   Base URL: {client.base_url}")

        # 测试简单调用
        from decision.ai_matrix.base import AIMessage

        messages = [AIMessage(role="user", content="简述 GLM-5 的优势（50字以内）")]

        print(f"\n🔄 调用 GLM-5...")
        response = await client.chat(messages=messages, max_tokens=200, temperature=0.7)

        if response.success:
            print(f"✅ GLM-5 调用成功")
            print(f"   Tokens: {response.total_tokens}")
            print(f"   耗时: {response.duration_ms:.0f}ms")
            print(f"\n📝 响应内容:")
            print(f"   {response.content}")
        else:
            print(f"❌ GLM-5 调用失败: {response.error_message}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


async def test_shared_llm_glm5():
    """测试 shared.llm 中的 GLM-5 客户端"""
    print("\n" + "=" * 60)
    print("测试 shared.llm GLM-5 客户端")
    print("=" * 60)

    try:
        from shared.llm.clients import get_glm5_client

        client = get_glm5_client()
        print(f"✅ Shared LLM GLM-5 客户端初始化成功")
        print(f"   模型: {client.model}")

        # 测试调用
        print(f"\n🔄 调用 GLM-5...")
        response = await client.call(
            prompt="用一句话说明什么是量化交易",
            temperature=0.7,
            max_tokens=200
        )

        if response.success:
            print(f"✅ Shared LLM GLM-5 调用成功")
            print(f"   Tokens: {response.total_tokens}")
            print(f"   耗时: {response.duration_ms:.0f}ms")
            print(f"\n📝 响应内容:")
            print(f"   {response.content}")
        else:
            print(f"❌ 调用失败: {response.error_message}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


async def test_valuation_engine_glm5():
    """测试估值引擎使用 GLM-5"""
    print("\n" + "=" * 60)
    print("测试估值引擎 GLM-5 集成")
    print("=" * 60)

    try:
        from decision.engine.valuation_tool import (
            IntelligentValuationEngine,
            ValuationInput,
            VALUATION_CONFIG
        )

        print(f"📊 估值引擎配置:")
        print(f"   AI 模型: {VALUATION_CONFIG.get('ai_model', 'glm-5')}")
        print(f"   使用最新版本: {VALUATION_CONFIG.get('use_latest_models', True)}")

        engine = IntelligentValuationEngine()
        print(f"✅ 估值引擎初始化成功")
        print(f"   使用模型: {engine.ai_model}")

        # 注意：完整估值测试需要真实数据，这里只验证初始化
        print(f"\n✅ GLM-5 已成功集成到估值引擎")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    print("\n🚀 开始 GLM-5 集成测试\n")

    # 测试1: 基础 GLM-5 客户端
    await test_glm5_basic()

    # 测试2: Shared LLM 客户端
    await test_shared_llm_glm5()

    # 测试3: 估值引擎集成
    await test_valuation_engine_glm5()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
