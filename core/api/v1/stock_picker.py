"""
AI TradeBot - 选股API路由
"""

import os
from datetime import datetime
from fastapi import APIRouter, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from decision.engine.wall_street_selector import (
    run_stock_selection,
    StrategyMode,
    PortfolioSignal,
    StockSignal,
)


router = APIRouter(prefix="/stock_picker", tags=["选股引擎"])


# ==================== 请求模型 ====================

class StockDataRequest(BaseModel):
    """单只股票数据请求"""
    ticker: str
    name: Optional[str] = None


class StockSelectionRequest(BaseModel):
    """选股请求"""
    tickers: List[str]
    strategy_mode: str = "auto"
    max_positions: int = 10


# ==================== 响应模型 ====================

class StockSignalResponse(BaseModel):
    """股票信号响应"""
    ticker: str
    name: str
    composite_score: float
    score_level: str
    fundamental_score: float
    technical_score: float
    risk_score: float
    signal_type: str
    signal_strength: float
    confidence: float
    position_size: float
    target_price: float
    stop_loss: float
    time_horizon: str
    rank: int


class PortfolioSignalResponse(BaseModel):
    """组合信号响应"""
    signals: List[StockSignalResponse]
    strategy_mode: str
    total_positions: int
    expected_return: float
    sharpe_ratio: float
    total_var: float
    generated_at: str


def signal_to_response(signal: StockSignal) -> StockSignalResponse:
    """转换信号到响应"""
    return StockSignalResponse(
        ticker=signal.ticker,
        name=signal.name,
        composite_score=signal.composite_score,
        score_level=signal.score_level,
        fundamental_score=signal.fundamental_score,
        technical_score=signal.technical_score,
        risk_score=signal.risk_score,
        signal_type=signal.signal_type,
        signal_strength=signal.signal_strength,
        confidence=signal.confidence,
        position_size=signal.position_size,
        target_price=signal.target_price,
        stop_loss=signal.stop_loss,
        time_horizon=signal.time_horizon,
        rank=signal.rank,
    )


def get_tushare_data(tickers: List[str]) -> tuple:
    """获取Tushare实时股票数据"""
    tushare_token = os.getenv("TUSHARE_TOKEN")
    market_data = {}
    fundamental_data = {}
    errors = []
    
    if not tushare_token:
        raise ValueError("Tushare Token未配置")
    
    try:
        import tushare as ts
        ts.set_token(tushare_token)
        pro = ts.pro_api()
        today = datetime.now().strftime("%Y%m%d")
        
        for ticker in tickers:
            try:
                df_daily = pro.daily(ts_code=ticker, trade_date=today)
                df_basic = pro.daily_basic(ts_code=ticker, trade_date=today)
                
                if df_daily is not None and not df_daily.empty:
                    row = df_daily.iloc[-1]
                    market_data[ticker] = {
                        "price": float(row.get("close", 0)),
                        "pct_chg": float(row.get("pct_chg", 0)),
                        "open": float(row.get("open", 0)),
                        "high": float(row.get("high", 0)),
                        "low": float(row.get("low", 0)),
                        "vol": int(row.get("vol", 0)),
                        "amount": float(row.get("amount", 0)),
                        "pre_close": float(row.get("pre_close", 0)),
                    }
                else:
                    errors.append(f"{ticker}: 无行情数据")
                
                if df_basic is not None and not df_basic.empty:
                    row = df_basic.iloc[-1]
                    fundamental_data[ticker] = {
                        "turnover_rate": float(row.get("turnover_rate", 0)),
                        "volume_ratio": float(row.get("volume_ratio", 1)),
                        "pe": float(row.get("pe", 0)),
                        "pb": float(row.get("pb", 0)),
                        "total_mv": float(row.get("total_mv", 0)),
                        "circ_mv": float(row.get("circ_mv", 0)),
                    }
                    
            except Exception as e:
                errors.append(f"{ticker}: {str(e)}")
                continue
                
    except Exception as e:
        raise RuntimeError(f"数据无法连接: {str(e)}")
    
    if not market_data:
        error_msg = "; ".join(errors) if errors else "未能获取任何数据"
        raise ValueError(f"数据无法连接: {error_msg}")
    
    return market_data, fundamental_data


# ==================== API端点 ====================

@router.post("/select", response_model=PortfolioSignalResponse)
async def stock_selection(request: StockSelectionRequest):
    """
    选股主入口
    
    根据多因子模型生成选股信号，支持以下策略模式:
    - auto: 自动检测市场状态选择策略
    - momentum: 动量策略
    - reversal: 反转策略
    - quality: 质量策略
    - growth: 成长策略
    - value: 价值策略
    """
    # 获取Tushare真实数据（无模拟数据降级）
    try:
        market_data, fundamental_data = get_tushare_data(request.tickers)
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "error_code": "DATA_CONNECTION_FAILED",
        }
    
    # 运行选股
    result = await run_stock_selection(
        tickers=request.tickers,
        market_data=market_data,
        fundamental_data=fundamental_data,
        strategy_mode=request.strategy_mode,
        max_positions=request.max_positions,
    )
    
    # 转换为响应
    return PortfolioSignalResponse(
        signals=[signal_to_response(s) for s in result.signals],
        strategy_mode=result.strategy_mode,
        total_positions=result.total_positions,
        expected_return=result.expected_return,
        sharpe_ratio=result.sharpe_ratio,
        total_var=result.total_var,
        generated_at=result.generated_at,
    )


@router.get("/factors")
async def get_factor_info():
    """
    获取因子信息
    
    返回所有可用因子及其权重配置
    """
    from decision.engine.wall_street_selector import FACTOR_CONFIG
    
    factors = []
    for category, factor_dict in FACTOR_CONFIG.items():
        for factor_name, params in factor_dict.items():
            factors.append({
                "category": category,
                "name": factor_name,
                "weight": params.get("weight", 0),
                "description": params.get("description", ""),
                "direction": params.get("direction", "neutral"),
                "optimal_range": params.get("optimal_range", []),
            })
    
    return {
        "total_factors": len(factors),
        "factors": factors,
    }


@router.get("/strategies")
async def get_strategies():
    """
    获取可用策略模式
    """
    strategies = [
        {
            "mode": "auto",
            "name": "自动模式",
            "description": "根据市场状态自动选择最佳策略",
        },
        {
            "mode": "momentum",
            "name": "动量策略",
            "description": "追涨杀跌，适合牛市",
        },
        {
            "mode": "reversal",
            "name": "反转策略",
            "description": "低买高卖，适合熊市",
        },
        {
            "mode": "quality",
            "name": "质量策略",
            "description": "选择优质龙头，适合震荡市",
        },
        {
            "mode": "growth",
            "name": "成长策略",
            "description": "高增长预期，适合结构性行情",
        },
        {
            "mode": "value",
            "name": "价值策略",
            "description": "低估值策略，适合价值回归",
        },
    ]
    
    return {"strategies": strategies}


@router.get("/realtime")
async def get_realtime_prices(tickers: str = "600519.SH,000001.SZ,300750.SZ"):
    """获取实时股票价格"""
    ticker_list = [t.strip() for t in tickers.split(",")]
    
    try:
        market_data, _ = get_tushare_data(ticker_list)
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "error_code": "DATA_CONNECTION_FAILED",
        }
    
    for ticker in market_data:
        market_data[ticker]["source"] = "tushare"
            market_data[ticker]["source"] = "tushare"
    
    return {
        "success": True,
        "data": {
            "tickers": market_data,
            "count": len(market_data),
            "timestamp": datetime.now().isoformat(),
        }
    }
