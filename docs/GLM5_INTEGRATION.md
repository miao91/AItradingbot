# GLM-5 集成文档

## 概述

GLM-5 已成功集成到 AI TradeBot 项目中。GLM-5 是智谱 AI 最新旗舰模型，相比 GLM-4 有显著提升：

### GLM-5 优势
- **更强的推理能力**：更深层的因果分析和逻辑推演
- **更长的上下文窗口**：128k tokens（GLM-4 为 8k）
- **更好的代码生成能力**：适合估值引擎的 Python 代码生成
- **增强的多模态理解**：能综合分析更复杂的信息

## 集成位置

### 1. Shared LLM 客户端 (`shared/llm/clients.py`)
```python
from shared.llm.clients import get_glm5_client

# 使用 GLM-5
client = get_glm5_client()
response = await client.call(
    prompt="你的问题",
    temperature=0.7,
    max_tokens=2000
)
```

### 2. 决策矩阵客户端 (`decision/ai_matrix/glm5/client.py`)
```python
from decision.ai_matrix.glm5.client import get_glm5_client

# 用于事件推演和退出规划
client = get_glm5_client()
result = await client.reason_event(request)
```

### 3. 估值引擎 (`decision/engine/valuation_tool.py`)
```python
# 配置文件中设置
VALUATION_CONFIG = {
    "ai_model": "glm-5",  # 使用 GLM-5
    # 或 "glm-4" 使用 GLM-4
}
```

## 配置

### 环境变量

在 `.env` 文件中添加：

```bash
# 智谱 AI API Key（GLM-4 和 GLM-5 共用）
ZHIPU_API_KEY=your_zhipu_api_key_here

# 智谱 API Base URL（可选，默认如下）
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4

# 模型选择（可选）
ZHIPU_MODEL=glm-5
```

### 获取 API Key

1. 访问 [智谱 AI 开放平台](https://open.bigmodel.cn/)
2. 注册/登录账号
3. 在控制台获取 API Key
4. 将 API Key 添加到 `.env` 文件

## 使用方式

### 方式 1: 直接使用 Shared LLM 客户端

```python
import asyncio
from shared.llm.clients import get_glm5_client

async def example():
    client = get_glm5_client()

    response = await client.call(
        prompt="简述量化交易的三个核心要素",
        temperature=0.7,
        max_tokens=500
    )

    if response.success:
        print(f"响应: {response.content}")
        print(f"使用 tokens: {response.total_tokens}")
        print(f"耗时: {response.duration_ms:.0f}ms")
    else:
        print(f"错误: {response.error_message}")

asyncio.run(example())
```

### 方式 2: 使用估值引擎（自动选择 GLM-5）

```python
from decision.engine.valuation_tool import (
    IntelligentValuationEngine,
    ValuationInput
)

# 估值引擎已配置为使用 GLM-5
engine = IntelligentValuationEngine()

# 进行估值计算
inputs = ValuationInput(
    ticker="600519.SH",
    current_price=1680.50,
    # ... 其他参数
)

result = await engine.calculate(inputs)
```

### 方式 3: 手动选择 GLM-4 或 GLM-5

```python
# 使用 GLM-4
from decision.ai_matrix.glm4.client import get_glm4_client
glm4_client = await get_glm4_client()

# 使用 GLM-5
from decision.ai_matrix.glm5.client import get_glm5_client
glm5_client = await get_glm5_client()
```

## GLM-4 vs GLM-5 选择建议

| 使用场景 | 推荐模型 | 原因 |
|---------|---------|------|
| 估值计算 | **GLM-5** | 更强的代码生成和推理能力 |
| 简单分类 | GLM-4 | 成本更低，速度更快 |
| 长文本分析 | **GLM-5** | 128k 上下文窗口 |
| 实时决策 | GLM-4 | 响应速度更快 |
| 复杂推理 | **GLM-5** | 更深层的逻辑分析 |

## 测试

运行测试脚本验证集成：

```bash
python test_glm5.py
```

测试内容：
1. GLM-5 基础客户端调用
2. Shared LLM 客户端
3. 估值引擎集成

## API 参考

### GLM5Client 类

**方法**:
- `get_api_key_env()`: 返回 "ZHIPU_API_KEY"
- `get_base_url_env()`: 返回 "ZHIPU_BASE_URL"
- `get_model_env()`: 返回 "ZHIPU_MODEL"
- `get_default_model()`: 返回 "glm-5"
- `get_system_prompt()`: 返回系统提示词

**核心方法**:
- `chat(messages, temperature, max_tokens)`: 发送聊天请求
- `reason_event(request)`: 对事件进行深度推演
- `generate(prompt, max_tokens, temperature)`: 生成文本（兼容估值引擎）

### GLM5Client vs GLM4Client

| 特性 | GLM-5 | GLM-4 |
|------|-------|-------|
| 最大输入 tokens | 32,000 | 8,000 |
| 上下文窗口 | 128k | 8k |
| 超时时间 | 90秒 | 60秒 |
| 推理能力 | 更强 | 标准 |
| 代码生成 | 更准确 | 标准 |

## 故障排查

### 问题 1: API Key 未设置
```
WARNING: GLM5Client: API Key 未设置
```

**解决**: 在 `.env` 文件中设置 `ZHIPU_API_KEY`

### 问题 2: 身份验证失败
```
ERROR: Error code: 401 - {'error': {'code': '1000', 'message': '身份验证失败。'}}
```

**解决**:
1. 检查 API Key 是否正确
2. 确认 API Key 有效且未过期
3. 检查网络连接

### 问题 3: Base URL 为 None
```
Base URL: None
```

**解决**: 已在代码中添加默认值，如果仍有问题，手动设置环境变量 `ZHIPU_BASE_URL`

## 性能优化

1. **单例模式**: 使用 `get_glm5_client()` 获取全局单例，避免重复初始化
2. **连接池**: AsyncOpenAI 自动管理连接池
3. **超时设置**: GLM-5 默认 90 秒超时，可根据需要调整

## 未来改进

- [ ] 添加流式响应支持
- [ ] 实现 GLM-5 特有的长文档处理能力
- [ ] 添加更多 GLM-5 专用功能（如多模态理解）
- [ ] 性能监控和成本追踪

## 更新日志

### 2026-02-13
- ✅ 初始集成 GLM-5
- ✅ 添加 GLM5Client 到 shared/llm/clients.py
- ✅ 添加 GLM5Client 到 decision/ai_matrix/glm5/client.py
- ✅ 更新估值引擎支持 GLM-5
- ✅ 修复 GLM4Client 缺失的单例模式
- ✅ 添加默认 Base URL
- ✅ 创建测试脚本 test_glm5.py
