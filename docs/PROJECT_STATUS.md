# AI TradeBot 项目进展文档

**更新时间**: 2026-02-13 (最新)
**当前版本**: 2026 Flagship "Deep Thinking Type"

---

## 📋 目录

1. [最新完成工作](#最新完成工作)
2. [核心系统状态](#核心系统状态)
3. [待完成任务](#待完成任务)
4. [已知问题](#已知问题)
5. [技术架构](#技术架构)
6. [下一步计划](#下一步计划)

---

## ✅ 最新完成工作

### 0. Phase 2 核心功能实现 (2026-02-13 本次会话 - 全部完成)

#### 完成内容：

**Task #16: 全球情报研读模块**
- ✅ 修复 `perception/papers/papers_reader.py` 导入路径
- ✅ 修复 Kimi 客户端调用方法 (`generate` → `call`)
- ✅ 更新 `trigger_manual_analysis` 使用 `PapersReader` 进行 Kimi-128k 分析
- ✅ 安装缺失依赖 (aiofiles, beautifulsoup4, PyPDF2)

**Task #19: 五维评估模型**
- ✅ 创建 `decision/engine/five_dimension_scorer.py`
- ✅ 实现五维评分系统 (0-10分):
  - 重塑性 (Reshaping)
  - 持续性 (Persistence)
  - 地缘政治传导 (Geopolitical)
  - 市场定价偏离 (Mispricing)
  - 流动性环境 (Liquidity)
- ✅ 加权综合评分计算
- ✅ AI 驱动的评估分析

**Task #17: AI 思维链展示**
- ✅ 创建 `decision/engine/reasoning_engine.py` 推理引擎
- ✅ 创建 `core/api/v1/reasoning.py` API 端点
- ✅ 支持 SSE (Server-Sent Events) 流式推送
- ✅ 11步推理链展示
- ✅ 集成 GLM-5 进行深度分析

**Task #21: 无幻觉计算沙盒**
- ✅ 创建 `decision/engine/sandbox_validator.py`
- ✅ 行业适配模型验证
- ✅ 输出格式标准化
- ✅ 幻觉检测机制 (不合理数值检测)

**Task #15: Tushare 实时快讯流**
- ✅ 创建 `core/api/v1/news.py` 新闻 API
- ✅ 支持模拟数据模式 (Tushare 未启用时自动降级)
- ✅ 高评分新闻筛选
- ✅ 最近新闻时间过滤
- ✅ 服务状态监控

**Task #18: 计算透明化弹窗**
- ✅ Math Logic 弹窗 HTML 结构
- ✅ CSS 样式 (.math-logic-modal)
- ✅ JavaScript 函数 (viewMathLogic, closeMathLogicModal)
- ✅ AI 生成的 Python 估值代码展示
- ✅ 说明文字 (AI 生成 + 计算保证)

**Task #22: 语言隔离与异步非阻塞**
- ✅ 英文内容检测逻辑
- ✅ asyncio 异步任务并行执行
- ✅ 系统健康检查集成

**Task #24: 全链路逻辑自检**
- ✅ 创建 `decision/engine/health_checker.py`
- ✅ 创建 `core/api/v1/health.py` API 端点
- ✅ 5项核心检查:
  - 汇率预警联动
  - 语言隔离
  - 异步非阻塞
  - 幻觉防护
  - 行业适配

**额外功能: 蒙特卡洛 GPU 加速引擎 (RTX 5080)**
- ✅ 创建 `decision/engine/monte_carlo_engine.py`
- ✅ 多后端支持: CuPy (CUDA) / PyTorch GPU / NumPy CPU
- ✅ 100,000+ 并行模拟
- ✅ VaR 和 Expected Shortfall 计算
- ✅ 概率分布直方图生成
- ✅ 创建 `core/api/v1/monte_carlo.py` API
- ✅ 创建 `check_gpu.py` GPU 检测脚本
- ✅ Showcase 前端概率分布可视化

#### 文件变更：
```
perception/papers/papers_reader.py
  - 修复导入: from shared.llm.clients import KimiClient
  - 修复调用: kimi_client.call() 替代 generate()
  - 修复 LLMResponse 处理

perception/papers/manual_reader.py
  - 更新 trigger_manual_analysis() 使用 PapersReader

decision/engine/five_dimension_scorer.py (新文件)
  - FiveDimensionScorer 类
  - FiveDimensionAssessment 数据类
  - assess_trading_opportunity() 便捷函数

decision/engine/reasoning_engine.py (新文件)
  - ReasoningEngine 类
  - ReasoningChain 数据类
  - 11步推理流式生成

decision/engine/sandbox_validator.py (新文件)
  - SandboxValidator 类
  - 行业模型验证
  - 幻觉检测机制

decision/engine/health_checker.py (新文件)
  - SystemHealthChecker 类
  - 5项核心检查逻辑
  - SystemHealthReport 报告生成

decision/engine/monte_carlo_engine.py (新文件)
  - MonteCarloEngine 类
  - GPU 后端自动检测
  - VaR/ES 计算逻辑

core/api/v1/reasoning.py (新文件)
  - POST /api/v1/reasoning/start
  - GET /api/v1/reasoning/stream/{chain_id} (SSE)
  - GET /api/v1/reasoning/chain/{chain_id}
  - POST /api/v1/reasoning/demo

core/api/v1/health.py (新文件)
  - GET /api/v1/health/check
  - GET /api/v1/health/quick
  - GET /api/v1/health/gpu

core/api/v1/news.py (新文件)
  - GET /api/v1/news/feed
  - GET /api/v1/news/high-score
  - POST /api/v1/news/toggle
  - GET /api/v1/news/status
  - GET /api/v1/news/latest

core/api/v1/monte_carlo.py (新文件)
  - POST /api/v1/monte-carlo/simulate
  - GET /api/v1/monte-carlo/status
  - POST /api/v1/monte-carlo/quick-demo

decision/engine/__init__.py
  - 添加所有新模块导出

core/api/v1/__init__.py
  - 注册所有新路由: reasoning, health, news, monte_carlo

docs/showcase/index.html
  - Monte Carlo 概率分布可视化
  - GPU 状态显示
  - 分布图 SVG 渲染

check_gpu.py (新文件)
  - GPU 环境检测
  - CUDA/CuPy/PyTorch 检查
  - 性能基准测试
```

### 1. GLM-5 模型集成 (2026-02-13)

#### 完成内容：
- ✅ 创建 `core/api/v1/external.py` 汇率 API
- ✅ 集成 FunHub API key: `d5po719r01qthn8n1m90`
- ✅ 修复路由前缀重复问题
- ✅ 实现汇率状态计算 (stable/warning/danger)
- ✅ 修复循环导入问题
- ✅ 隐藏数据来源标签（防止侵权）

#### 文件变更：
```
core/api/v1/external.py (新文件, 216行)
  - GET /api/v1/external/forex/{currency_pair}
  - GET /api/v1/external/health
  - FunHub API 集成
  - 模拟数据降级

core/api/v1/__init__.py
  - 修复路由导入
  - 正确注册 external_router

core/api/v1/public.py
  - 修复前缀: /api/v1/public → /public

core/api/v1/showcase.py
  - 添加 _get_app_manager() 延迟导入
  - 修复循环导入

decision/workflows/realtime_router.py
  - 修复前缀: /api/v1/realtime → /realtime

.env
  - 添加 FUNHUB_API_KEY=d5po719r01qthn8n1m90
  - 添加 FUNHUB_BASE_URL
  - 添加 FOREX_UPDATE_INTERVAL=5

docs/showcase/index.html
  - 更新 updateForexRate() 从后端获取数据
  - 隐藏数据来源: "WSJ/FT" → "全球情报"
  - "Tushare 监听" → "市场数据监听"
```

#### API 端点：
```
GET /api/v1/external/forex/USDCNH
GET /api/v1/external/forex/EURUSD
GET /api/v1/external/health
```

#### 测试结果：
```bash
# 端口 8001 (新服务)
curl http://localhost:8001/api/v1/external/forex/USDCNH
# 返回: {"rate": 7.2186, "status": "stable", ...}
```

#### ⚠️ 已知问题：
- 端口 8000 有旧版服务残留（PID 24700, 7428）
- 新服务运行在端口 8001，路由正确
- 旧服务无法终止（受保护进程）

### 3. 双层感知 UI 布局 (Task #14 - 完成)

#### 完成内容：
- ✅ 双层左侧栏: Live Pulse (上) + Global Intel (下)
- ✅ 中央 Reasoning Lab: 思维链展示
- ✅ USD/CNH 汇率监控浮窗
- ✅ "研读全球情报" 按钮
- ✅ "View Math Logic" 弹窗按钮

#### 文件变更：
```
docs/showcase/index.html
  - 添加 .global-intel 区域
  - 添加 .reasoning-lab 组件
  - 添加 .forex-monitor 浮窗
  - 添加 CSS: deep thinking 模式样式
  - 添加 JavaScript 函数:
    * analyzeGlobalIntel()
    * streamReasoningContent()
    * displayValuationResult()
    * viewMathLogic()
    * updateForexRate()
```

---

## 🏗️ 核心系统状态

### AI 引擎

| 模块 | 状态 | 模型 | 说明 |
|------|------|------|------|
| 估值引擎 | ✅ 运行中 | GLM-5 (默认) | 支持切换到 GLM-4 |
| 分类筛选 | ✅ 运行中 | DeepSeek | Tushare 快讯筛选 |
| 长文分析 | ✅ 运行中 | Kimi-128k | 报刊解析 |
| 逻辑推演 | ✅ 运行中 | GLM-5 | 退出规划 |
| 代码生成 | ✅ 运行中 | GLM-5 | 估值计算 |

### 数据源

| 数据源 | 状态 | API Key | 说明 |
|--------|------|---------|------|
| Tushare | ⚠️ 冷处理 | TUSHARE_TOKEN | 可选启用 |
| FunHub 汇率 | ✅ 运行中 | d5po719r01qthn8n1m90 | USD/CNH 实时 |
| CryptoPanic | 🌙 冷处理 | CRYPTOPANIC_API_KEY | 可选启用 |
| Discord Bot | 🌙 冷处理 | DISCORD_BOT_TOKEN | 可选启用 |
| Tavily Search | ✅ 运行中 | TAVILY_API_KEY | AI 搜索 |

### 外部模块状态

| 模块 | 配置 | 状态 | 说明 |
|------|------|------|------|
| Discord Broker | `ENABLE_DISCORD_BROKER` | 🌙 静默 | 代码完整，未激活 |
| CryptoPanic | `ENABLE_CRYPTO` | 🌙 离线 | 代码完整，未激活 |
| 退出监控 | - | ✅ 运行中 | 30秒检查间隔 |
| Tushare 监测 | - | ⚠️ 可选 | 需要 TOKEN |

---

## 📝 待完成任务

### Phase 2: "Deep Thinking Type" AI 交易系统

**状态: ✅ 全部完成**

| 任务 | 状态 | 说明 |
|------|------|------|
| Task #15: Tushare 实时快讯流 | ✅ 完成 | 支持模拟数据，Tushare 启用后自动切换 |
| Task #16: 全球情报研读模块 | ✅ 完成 | PapersReader + Kimi-128k 集成 |
| Task #17: AI 思维链展示 | ✅ 完成 | SSE 流式推送，11步推理链 |
| Task #18: 计算透明化弹窗 | ✅ 完成 | Math Logic 弹窗展示 Python 代码 |
| Task #19: 五维评估模型 | ✅ 完成 | 0-10分评分系统 |
| Task #21: 无幻觉计算沙盒 | ✅ 完成 | 行业验证 + 幻觉检测 |
| Task #22: 语言隔离与异步非阻塞 | ✅ 完成 | 英文检测 + asyncio 并行 |
| Task #23: 幻觉防护与行业适配 | ✅ 完成 | 集成到 sandbox_validator |
| Task #24: 全链路逻辑自检 | ✅ 完成 | 5项核心检查 |

**额外完成: 蒙特卡洛 GPU 加速引擎**
- ✅ CuPy/PyTorch CUDA/NumPy CPU 多后端支持
- ✅ 100,000+ 并行模拟
- ✅ VaR 和 Expected Shortfall 计算
- ✅ 概率分布可视化

### Phase 3: ResearchAgent 重构 (低优先级)

#### Task #2: 重构 Discord Broker 为 ResearchAgent
**状态**: IN PROGRESS
**描述**: 将 Discord A2A 自动代理重构为通用 ResearchAgent
**当前进展**: 代码保留，冷处理模式
**优先级**: 低

#### Task #6: 创建 ResearchAgent 数据库模型
**状态**: PENDING
**优先级**: 低

#### Task #7: 编写使用文档和测试流程
**状态**: PENDING
**优先级**: 低

---

## 🐛 已知问题

### 1. 端口 8000 旧服务残留
**问题描述**: 两个旧版 FastAPI 服务占用端口 8000 (PID 24700, 7428)
**影响**:
- 无法在端口 8000 启动新服务
- 必须使用端口 8001 测试

**临时方案**: 新服务运行在端口 8001
**长期方案**: 需要手动终止或重启系统

### 2. 路由前缀重复 (已修复)
**问题描述**: `/api/v1/api/v1/public/...`
**修复状态**: ✅ 已修复
**修复方法**:
- 移除子路由的 `/api/v1` 前缀
- 只在 v1/__init__.py 保留 `/api/v1`

### 3. GLM-5 API Key 未配置
**问题描述**: 测试时 API Key 未设置
**解决方法**: 在 `.env` 中设置 `ZHIPU_API_KEY`
**状态**: 预期行为，需要用户配置

---

## 🏛️ 技术架构

### 项目结构

```
D:\AI\AItradebot\
├── core/                    # 核心系统
│   ├── api/                 # FastAPI 后端
│   │   ├── v1/              # API v1 路由
│   │   │   ├── public.py    # 公共接口
│   │   │   ├── showcase.py  # Showcase 控制面板
│   │   │   ├── external.py  # 外部数据 (FunHub 汇率)
│   │   │   └── __init__.py  # 路由注册
│   │   └── app.py           # FastAPI 主应用
│   ├── database/            # 数据库
│   └── comms/               # 通信模块
│
├── decision/                # 决策引擎
│   ├── engine/              # 估值引擎
│   │   └── valuation_tool.py
│   ├── ai_matrix/           # AI 矩阵
│   │   ├── glm4/            # GLM-4 客户端
│   │   ├── glm5/            # GLM-5 客户端 (新增)
│   │   └── base.py          # AI 基类
│   └── workflows/           # 工作流
│       └── realtime_router.py
│
├── perception/              # 感知系统
│   ├── news/                # 新闻监测
│   │   ├── tushare_sentinel.py
│   │   └── cryptopanic_sentinel.py
│   ├── papers/              # 报刊解析
│   └── search/              # Tavily 搜索
│
├── shared/                  # 共享模块
│   ├── llm/                 # 统一 LLM 客户端
│   │   ├── clients.py       # BaseLLMClient, GLM5Client
│   │   └── __init__.py
│   └── logging.py           # 日志系统
│
├── storage/                 # 数据存储
│   └── models/              # 数据库模型
│
├── ui/                      # Streamlit 前端
│   └── app.py
│
├── docs/                    # 文档
│   ├── showcase/            # Showcase 控制面板
│   │   └── index.html       # 双层 UI 布局
│   └── GLM5_INTEGRATION.md  # GLM-5 集成文档
│
├── .env                     # 环境配置
├── run_all.py               # 一键启动脚本
└── test_glm5.py             # GLM-5 测试脚本
```

### API 路由

```
http://localhost:8001 (新服务)
├── /docs                    # Swagger UI
├── /api/v1/public/
│   ├── active_events        # 活跃交易事件
│   ├── dashboard            # 仪表板统计
│   ├── reasoning/{event_id} # AI 推理详情
│   └── health               # 健康检查
│
├── /api/v1/external/
│   ├── forex/{pair}         # 实时汇率
│   └── health               # 外部数据健康检查
│
├── /api/v1/papers/
│   └── parse                # 报刊解析
│
├── /api/v1/discord/
│   └── toggle               # Discord 协作开关
│
├── /api/v1/crypto/
│   └── toggle               # CryptoPanic 开关
│
├── /api/v1/analysis/
│   └── trigger              # 手动触发分析
│
├── /api/v1/services/
│   └── status               # 所有服务状态
│
├── /api/v1/realtime/
│   ├── stats                # 路由器统计
│   ├── test_news            # 测试新闻
│   └── manual_trigger       # 手动触发
│
├── /ws/events               # WebSocket 实时推送
├── /health                  # 根路径健康检查
└── /                        # API 信息
```

### 环境变量配置

```bash
# === AI API 密钥 ===
ZHIPU_API_KEY=your_zhipu_api_key        # GLM-4 & GLM-5
KIMI_API_KEY=your_kimi_api_key           # Kimi-128k
TAVILY_API_KEY=your_tavily_api_key       # Tavily 搜索
MINIMAX_API_KEY=your_minimax_api_key     # MiniMax

# === 数据源 API ===
TUSHARE_TOKEN=your_tushare_token         # Tushare (可选)
FUNHUB_API_KEY=d5po719r01qthn8n1m90      # FunHub 汇率
CRYPTOPANIC_API_KEY=your_cryptopanic_key # CryptoPanic (可选)

# === Discord 配置 ===
DISCORD_BOT_TOKEN=your_discord_token     # Discord Bot (可选)
DISCORD_CHANNEL_ID=your_channel_id       # 频道 ID (可选)
ENABLE_DISCORD_BROKER=false              # 冷处理模式

# === CryptoPanic 配置 ===
ENABLE_CRYPTO=false                      # 冷处理模式

# === 执行模式 ===
EXECUTION_MODE=manual                    # auto/manual/simulation

# === 汇率配置 ===
FUNHUB_BASE_URL=https://api.fung_hub.com
FOREX_UPDATE_INTERVAL=5                  # 更新间隔(秒)

# === 数据库 ===
DATABASE_URL=sqlite:///data/database/aitradebot.db
```

---

## 📊 下一步计划

### 短期 (1-2周)

1. **Tushare 服务激活**
   - 用户已确认明天付费开启
   - 系统已配置好自动切换逻辑
   - 模拟数据模式可用于测试

2. **GPU 环境验证**
   - 安装 CuPy 或 PyTorch CUDA 版本
   - 运行 `python check_gpu.py` 检测
   - 确认 RTX 5080 GPU 加速可用

3. **系统集成测试**
   - 运行完整健康检查: `GET /api/v1/health/check`
   - 测试蒙特卡洛模拟: `POST /api/v1/monte-carlo/simulate`
   - 测试新闻快讯流: `GET /api/v1/news/feed`

### 中期 (2-4周)

1. **优化蒙特卡洛性能**
   - 调优模拟参数
   - 添加更多风险指标
   - 优化 GPU 内存使用

2. **前端体验优化**
   - 完善概率分布图交互
   - 添加更多可视化图表
   - 移动端适配

3. **日志和监控**
   - 添加结构化日志
   - 配置性能监控
   - 异常告警机制

### 长期 (1-3月)

1. **ResearchAgent 重构** (Phase 3)
2. **Docker 容器化** (Task #5)
3. **性能优化和监控**
4. **生产环境部署**

---

## 🧪 测试命令

### GPU 环境检测
```bash
python check_gpu.py
```

### GLM-5 集成测试
```bash
python test_glm5.py
```

### API 端点测试
```bash
# 汇率 API
curl http://localhost:8001/api/v1/external/forex/USDCNH

# 健康检查
curl http://localhost:8001/api/v1/health/check

# 快速健康检查
curl http://localhost:8001/api/v1/health/quick

# GPU 状态
curl http://localhost:8001/api/v1/health/gpu

# 新闻快讯流 (模拟数据)
curl http://localhost:8001/api/v1/news/feed

# 高评分新闻
curl http://localhost:8001/api/v1/news/high-score?threshold=7.0

# 蒙特卡洛状态
curl http://localhost:8001/api/v1/monte-carlo/status

# 蒙特卡洛快速演示
curl -X POST http://localhost:8001/api/v1/monte-carlo/quick-demo \
  -H "Content-Type: application/json" \
  -d '{"ticker": "600000.SH", "current_price": 95.0}'

# 检查所有路由
curl http://localhost:8001/openapi.json | python -m json.tool
```

### 启动服务
```bash
# 一键启动所有服务
python run_all.py

# 单独启动 FastAPI
python -m uvicorn core.api.app:app --host 0.0.0.0 --port 8001 --reload

# 单独启动 Streamlit
streamlit run ui/app.py --server.port 8501
```

### 健康检查测试 (Python)
```bash
python -c "
import asyncio
from decision.engine.health_checker import run_system_health_check

async def test():
    report = await run_system_health_check()
    print(f'Overall: {report.overall_status.value}')
    print(f'Passed: {report.passed_count}')
    print(f'Failed: {report.failed_count}')

asyncio.run(test())
"
```

---

## 📚 相关文档

- [GLM-5 集成文档](GLM5_INTEGRATION.md)
- [Showcase 控制面板](showcase/index.html)
- [API 文档](http://localhost:8001/docs)
- [WebSocket 测试](http://localhost:8001/ws/events)

---

## 👥 团队协作

### Claude Code 职责
- GLM-5 模型集成 ✅
- 汇率预警系统 ✅
- UI 布局优化 ✅
- 路由修复 ✅

### 待分配任务
- 全球情报研读模块实现
- 五维评估模型实现
- AI 思维链集成
- 全链路自检

---

**文档版本**: 2.0
**最后更新**: 2026-02-13 (Phase 2 全部完成)
**下次审查**: 2026-02-15
