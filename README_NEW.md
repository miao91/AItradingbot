# AI TradeBot 重构项目 - 动态决策链条

## 项目结构

```
AItradebot/
├── frontend/              # React + TypeScript + Tailwind 前端
│   ├── src/
│   │   ├── components/    # UI组件
│   │   │   ├── Header.tsx
│   │   │   ├── DecisionChain.tsx    # 决策链条导航
│   │   │   ├── NewsTicker.tsx       # 滚动新闻流
│   │   │   ├── IndustryAnalysis.tsx # AI行业分析
│   │   │   ├── AssetList.tsx        # 核心资产列表
│   │   │   ├── TechAnalysis.tsx     # 技术分析(MACD/均线)
│   │   │   ├── TVChart.tsx          # TradingView图表
│   │   │   └── FinEngineering.tsx   # 金融工程分析
│   │   ├── services/
│   │   │   └── api.ts               # API服务
│   │   ├── types/
│   │   │   └── index.ts             # TypeScript类型
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   └── postcss.config.js
│
├── backend/               # FastAPI 后端
│   ├── main.py            # API主文件
│   └── requirements.txt
│
└── legacy/                # 原项目备份
```

## 决策流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [新闻流] → [行业分析] → [核心资产] → [技术分析] → [TradingView] → [金融工程]  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1. 新闻流 (NewsTicker)
- 实时展示 Tushare 财经新闻
- 点击新闻触发后续分析
- 显示时间、来源、分类、相关股票

### 2. 行业分析 (IndustryAnalysis)
- AI 分析新闻对行业的影响
- 给出乐观/中性/悲观预测
- 显示置信度和核心观点
- 详细分析可展开查看

### 3. 核心资产 (AssetList)
- 列出该行业的核心股票
- 显示权重、价格、涨跌幅
- 点击股票进入技术分析

### 4. 技术分析 (TechAnalysis)
- MACD 信号：金叉/死叉/背离
- 均线系统：多头排列/空头排列
- 综合评分：买入/持有/卖出

### 5. TradingView 图表
- 实时 K 线图表
- 内置 MA 和 MACD 指标
- 支持全屏查看

### 6. 金融工程分析 (FinEngineering)
- VaR 风险值 (95%/99%)
- 夏普比率
- 蒙特卡洛模拟分布图
- 详细分析可展开

## 启动方式

### 1. 启动后端 API
```bash
cd backend
pip install -r requirements.txt
python main.py
```
后端运行在 http://localhost:8000

### 2. 启动前端
```bash
cd frontend
npm install
npm run dev
```
前端运行在 http://localhost:5173

### 3. 访问应用
打开浏览器访问 http://localhost:5173

## UI设计理念

### 交易员视角
- **结果优先**：核心结论放在最显眼位置
- **流程清晰**：决策链条导航直观展示当前步骤
- **信息分层**：复杂计算隐藏在展开区域
- **专业配色**：暗色主题，红绿涨跌标识

### 颜色方案
- 背景：#0a0a0a (主) / #141414 (卡片)
- 看涨：#00e676 (绿色)
- 看跌：#ff5252 (红色)
- 中性：#448aff (蓝色)
- 强调：#9b59b6 (紫色)

## 后续开发建议

### 1. 接入 Tushare API
- 在 backend/main.py 中接入真实的 Tushare 新闻 API
- 实现实时新闻推送 (WebSocket)

### 2. AI 分析增强
- 接入 Kimi/GLM 等大模型进行行业分析
- 实现更智能的情绪判断

### 3. 数据持久化
- 添加数据库存储 (SQLite/PostgreSQL)
- 记录用户操作历史

### 4. 用户系统
- 添加登录/注册
- 个人收藏和设置

### 5. 实盘交易
- 接入 QMT 等量化交易接口
- 实现自动化下单

## 文件清单

已创建的文件：
- ✅ frontend/src/components/Header.tsx
- ✅ frontend/src/components/DecisionChain.tsx
- ✅ frontend/src/components/NewsTicker.tsx
- ✅ frontend/src/components/IndustryAnalysis.tsx
- ✅ frontend/src/components/AssetList.tsx
- ✅ frontend/src/components/TechAnalysis.tsx
- ✅ frontend/src/components/TVChart.tsx
- ✅ frontend/src/components/FinEngineering.tsx
- ✅ frontend/src/services/api.ts
- ✅ frontend/src/types/index.ts
- ✅ frontend/src/App.tsx
- ✅ frontend/src/main.tsx
- ✅ frontend/src/index.css
- ✅ frontend/tailwind.config.js
- ✅ frontend/postcss.config.js
- ✅ backend/main.py
- ✅ backend/requirements.txt
- ✅ REBUILD_PLAN.md
- ✅ README_NEW.md (本文件)
