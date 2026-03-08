from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Literal
import uvicorn
import os
import tushare as ts
from datetime import datetime
import re
import json
from pathlib import Path

# 加载.env文件
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

app = FastAPI(
    title="AI TradeBot API",
    description="动态决策链条系统后端API",
    version="2.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tushare配置
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
if TUSHARE_TOKEN:
    ts.set_token(TUSHARE_TOKEN)

# 数据模型
class NewsItem(BaseModel):
    id: str
    time: str
    title: str
    source: str
    category: Optional[str] = None
    industry: Optional[str] = None
    relatedTickers: Optional[List[str]] = None

class AnalysisRequest(BaseModel):
    news_id: str
    news_title: str

class AnalysisResult(BaseModel):
    industry: str
    sentiment: Literal["optimistic", "neutral", "pessimistic"]
    confidence: float
    summary: str
    detailedAnalysis: Optional[str] = None
    keyPoints: List[str]

class Asset(BaseModel):
    ticker: str
    name: str
    type: str
    weight: str
    price: Optional[float] = None
    change: Optional[float] = None
    changePct: Optional[float] = None

class MacdSignal(BaseModel):
    signal: Literal["golden_cross", "death_cross", "divergence", "neutral"]
    strength: float

class MaSignal(BaseModel):
    trend: Literal["bullish", "bearish", "neutral"]
    alignment: str

class TechSignals(BaseModel):
    macd: MacdSignal
    ma: MaSignal
    overall: Literal["BUY", "SELL", "HOLD", "STRONG_BUY", "STRONG_SELL"]
    indicators: Optional[dict] = None

class MonteCarloResult(BaseModel):
    var95: float
    var99: float
    sharpeRatio: float
    maxDrawdown: float
    winRate: float
    distribution: List[float]

# 行业关键词映射
INDUSTRY_KEYWORDS = {
    "银行": ["银行", "银保监会", "央行", "降准", "降息", "贷款", "存款", "利率"],
    "新能源": ["新能源", "锂电池", "光伏", "风电", "宁德时代", "比亚迪", "特斯拉", "电动车", "电池"],
    "白酒": ["白酒", "茅台", "五粮液", "泸州老窖", "酒", "酿酒"],
    "半导体": ["半导体", "芯片", "中芯国际", "光刻机", "集成电路", "晶圆"],
    "房地产": ["房地产", "房价", "地产", "万科", "碧桂园", "恒大", "房贷"],
    "券商": ["券商", "证券", "东方财富", "中信证券", "华泰", "开户"],
    "汽车": ["汽车", "整车", "比亚迪", "吉利", "长城", "上汽"],
    "医药": ["医药", "医疗", "中药", "创新药", "恒瑞", "医保"],
    "保险": ["保险", "平安", "中国人寿", "保单", "险资"],
    "钢铁": ["钢铁", "螺纹钢", "铁矿石", "宝钢", "鞍钢"],
    "煤炭": ["煤炭", "煤", "神华", "兖州煤业", "动力煤"],
    "军工": ["军工", "航天", "航空", "船舶", "导弹", "国防"],
}

# 新闻分类关键词
CATEGORY_KEYWORDS = {
    "宏观政策": ["政策", "央行", "证监会", "银保监会", "国务院", "降准", "降息", "财政", "货币"],
    "公司新闻": ["公告", "公司", "上市", "收购", "重组", "定增", "回购"],
    "业绩快报": ["财报", "业绩", "净利润", "营收", "利润", "预告", "季报", "年报"],
    "板块异动": ["涨停", "跌停", "异动", "拉升", "暴跌", "板块", "领涨", "领跌"],
    "行业新闻": ["行业", "产能", "供需", "景气", "转型", "补贴"],
    "市场行情": ["指数", "大盘", "沪指", "深指", "创业板", "科创板", "北交所", "成交量"],
}

def extract_industry(title: str, content: str = "") -> Optional[str]:
    """从标题和内容中提取行业"""
    text = title + " " + (content or "")
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return industry
    return None

def extract_category(title: str, content: str = "") -> Optional[str]:
    """从标题和内容中提取新闻分类"""
    text = title + " " + (content or "")
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return category
    return "市场行情"  # 默认分类

def extract_tickers(title: str) -> List[str]:
    """从标题中提取股票代码"""
    tickers = []
    # 匹配6位数字代码 (如 600036.SH, 000001.SZ, 300750.SZ)
    patterns = [
        r'(\d{6}\.(?:SH|SZ|BJ))',  # A股代码
        r'([68]\d{5})',  # 6/8开头
        r'(00\d{5})',  # 00开头
        r'(30\d{5})',  # 30开头
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, title)
        for match in matches:
            if '.' not in match:
                # 添加交易所后缀
                if match.startswith('68') or match.startswith('6'):
                    ticker = f"{match}.SH"
                elif match.startswith('30') or match.startswith('00'):
                    ticker = f"{match}.SZ"
                else:
                    ticker = match
                if ticker not in tickers:
                    tickers.append(ticker)
    
    return tickers[:3]  # 最多返回3个

def normalize_title(title: str) -> str:
    """标准化标题用于去重比较"""
    import re
    # 去除标点符号、空格、转义字符
    title = re.sub(r'[^\w\u4e00-\u9fff]', '', title)
    # 转为小写
    title = title.lower()
    return title

def is_duplicate(title1: str, title2: str) -> bool:
    """判断两个标题是否重复（模糊匹配）"""
    # 标准化
    t1 = normalize_title(title1)
    t2 = normalize_title(title2)
    
    # 完全相同
    if t1 == t2:
        return True
    
    # 长度差异太大，不视为重复
    if len(t1) == 0 or len(t2) == 0:
        return False
    if abs(len(t1) - len(t2)) / max(len(t1), len(t2)) > 0.3:
        return False
    
    # 计算相似度（简单方法：公共子串占比）
    # 使用集合方法计算Jaccard相似度
    set1 = set(t1)
    set2 = set(t2)
    if len(set1) == 0 or len(set2) == 0:
        return False
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    similarity = intersection / union if union > 0 else 0
    
    # 相似度超过70%视为重复
    return similarity > 0.7

def deduplicate_news(news_items: List[NewsItem]) -> List[NewsItem]:
    """去除重复新闻"""
    if not news_items:
        return news_items
    
    unique_news = []
    seen_titles = []
    
    for item in news_items:
        is_dup = False
        for seen_title in seen_titles:
            if is_duplicate(item.title, seen_title):
                is_dup = True
                break
        
        if not is_dup:
            unique_news.append(item)
            seen_titles.append(item.title)
    
    removed = len(news_items) - len(unique_news)
    if removed > 0:
        print(f"[去重] 移除 {removed} 条重复新闻，保留 {len(unique_news)} 条")
    
    return unique_news

def fetch_tushare_news() -> List[NewsItem]:
    """从Tushare获取实时新闻 - 使用pro.news接口"""
    news_items = []
    
    if not TUSHARE_TOKEN:
        print("[警告] TUSHARE_TOKEN未设置，使用模拟数据")
        return get_mock_news()
    
    # 计算时间范围 - 最近2小时
    from datetime import timedelta
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=2)
    
    # 新闻来源列表 - 优先级顺序
    news_sources = [
        ('sina', '新浪财经'),
        ('cls', '财联社'),
        ('eastmoney', '东方财富'),
    ]
    
    for src_code, src_name in news_sources:
        try:
            pro = ts.pro_api()
            df = pro.news(
                src=src_code,
                start_date=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_date=end_time.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            if df is not None and not df.empty:
                print(f"[{src_name}] 获取到 {len(df)} 条新闻")
                
                for idx, row in df.iterrows():
                    title = str(row.get('title', ''))
                    content = str(row.get('content', ''))
                    
                    # 如果标题为空，用内容替代
                    if not title or title == 'None':
                        title = content[:80] if content else '无标题'
                    
                    if title and title != '无标题':
                        # 解析时间
                        datetime_str = str(row.get('datetime', ''))
                        try:
                            time_str = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S').strftime('%H:%M')
                        except:
                            time_str = datetime.now().strftime('%H:%M')
                        
                        news_items.append(NewsItem(
                            id=f"tushare_{src_code}_{idx}",
                            time=time_str,
                            title=title[:100],
                            source=src_name,
                            category=extract_category(title, content),
                            industry=extract_industry(title, content),
                            relatedTickers=extract_tickers(title) or None
                        ))
                
                # 如果获取到足够多的新闻就停止
                if len(news_items) >= 30:
                    break
                    
        except Exception as e:
            print(f"[{src_name}] 获取失败: {str(e)[:50]}")
            continue
    
    if not news_items:
        print("[警告] Tushare新闻获取失败，使用模拟数据")
        return get_mock_news()
    
    # 去重
    unique_news = deduplicate_news(news_items)
    
    # 按时间排序（最新的在前）
    unique_news.sort(key=lambda x: x.time, reverse=True)
    
    print(f"[总计] 获取 {len(unique_news)} 条去重后新闻")
    return unique_news[:50]


# API路由
    
    # 如果Tushare没有返回数据，使用模拟数据
    if not news_items:
        print("[Tushare] 无数据，使用模拟数据")
        return get_mock_news()
    
    return news_items[:50]  # 最多返回50条

def get_mock_news() -> List[NewsItem]:
    """获取模拟新闻数据（备用）"""
    return [
        NewsItem(
            id="1",
            time=datetime.now().strftime("%H:%M"),
            title="央行宣布降准0.5个百分点，释放流动性约1万亿元",
            source="央行官网",
            category="宏观政策",
            industry="银行",
            relatedTickers=["600036.SH"]
        ),
        NewsItem(
            id="2",
            time=datetime.now().strftime("%H:%M"),
            title="宁德时代：麒麟电池量产，能量密度提升50%",
            source="公司公告",
            category="公司新闻",
            industry="新能源",
            relatedTickers=["300750.SZ"]
        ),
        NewsItem(
            id="3",
            time=datetime.now().strftime("%H:%M"),
            title="贵州茅台Q4净利润预增15%，高端白酒需求旺盛",
            source="业绩预告",
            category="业绩快报",
            industry="白酒",
            relatedTickers=["600519.SH"]
        ),
        NewsItem(
            id="4",
            time=datetime.now().strftime("%H:%M"),
            title="半导体板块集体拉升，中芯国际涨超5%",
            source="行情快讯",
            category="板块异动",
            industry="半导体",
            relatedTickers=["688981.SH"]
        ),
    ]

# API路由
@app.get("/")
async def root():
    return {"message": "AI TradeBot API v2.0", "status": "running", "tushare_configured": bool(TUSHARE_TOKEN)}

@app.get("/api/news/stream", response_model=List[NewsItem])
async def get_news_stream():
    """获取实时新闻流 (Tushare)"""
    return fetch_tushare_news()

@app.post("/api/analysis/industry", response_model=AnalysisResult)
async def analyze_industry(request: AnalysisRequest):
    """AI行业分析"""
    import random
    sentiments = ["optimistic", "neutral", "pessimistic"]
    sentiment = random.choice(sentiments)
    
    summaries = {
        "optimistic": f"基于'{request.news_title}'的分析，该事件对行业产生积极影响，政策支持力度加大",
        "neutral": f"基于'{request.news_title}'的分析，该事件对行业影响中性，需持续观察",
        "pessimistic": f"基于'{request.news_title}'的分析，该事件可能对行业产生短期压力",
    }
    
    return AnalysisResult(
        industry="银行",
        sentiment=sentiment,
        confidence=0.75 + random.random() * 0.2,
        summary=summaries[sentiment],
        keyPoints=["流动性改善", "政策支持力度加大", "市场预期向好"],
    )

@app.get("/api/assets/industry/{industry}", response_model=List[Asset])
async def get_industry_assets(industry: str):
    """获取行业核心资产"""
    mock_assets_db = {
        "银行": [
            {"ticker": "600036.SH", "name": "招商银行", "type": "核心资产", "weight": "高", "price": 35.68, "change": 0.89, "changePct": 2.56},
            {"ticker": "000001.SZ", "name": "平安银行", "type": "核心资产", "weight": "高", "price": 12.58, "change": -0.12, "changePct": -0.94},
            {"ticker": "600016.SH", "name": "民生银行", "type": "一般资产", "weight": "中", "price": 3.92, "change": 0.03, "changePct": 0.77},
        ],
        "新能源": [
            {"ticker": "300750.SZ", "name": "宁德时代", "type": "核心资产", "weight": "高", "price": 198.50, "change": 5.20, "changePct": 2.69},
            {"ticker": "002594.SZ", "name": "比亚迪", "type": "核心资产", "weight": "高", "price": 268.00, "change": 3.50, "changePct": 1.32},
            {"ticker": "601012.SH", "name": "隆基绿能", "type": "一般资产", "weight": "中", "price": 22.35, "change": -0.45, "changePct": -1.97},
        ],
        "白酒": [
            {"ticker": "600519.SH", "name": "贵州茅台", "type": "核心资产", "weight": "高", "price": 1689.00, "change": 18.50, "changePct": 1.11},
            {"ticker": "000858.SZ", "name": "五粮液", "type": "核心资产", "weight": "高", "price": 148.20, "change": 2.10, "changePct": 1.44},
        ],
        "半导体": [
            {"ticker": "688981.SH", "name": "中芯国际", "type": "核心资产", "weight": "高", "price": 58.90, "change": 2.85, "changePct": 5.08},
            {"ticker": "688256.SH", "name": "寒武纪", "type": "成长资产", "weight": "中", "price": 125.60, "change": 8.20, "changePct": 6.99},
        ],
    }
    return mock_assets_db.get(industry, mock_assets_db["银行"])

@app.get("/api/technical/{ticker}", response_model=TechSignals)
async def get_technical_analysis(ticker: str):
    """获取技术分析信号 (MACD + 均线)"""
    import random
    
    macd_signals = ["golden_cross", "death_cross", "divergence", "neutral"]
    ma_trends = ["bullish", "bearish", "neutral"]
    overall_signals = ["BUY", "SELL", "HOLD", "STRONG_BUY", "STRONG_SELL"]
    
    macd_signal = random.choice(macd_signals)
    ma_trend = random.choice(ma_trends)
    
    if macd_signal == "golden_cross" and ma_trend == "bullish":
        overall = "STRONG_BUY"
    elif macd_signal == "golden_cross" or ma_trend == "bullish":
        overall = "BUY"
    elif macd_signal == "death_cross" and ma_trend == "bearish":
        overall = "STRONG_SELL"
    elif macd_signal == "death_cross" or ma_trend == "bearish":
        overall = "SELL"
    else:
        overall = "HOLD"
    
    return TechSignals(
        macd=MacdSignal(
            signal=macd_signal,
            strength=0.6 + random.random() * 0.3
        ),
        ma=MaSignal(
            trend=ma_trend,
            alignment="多头排列" if ma_trend == "bullish" else "空头排列" if ma_trend == "bearish" else "均线交织"
        ),
        overall=overall,
        indicators={
            "ma5": round(35.2 + random.random() * 2, 2),
            "ma10": round(34.8 + random.random() * 2, 2),
            "ma20": round(34.5 + random.random() * 2, 2),
            "macd": {"dif": round(0.5 + random.random() * 0.3, 2), "dea": round(0.3 + random.random() * 0.2, 2), "histogram": round(0.2 + random.random() * 0.1, 2)}
        }
    )

@app.get("/api/financial/monte-carlo/{ticker}", response_model=MonteCarloResult)
async def get_monte_carlo(ticker: str):
    """获取蒙特卡洛模拟结果"""
    import random
    
    try:
        import numpy as np
        returns = np.random.normal(0.0008, 0.025, 10000)
        var95 = abs(np.percentile(returns, 5) * 100)
        var99 = abs(np.percentile(returns, 1) * 100)
        
        return MonteCarloResult(
            var95=round(var95, 2),
            var99=round(var99, 2),
            sharpeRatio=round(1.2 + random.random() * 0.5, 2),
            maxDrawdown=round(10 + random.random() * 5, 2),
            winRate=round(55 + random.random() * 10, 2),
            distribution=[round(x, 4) for x in np.histogram(returns, bins=50)[0].tolist()]
        )
    except ImportError:
        # 如果没有numpy，返回模拟数据
        return MonteCarloResult(
            var95=2.5,
            var99=4.2,
            sharpeRatio=1.42,
            maxDrawdown=12.5,
            winRate=58.3,
            distribution=[round(random.random() * 10, 4) for _ in range(50)]
        )

if __name__ == "__main__":
    print(f"[启动] Tushare Token: {'已配置' if TUSHARE_TOKEN else '未配置'}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
