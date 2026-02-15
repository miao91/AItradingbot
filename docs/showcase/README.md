# AI TradeBot - 项目展示页面

> 事件驱动智能化交易系统

## 项目简介

AI TradeBot 是一个基于**事件驱动**的智能化交易系统，核心哲学是"以终为始"。系统不仅负责发现市场机会，更关键的是在每一次交易决策的初始，就由 AI 推演并预设清晰的退出策略。

## 核心特性

- **以终为始决策** - 每一笔交易在买入时就预设完整的退出策略
- **AI Matrix 协同** - Kimi、GLM-4、MiniMax、Tavily 多模型协同工作
- **事件驱动感知** - OpenClaw爬虫 + Tavily搜索实时捕捉市场机会
- **硬编码风控锁** - 仓位控制、资金管理、熔断机制
- **QMT执行对接** - 支持实盘与模拟交易
- **完整决策溯源** - 所有AI推理链路可追溯

## 访问完整项目

完整项目代码请访问：[https://github.com/miao91/aitradebot](https://github.com/miao91/aitradebot)

## 技术栈

- Python 3.10+
- FastAPI
- SQLAlchemy
- Streamlit
- QMT/xtquant
- Kimi API, GLM-4 API, MiniMax API, Tavily API

---

**"Begin with the End in Mind" - 每一笔交易，都有清晰的终点。**
