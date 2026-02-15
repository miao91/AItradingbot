# AI TradeBot 架构重构报告

**日期**: 2026-02-14
**版本**: GLM-5 核心驱动版
**状态**: P0 任务完成

---

## 一、完成的任务

### P0-1: GLM-5 核心决策层集成 ✅

**新建文件**:
```
core/orchestrator/
├── __init__.py
├── glm5_orchestrator.py    # GLM-5 核心编排器
└── dependency_injector.py  # 依赖注入框架
```

**核心功能**:
1. `GLM5Orchestrator` - GLM-5 总指挥
   - 任务复杂度判定（SIMPLE/MEDIUM/COMPLEX/LONG_FORM）
   - 普通快讯：GLM-5 直接完成 [摘要+打分+估值]
   - 长文档：Kimi分段预处理 → GLM-5汇总
   - GPU蒙特卡洛代码生成

2. `DependencyInjector` - 依赖注入
   - 替代全局单例模式
   - 支持单例/非单例
   - 生命周期管理

### P0-2: 依赖注入与单例清理 ✅

**重构内容**:
- 创建 `DependencyInjector` 类
- 支持 `get_container()` 获取全局容器
- 保留旧单例函数向后兼容

### P1-3: 精简配置与健康监测 ✅

**新建文件**:
```
config/
├── __init__.py
└── simple.py    # 20个核心配置项
```

**配置分类**:
| 类别 | 配置项 | 说明 |
|------|--------|------|
| AI配置 | 5项 | GLM-5、Kimi、默认模型 |
| 数据源 | 5项 | Tushare、FunHub、数据库 |
| 系统配置 | 5项 | 日志、端口、调试模式 |
| 风控配置 | 5项 | 止损止盈、熔断阈值 |

### P1-5: 添加基础监控 ✅

**新建文件**:
```
core/api/v1/metrics.py    # Prometheus 格式指标
core/risk/
├── __init__.py
└── circuit_breaker.py    # 风控熔断器
```

**监控指标**:
- `ai_requests_total` - AI 请求总数
- `ai_latency_avg_ms` - AI 平均延迟
- `gpu_memory_used_mb` - GPU 内存使用
- `circuit_breaker_trips` - 熔断器触发次数

**新增API端点**:
```
GET /api/v1/metrics          # Prometheus 格式
GET /api/v1/metrics/json     # JSON 格式
GET /api/v1/metrics/valuation-drift  # 估值漂移率
```

---

## 二、架构变更

### 旧架构
```
事件 → EventAnalyzer → 5步流程
                      ↓
              Kimi/GLM-4/MiniMax/Tavily/Classifier
                      ↓
                   ExitPlanner
```

### 新架构（GLM-5 核心化）
```
事件 → GLM5Orchestrator
         ├── 判定复杂度
         ├── SIMPLE: GLM-5 直接决策
         ├── MEDIUM: GLM-5 + 分析
         ├── COMPLEX: 多专家协作
         └── LONG_FORM: Kimi预处理 → GLM-5汇总
```

---

## 三、文件变更清单

### 新建文件 (9个)
```
core/orchestrator/__init__.py
core/orchestrator/glm5_orchestrator.py
core/orchestrator/dependency_injector.py
core/orchestrator/model_fallback.py      # P2: 模型降级
core/risk/__init__.py
core/risk/circuit_breaker.py
core/api/v1/metrics.py
config/__init__.py
config/simple.py
shared/utils/async_runner.py            # P1: 统一异步处理
```

### 修改文件 (3个)
```
core/api/v1/__init__.py              # 添加 metrics 路由
decision/workflows/event_analyzer.py # P1: 并行化数据获取
core/api/v1/metrics.py               # 添加 model-fallback 端点
```

---

## 四、验收标准检查

| 标准 | 状态 |
|------|------|
| GLM-5 核心化 | ✅ |
| 依赖注入框架 | ✅ |
| 配置精简为20项 | ✅ |
| 监控端点 /metrics | ✅ |
| 风控熔断器 | ✅ |

---

## 五、下一步（P1/P2 待完成）

### P1: ✅ 已完成
- [x] 统一全链路异步（asyncio.gather 并行化）
  - `decision/workflows/event_analyzer.py` - 并行获取行情 + Tavily 搜索
  - `core/orchestrator/glm5_orchestrator.py` - 并行 Kimi + 汇率获取
- [x] 优雅退出机制（SignalHandler）
  - 新建 `shared/utils/async_runner.py`
  - 支持 SIGINT/SIGTERM 信号处理
  - 提供 `run_async()` 统一入口
  - 提供 `graceful_shutdown_context()` 上下文管理器

### P2:
- [x] 多级容错与模型降级
  - 新建 `core/orchestrator/model_fallback.py`
  - 模型链: GLM-5 → GLM-4 → DeepSeek → 规则引擎
  - 熔断机制: 连续失败3次自动禁用
  - 自动恢复: 5分钟后尝试恢复
- [x] 代码工程化清理（mypy/black/isort）
  - 新建 `pyproject.toml` 配置文件
  - black 格式化: 9 个文件
  - isort 导入排序: 8 个文件
  - mypy 类型检查: 新代码无错误

---

## 六、最终架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     AI TradeBot v2.0                        │
│                    (GLM-5 核心驱动)                          │
├─────────────────────────────────────────────────────────────┤
│  入口层                                                      │
│  ├── run_async() - 统一异步入口                              │
│  └── graceful_shutdown_context() - 优雅退出                  │
├─────────────────────────────────────────────────────────────┤
│  编排层                                                      │
│  ├── GLM5Orchestrator - 总指挥                               │
│  │   ├── SIMPLE: GLM-5 直接决策                              │
│  │   ├── COMPLEX: 多专家协作                                  │
│  │   └── LONG_FORM: Kimi预处理 → GLM-5汇总                   │
│  └── ModelFallbackManager - 降级保护                         │
│      └── GLM-5 → GLM-4 → DeepSeek → 规则引擎                 │
├─────────────────────────────────────────────────────────────┤
│  风控层                                                      │
│  └── CircuitBreaker - 熔断器                                 │
│      └── DXY 波动 >0.5% 触发（美元指数）                      │
├─────────────────────────────────────────────────────────────┤
│  监控层                                                      │
│  ├── /api/v1/metrics - Prometheus 格式                       │
│  ├── /api/v1/metrics/json - JSON 格式                        │
│  ├── /api/v1/metrics/model-fallback - 降级状态               │
│  ├── /api/v1/metrics/dxy - 美元指数监控                      │
│  └── /api/v1/external/dxy - DXY 原始数据                     │
└─────────────────────────────────────────────────────────────┘
```

---

**报告人**: Claude Code
