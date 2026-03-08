# AI TradeBot - 事件驱动智能化量化交易系统

> "Begin with the End in Mind" - 从买入那一刻起，AI已预设明确的逻辑终点

## 项目简介

AI TradeBot 是一个基于**事件驱动**的智能化量化交易系统，核心哲学是"以终为始"。系统通过多源数据感知、AI决策引擎、严格风控体系实现自动化交易决策。

## 核心特性

- 🤖 **多模型AI决策矩阵** - Kimi长文处理、GLM-4逻辑博弈、MiniMax指令生成、Tavily信息聚合
- 📰 **实时新闻聚合** - Tushare Pro API 获取实时金融新闻，智能去重
- 🎯 **以终为始决策** - 每次交易预设止盈、止损、失效时间
- 🛡️ **多层风控体系** - 仓位控制、资金管理、熔断机制
- 💻 **赛博朋克风格UI** - 现代化Web界面，实时数据可视化

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (React + TypeScript + Vite)         │
│                   赛博朋克风格UI / WebSocket实时推送          │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                    后端 (FastAPI + Python)                   │
│              REST API / WebSocket / Tushare数据              │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│              AI决策引擎 (Multi-Agent Orchestrator)           │
│   信号生成 → 逻辑推演 → 退出规划 → 完整决策包                  │
└─────────────────────────────────────────────────────────────┘
```

## 快速启动

### 方式一：一键启动（推荐）

双击运行项目根目录下的 `启动AITradeBot.bat` 即可自动启动前后端服务。

### 方式二：手动启动

```bash
# 1. 启动后端 (端口 8000)
cd backend
uvicorn main:app --reload --port 8000

# 2. 启动前端 (端口 5173)
cd frontend
npm run dev
```

### 环境配置

在项目根目录创建 `.env` 文件：

```env
# Tushare Pro API Token
TUSHARE_TOKEN=your_token_here

# 大模型API配置
KIMI_API_KEY=your_kimi_key
GLM_API_KEY=your_glm_key
MINIMAX_API_KEY=your_minimax_key
TAVILY_API_KEY=your_tavily_key
```

## 功能模块

| 模块 | 说明 |
|------|------|
| **新闻资讯** | Tushare Pro 实时新闻，智能去重算法 |
| **决策链** | AI多模型协同推理，完整决策流程可视化 |
| **行业分析** | 行业热点追踪，板块轮动分析 |
| **标的池** | AI精选候选股票池 |
| **技术分析** | 实时行情与技术指标 |
| **金融工程** | 期权/可转债等金融衍生品分析 |

## 项目结构

```
AItradebot/
├── backend/              # FastAPI 后端
│   ├── main.py          # 主应用入口
│   └── requirements.txt # Python依赖
├── frontend/             # React 前端
│   ├── src/
│   │   ├── components/ # UI组件
│   │   ├── services/   # API服务
│   │   └── types/      # TypeScript类型
│   └── package.json
├── perception/          # 数据感知层
│   ├── data_sources/   # Tushare/AkShare数据源
│   └── fusion/         # 数据融合与去重
├── decision/           # AI决策引擎
│   ├── engine/         # 决策核心逻辑
│   └── generator/     # 策略生成器
├── core/               # 核心API
├── shared/             # 共享模块
├── docs/               # 文档
└── 启动AITradeBot.bat # 一键启动脚本
```

## 依赖要求

- **Python**: 3.10+
- **Node.js**: 18+
- **Tushare Pro Token**: 用于获取实时新闻与行情数据

## License

MIT License
