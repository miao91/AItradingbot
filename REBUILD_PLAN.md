# AI TradeBot 重构计划 - 动态决策链条网页应用

## 项目目标
创建一个专业的交易员视角的动态决策链条系统，流程：
**新闻流 → AI行业分析 → 核心资产 → 技术分析 → TradingView图表 → 金融工程分析**

## 新架构设计

### 目录结构
```
AItradebot/
├── frontend/                    # 新前端 (React + Vite + Tailwind)
│   ├── src/
│   │   ├── components/         # UI组件
│   │   │   ├── NewsTicker.tsx      # 滚动新闻流
│   │   │   ├── IndustryAnalysis.tsx # 行业AI分析
│   │   │   ├── AssetList.tsx       # 核心资产列表
│   │   │   ├── TechAnalysis.tsx    # 技术分析(MACD/均线)
│   │   │   ├── TVChart.tsx         # TradingView图表
│   │   │   ├── FinEngineering.tsx  # 金融工程分析
│   │   │   └── DecisionChain.tsx   # 决策链条可视化
│   │   ├── pages/
│   │   │   └── Dashboard.tsx       # 主仪表盘
│   │   ├── hooks/              # 自定义Hooks
│   │   ├── services/           # API服务
│   │   ├── types/              # TypeScript类型
│   │   └── App.tsx
│   ├── index.html
│   ├── package.json
│   └── tailwind.config.js
│
├── backend/                     # 后端API (FastAPI)
│   ├── app/
│   │   ├── api/
│   │   │   ├── news.py         # 新闻API (Tushare)
│   │   │   ├── analysis.py     # AI分析API
│   │   │   ├── assets.py       # 核心资产API
│   │   │   ├── technical.py    # 技术分析API
│   │   │   └── financial.py    # 金融工程API
│   │   ├── services/
│   │   │   ├── tushare_service.py    # Tushare接口
│   │   │   ├── ai_analysis.py        # AI行业分析
│   │   │   ├── tech_indicators.py    # 技术指标计算
│   │   │   └── asset_repository.py   # 核心资产库
│   │   ├── models/
│   │   └── main.py
│   └── requirements.txt
│
└── legacy/                      # 保留原有代码
    └── (原项目备份)
```

## UI设计原则（交易员视角）

### 1. 信息层级
```
┌─────────────────────────────────────────────────────────────┐
│  决策链条 (顶部导航条)                                       │
│  [新闻流] → [行业分析] → [核心资产] → [技术分析] → [下单]     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │                      │  │                              │ │
│  │   滚动新闻流          │  │   动态内容区域                │ │
│  │   (左侧 30%)         │  │   (右侧 70%)                 │ │
│  │                      │  │                              │ │
│  │   • 央行降准          │  │   点击新闻后显示:             │ │
│  │   • 宁德时代          │  │   • AI行业情绪(乐观/中性/悲观)│ │
│  │   • 贵州茅台          │  │   • 核心资产列表              │ │
│  │   • ...              │  │   • TradingView图表           │ │
│  │                      │  │   • 技术信号                  │ │
│  └──────────────────────┘  │   • 金融工程分析              │ │
│                            │                              │ │
│                            └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2. 颜色方案（专业交易风格）
```css
/* 暗色专业主题 */
--bg-primary: #0a0a0a;        /* 主背景 */
--bg-card: #141414;           /* 卡片背景 */
--border: #2a2a2a;            /* 边框 */
--text-primary: #e0e0e0;      /* 主文字 */
--text-secondary: #888888;    /* 次要文字 */

/* 状态颜色 */
--bullish: #00e676;           /* 看涨/乐观 */
--bearish: #ff5252;           /* 看跌/悲观 */
--neutral: #448aff;           /* 中性 */
--warning: #ffd740;           /* 警告/观察 */
--accent: #9b59b6;            /* 强调色 */
```

### 3. 组件设计

#### NewsTicker 滚动新闻
- 实时滚动展示Tushare新闻
- 每条新闻显示：时间、标题、相关股票标签
- 点击新闻后高亮显示，触发右侧分析

#### IndustryAnalysis 行业分析
- AI分析结果显示区域
- 情绪指标：乐观(绿)/中性(蓝)/悲观(红)
- 置信度百分比
- 核心论点摘要（一句话）
- 详细分析可展开

#### AssetList 核心资产
- 表格展示该行业核心股票
- 显示：代码、名称、最新价、涨跌幅、操作建议
- 点击股票跳转到技术分析

#### TechAnalysis 技术分析
- 简洁信号展示
- MACD：金叉/死叉/背离
- 均线：多头排列/空头排列/整理
- 综合评分：买入/持有/卖出

#### TVChart TradingView图表
- 集成TradingView Widget
- 支持切换周期(日/周/小时)
- 显示MA和MACD指标

#### FinEngineering 金融工程
- 蒙特卡洛模拟结果
- VaR风险值
- 夏普比率
- 展开显示详细分布图

## API接口设计

### 1. 新闻流
```
GET /api/news/stream
Response: {
  "news": [
    {
      "id": "string",
      "time": "2024-02-26 14:30:00",
      "title": "央行宣布降准0.5个百分点",
      "source": "央行官网",
      "related_tickers": ["银行板块"],
      "category": "宏观经济"
    }
  ]
}
```

### 2. AI行业分析
```
POST /api/analysis/industry
Body: { "news_id": "string", "news_title": "string" }
Response: {
  "industry": "银行",
  "sentiment": "optimistic",  // optimistic | neutral | pessimistic
  "confidence": 0.85,
  "summary": "降准释放流动性，利好银行业",
  "detailed_analysis": "...",
  "key_points": ["流动性改善", "息差压力缓解"]
}
```

### 3. 核心资产
```
GET /api/assets/industry/{industry}
Response: {
  "industry": "银行",
  "assets": [
    {
      "ticker": "600036.SH",
      "name": "招商银行",
      "type": "核心资产",
      "weight": "高"
    }
  ]
}
```

### 4. 技术分析
```
GET /api/technical/{ticker}
Response: {
  "ticker": "600036.SH",
  "signals": {
    "macd": { "signal": "golden_cross", "strength": 0.8 },
    "ma": { "trend": "bullish", "alignment": "多头排列" },
    "overall": "BUY"
  },
  "indicators": {
    "ma5": 35.2,
    "ma10": 34.8,
    "ma20": 34.5,
    "macd": { "dif": 0.5, "dea": 0.3, "histogram": 0.2 }
  }
}
```

### 5. 金融工程分析
```
GET /api/financial/monte-carlo/{ticker}
Response: {
  "ticker": "600036.SH",
  "var_95": 0.025,
  "var_99": 0.045,
  "sharpe_ratio": 1.42,
  "distribution": [...]
}
```

## 执行计划

### Phase 1: 项目初始化 (30分钟)
1. 创建新的目录结构
2. 初始化前端项目 (Vite + React + TypeScript)
3. 配置Tailwind CSS
4. 初始化后端项目结构

### Phase 2: 前端基础 (60分钟)
1. 创建基础布局组件
2. 实现决策链条导航
3. 创建新闻流组件
4. 集成TradingView Widget

### Phase 3: 后端API (60分钟)
1. 实现Tushare新闻接口
2. 实现AI行业分析接口
3. 实现核心资产接口
4. 实现技术分析接口
5. 迁移金融工程分析

### Phase 4: 功能整合 (60分钟)
1. 连接前后端API
2. 实现决策链条流程
3. 添加加载状态和错误处理
4. 优化UI交互

### Phase 5: 测试优化 (30分钟)
1. 测试完整流程
2. 优化性能
3. 完善文档

总计约4小时

## 依赖清单

### 前端
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0",
    "recharts": "^2.10.0",
    "lucide-react": "^0.294.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }
}
```

### 后端
```
fastapi==0.104.0
uvicorn==0.24.0
websockets==12.0
tushare==1.3.0
pandas==2.1.0
numpy==1.26.0
httpx==0.25.0
python-dotenv==1.0.0
```

## 下一步行动

1. 备份现有项目到 legacy/ 目录
2. 创建新的 frontend/ 和 backend/ 目录
3. 开始 Phase 1: 项目初始化
