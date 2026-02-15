# AI TradeBot - 架构设计文档

## 目录

1. [设计原则](#设计原则)
2. [系统分层](#系统分层)
3. [核心模块](#核心模块)
4. [数据流](#数据流)
5. [安全设计](#安全设计)
6. [扩展性设计](#扩展性设计)

---

## 设计原则

### 1. 模块化 (Modular)

各层职责清晰，接口明确：

- **感知层**: 只负责数据采集，不做决策
- **决策层**: 只负责逻辑推演，不直接下单
- **执行层**: 只负责订单执行，不判断逻辑
- **存储层**: 数据持久化，提供统一访问接口

### 2. 安全性 (Safety)

**风控硬锁原则**: 风控参数硬编码在代码中，不通过配置文件修改

```python
# core/security.py
class SafetyLock:
    MAX_SINGLE_POSITION_RATIO = 0.10  # 硬编码，不可配置
    MAX_DAILY_LOSS_RATIO = 0.03
    # ...
```

### 3. 透明性 (Traceability)

所有 AI 决策过程必须完整记录：

- 输入
- 提示词
- 输出
- 推理链路

---

## 系统分层

```
┌─────────────────────────────────────────────────────────┐
│                       UI Layer                          │
│                   (Streamlit Dashboard)                  │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP/WebSocket
┌───────────────────────────▼─────────────────────────────┐
│                      Core Layer                         │
│                  (FastAPI Backend)                       │
├─────────────────────────────────────────────────────────┤
│  Config  │  Security  │  Services  │  API Routes        │
└───────────────────────────┬─────────────────────────────┘
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
┌──────▼──────┐    ┌────────▼────────┐   ┌─────▼──────┐
│ Perception  │    │    Decision     │   │ Execution  │
│    Layer    │◄──►│     Layer       │◄──►│   Layer    │
├─────────────┤    ├─────────────────┤   ├────────────┤
│ OpenClaw    │    │  AI Matrix      │   │  QMT Gateway│
│ Tavily      │    │  Decision Engine│   │ Order Router│
│ Tushare     │    │  Workflows      │   │ Position Mgr│
│ AkShare     │    │                 │   │            │
└──────┬──────┘    └────────┬────────┘   └─────┬──────┘
       │                    │                  │
       └────────────────────┼──────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│                    Storage Layer                        │
│              (SQLite + SQLAlchemy ORM)                   │
└─────────────────────────────────────────────────────────┘
```

---

## 核心模块

### 1. 感知层 (Perception Layer)

**职责**: 从各种数据源采集信息

| 模块 | 数据源 | 更新频率 | 数据类型 |
|------|--------|----------|----------|
| OpenClaw | 目标网站爬取 | 实时/定时 | 非结构化文本 |
| Tavily | 实时新闻搜索 | 实时 | 结构化新闻 |
| Tushare | 历史数据/基本面 | 每日 | 时间序列/财务 |
| AkShare | 实时行情 | 实时 | Tick/分时 |

**事件总线模式**:

```python
# shared/event_bus.py
class EventBus:
    async def publish(self, event_type: str, data: dict):
        """发布事件"""
        pass

    async def subscribe(self, event_type: str, handler):
        """订阅事件"""
        pass
```

### 2. 决策层 (Decision Layer)

**职责**: 协调 AI Matrix，生成交易决策

#### AI Matrix 协同流程

```
Event → [Kimi: 长文清洗] → [Tavily: 背景搜索] → [GLM-4: 逻辑推演]
     ↓
[MiniMax: 结构化输出] → Decision Bundle → Risk Check → Execution
```

#### 决策引擎 (Decision Engine)

```python
# decision/engine/engine.py
class DecisionEngine:
    async def make_decision(self, event: Event) -> DecisionBundle:
        # 1. 信号生成
        signal = await self.signal_generator.generate(event)

        # 2. 逻辑推演
        reasoning = await self.reasoner.reason(signal)

        # 3. 退出规划 (核心)
        exit_plan = await self.exit_planner.plan(reasoning)

        # 4. 打包决策
        return DecisionBundle(
            signal=signal,
            reasoning=reasoning,
            exit_plan=exit_plan
        )
```

### 3. 执行层 (Execution Layer)

**职责**: 将决策转化为实际交易

#### QMT 网关

```python
# execution/qmt/gateway.py
class QMTGateway:
    async def connect(self):
        """连接 QMT"""
        pass

    async def place_order(self, order: Order) -> OrderResult:
        """下单"""
        pass

    async def get_position(self, symbol: str) -> Position:
        """查询持仓"""
        pass
```

### 4. 存储层 (Storage Layer)

**ORM 模型设计**

```python
# storage/models/decision.py
class Decision(Base):
    __tablename__ = "decisions"

    id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey("events.id"))
    action = Column(Enum(DecisionAction))
    exit_plan = Column(JSON)  # 存储 JSON 格式的退出计划
    reasoning_chain = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## 数据流

### 完整决策链路

```
[外部事件]
    │
    ▼
┌─────────────────────────────────────────────────┐
│ 1. 感知层捕获事件                                │
│    - OpenClaw 爬取公告                           │
│    - Tavily 搜索相关新闻                         │
│    - 标准化为 Event 对象                         │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 2. 事件总线分发                                  │
│    - WebSocket 推送给决策层                      │
│    - 同时存入数据库                              │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 3. AI Matrix 协同决策                            │
│    ├─ Kimi: 长文清洗                            │
│    ├─ Tavily: 背景搜索                          │
│    ├─ GLM-4: 逻辑推演                           │
│    └─ MiniMax: 结构化输出                       │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 4. 决策引擎生成 Decision Bundle                  │
│    {                                            │
│      "action": "BUY",                           │
│      "exit_plan": {         ← 核心差异点        │
│        "take_profit": {...},                    │
│        "stop_loss": {...},                      │
│        "expiration": {...}                      │
│      }                                          │
│    }                                            │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 5. 风控硬锁检查                                  │
│    - 仓位上限检查                                │
│    - 资金约束检查                                │
│    - 频率限制检查                                │
└─────────────────┬───────────────────────────────┘
                  │ 通过
                  ▼
┌─────────────────────────────────────────────────┐
│ 6. 执行层下单                                    │
│    - QMT Gateway                                │
│    - 订单路由                                    │
│    - 持仓建立                                    │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│ 7. 持仓持续监控                                  │
│    - 实时行情监控                                │
│    - 触发退出条件时自动执行                      │
│    - 记录到交易日志                              │
└─────────────────────────────────────────────────┘
```

---

## 安全设计

### 风控硬锁位置

```
Decision Bundle
    │
    ▼
┌─────────────────────────────────────┐
│ Risk Control Safety Locks           │
│ (core/security.py)                  │
├─────────────────────────────────────┤
│ ┌─────────────────────────────────┐ │
│ │ 1. 仓位锁                       │ │
│ │    MAX_SINGLE_POSITION_RATIO    │ │
│ │    = 0.10 (硬编码)              │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ 2. 资金锁                       │ │
│ │    MAX_DAILY_LOSS_RATIO         │ │
│ │    = 0.03 (硬编码)              │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ 3. 频率锁                       │ │
│ │    MAX_TRADES_PER_DAY           │ │
│ │    = 10 (硬编码)                │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
    │
    │ 全部通过
    ▼
Execution
```

### 熔断机制

```python
# core/services/risk_service.py
class RiskService:
    async def check_circuit_breaker(self) -> bool:
        """检查熔断状态"""
        today_pnl = await self.get_today_pnl_ratio()
        if today_pnl < -MAX_DAILY_LOSS_RATIO:
            await self.trigger_circuit_break()
            return False
        return True
```

---

## 扩展性设计

### 添加新 AI 模型

```python
# 1. 在 decision/ai_matrix/ 下新建目录
decision/ai_matrix/new_ai/
    ├── __init__.py
    ├── client.py      # 继承 AIBase
    └── prompts.py     # 提示词模板

# 2. 在决策引擎中注册
# decision/engine/engine.py
self.ai_models["new_ai"] = NewAIClient()
```

### 添加新数据源

```python
# 1. 在 perception/ 下新建目录
perception/new_source/
    ├── __init__.py
    └── client.py

# 2. 实现统一接口
class NewSourceClient(DataSourceBase):
    async def fetch_data(self, params) -> Event:
        pass
```

---

## 数据库 Schema

详见 `storage/models/` 目录

- `event.py`: 事件表
- `decision.py`: 决策表
- `position.py`: 持仓表
- `trade_log.py`: 交易日志表
- `ai_reasoning.py`: AI 推理日志表
