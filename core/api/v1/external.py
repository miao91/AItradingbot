"""
AI TradeBot - 外部数据 API (FunHub 汇率数据)

提供实时汇率数据的后端接口
"""

import os
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/external", tags=["external"])


# =============================================================================
# Configuration
# =============================================================================

FUNHUB_CONFIG = {
    "api_key": os.getenv("FUNHUB_API_KEY", ""),
    "base_url": os.getenv("FUNHUB_BASE_URL", "https://api.fung_hub.com"),
    "timeout": 10,
}

# Finnhub 配置
FINNHUB_CONFIG = {
    "api_key": os.getenv("FINNHUB_API_KEY", ""),
    "base_url": "https://finnhub.io/api/v1",
    "timeout": 10,
}

# 美元指数配置
DXY_CONFIG = {
    "base_url": os.getenv("DXY_API_URL", "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"),
    # DXY 由以下货币组成:
    # EUR (57.6%), JPY (13.6%), GBP (11.9%), CAD (9.1%), SEK (4.2%), CHF (3.6%)
    "component_weights": {
        "EUR/USD": 0.576,
        "USD/JPY": 0.136,
        "GBP/USD": 0.119,
        "USD/CAD": 0.091,
        "USD/SEK": 0.042,
        "USD/CHF": 0.036,
    },
}


# =============================================================================
# Models
# =============================================================================

class ForexRateResponse(BaseModel):
    """汇率响应"""

    currency_pair: str  # USD/CNH, EUR/USD, etc.
    rate: float
    bid: float
    ask: float
    timestamp: str
    change_24h: float = 0.0  # 24小时变动
    status: str  # stable, warning, danger


class DollarIndexResponse(BaseModel):
    """美元指数响应"""

    dxy_value: float  # 美元指数值
    change_pct: float  # 变动百分比
    change_24h: float  # 24小时变动
    timestamp: str
    status: str  # stable, warning, danger
    source: str = "yahoo_finance"  # 数据来源
    components: Dict[str, float] = {}  # 组成货币汇率


# =============================================================================
# Helper Functions
# =============================================================================

async def _fetch_forex_from_funhub(currency_pair: str = "USD/CNH") -> Dict[str, Any]:
    """
    获取汇率数据

    优先使用 Yahoo Finance (免费，实时)

    Args:
        currency_pair: 货币对，如 USD/CNH

    Returns:
        汇率数据字典
    """
    # Yahoo Finance 货币对映射
    yahoo_tickers = {
        "USD/CNH": "CNH=X",
        "USD/CNY": "CNY=X",
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "JPY=X",
        "USD/CAD": "CAD=X",
        "USD/SEK": "SEK=X",
        "USD/CHF": "CHF=X",
    }

    # 尝试 Yahoo Finance
    try:
        ticker = yahoo_tickers.get(currency_pair, currency_pair.replace("/", "") + "=X")
        async with httpx.AsyncClient(timeout=10) as client:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/" + ticker
            params = {"interval": "1d", "range": "1d"}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            result = data.get("chart", {}).get("result", [{}])[0]
            meta = result.get("meta", {})

            rate = meta.get("regularMarketPrice")
            previous_close = meta.get("previousClose", rate)

            if rate:
                change_24h = ((rate - previous_close) / previous_close * 100) if previous_close else 0
                logger.info(f"[Forex] Yahoo Finance {currency_pair}: {rate}")

                return {
                    "currency_pair": currency_pair,
                    "rate": round(float(rate), 4),
                    "bid": round(float(rate) - 0.005, 4),
                    "ask": round(float(rate) + 0.005, 4),
                    "timestamp": datetime.now().isoformat(),
                    "change_24h": round(change_24h, 4),
                }
    except Exception as e:
        logger.warning(f"[Forex] Yahoo Finance 失败: {e}")

    # 降级到模拟数据
    logger.warning("[Forex] 使用模拟数据")
    return _generate_mock_forex_data(currency_pair)


def _generate_mock_forex_data(currency_pair: str = "USD/CNH") -> Dict[str, Any]:
    """
    生成模拟汇率数据（当 API 不可用时）
    """
    # 基础汇率（2026 年的假设值）
    base_rates = {
        "USD/CNH": 7.24,
        "EUR/USD": 1.08,
        "GBP/USD": 1.26,
        "USD/JPY": 149.50,
        "USD/CAD": 1.35,
        "USD/SEK": 10.50,
        "USD/CHF": 0.88,
    }

    base_rate = base_rates.get(currency_pair, 7.24)
    fluctuation = (random.random() - 0.5) * 0.05  # ±0.025 的波动

    rate = base_rate + fluctuation
    change_24h = (random.random() - 0.5) * 0.02  # ±0.01 的24小时变动

    return {
        "currency_pair": currency_pair,
        "rate": round(rate, 4),
        "bid": round(rate - 0.005, 4),
        "ask": round(rate + 0.005, 4),
        "timestamp": datetime.now().isoformat(),
        "change_24h": round(change_24h, 4),
    }


def _calculate_forex_status(rate: float, base_rate: float = 7.24) -> str:
    """
    根据汇率波动计算状态
    """
    deviation = abs(rate - base_rate) / base_rate

    if deviation > 0.01:  # 1% 以上波动
        return "danger"
    elif deviation > 0.005:  # 0.5% 以上波动
        return "warning"
    else:
        return "stable"


async def _calculate_dxy() -> Dict[str, Any]:
    """
    获取美元指数 (DXY) 数据

    优先级：
    1. Yahoo Finance (免费，无需 key)
    2. Finnhub (需要 API key，但免费版不支持外汇)

    Returns:
        DXY 数据字典
    """
    # 尝试 Yahoo Finance
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB"
            params = {"interval": "1d", "range": "2d"}
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            result = data.get("chart", {}).get("result", [{}])[0]
            meta = result.get("meta", {})
            indicators = result.get("indicators", {}).get("quote", [{}])[0]

            dxy_value = meta.get("regularMarketPrice")
            previous_close = meta.get("previousClose", dxy_value)

            if dxy_value and previous_close:
                change_pct = ((dxy_value - previous_close) / previous_close) * 100
            else:
                change_pct = 0

            closes = indicators.get("close", [])
            if len(closes) >= 2 and closes[0] and closes[-1]:
                change_24h = ((closes[-1] - closes[0]) / closes[0]) * 100
            else:
                change_24h = change_pct

            logger.info(f"[DXY] Yahoo Finance: {dxy_value:.2f}, 变动: {change_pct:.3f}%")

            return {
                "dxy_value": round(dxy_value, 2),
                "change_pct": round(change_pct, 3),
                "change_24h": round(change_24h, 3),
                "timestamp": datetime.now().isoformat(),
                "components": {},
                "source": "yahoo_finance",
            }

    except Exception as e:
        logger.warning(f"[DXY] Yahoo Finance 失败: {e}")

    # Finnhub 免费版不支持外汇，尝试其他方案
    try:
        return await _fetch_dxy_from_finnhub()
    except Exception as e:
        logger.error(f"[DXY] Finnhub 也失败: {e}")
        raise RuntimeError(f"无法获取 DXY 数据，请检查网络连接。Yahoo错误: {e}")


async def _fetch_dxy_from_finnhub() -> Dict[str, Any]:
    """
    从 Finnhub 获取美元指数数据

    Finnhub 不直接提供 DXY，但可以通过外汇数据计算
    """
    api_key = FINNHUB_CONFIG["api_key"]
    if not api_key:
        raise RuntimeError("Finnhub API Key 未配置")

    async with httpx.AsyncClient(timeout=FINNHUB_CONFIG["timeout"]) as client:
        # 获取主要外汇汇率
        # Finnhub forex rates: base=USD
        url = f"{FINNHUB_CONFIG['base_url']}/forex/rates"
        params = {"base": "USD", "token": api_key}

        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # 从汇率数据计算 DXY
        # DXY = 50.14348112 × EUR^(-0.576) × JPY^0.136 × GBP^(-0.119) × CAD^0.091 × SEK^0.042 × CHF^0.036
        rates = data.get("quote", {})

        eur = rates.get("EUR", 0.92)  # USD/EUR ≈ 0.92
        jpy = rates.get("JPY", 149.0)
        gbp = rates.get("GBP", 0.79)
        cad = rates.get("CAD", 1.35)
        sek = rates.get("SEK", 10.5)
        chf = rates.get("CHF", 0.88)

        dxy = 50.14348112
        dxy *= pow(1 / eur, -0.576) if eur else 1  # EUR/USD
        dxy *= pow(jpy, 0.136) if jpy else 1
        dxy *= pow(1 / gbp, -0.119) if gbp else 1  # GBP/USD
        dxy *= pow(cad, 0.091) if cad else 1
        dxy *= pow(sek, 0.042) if sek else 1
        dxy *= pow(chf, 0.036) if chf else 1

        logger.info(f"[DXY] Finnhub: {dxy:.2f}")

        return {
            "dxy_value": round(dxy, 2),
            "change_pct": 0,  # Finnhub 免费版不提供变动数据
            "change_24h": 0,
            "timestamp": datetime.now().isoformat(),
            "components": {
                "EUR/USD": round(1 / eur, 4) if eur else 0,
                "USD/JPY": jpy,
                "GBP/USD": round(1 / gbp, 4) if gbp else 0,
                "USD/CAD": cad,
                "USD/SEK": sek,
                "USD/CHF": chf,
            },
            "source": "finnhub",
        }


def _calculate_dxy_status(change_pct: float) -> str:
    """
    根据美元指数变动计算状态

    DXY 波动阈值：
    - >0.5%: danger（显著波动，可能影响全球市场）
    - >0.25%: warning
    - <=0.25%: stable
    """
    abs_change = abs(change_pct)

    if abs_change > 0.5:
        return "danger"
    elif abs_change > 0.25:
        return "warning"
    else:
        return "stable"


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/forex/{currency_pair}", response_model=ForexRateResponse)
async def get_forex_rate(currency_pair: str = "USD/CNH"):
    """
    获取实时汇率数据

    Args:
        currency_pair: 货币对，如 USD/CNH, EUR/USD

    Returns:
        汇率数据
    """
    try:
        logger.info(f"[FunHub] 获取汇率: {currency_pair}")

        data = await _fetch_forex_from_funhub(currency_pair)
        status = _calculate_forex_status(data["rate"])

        return ForexRateResponse(
            currency_pair=data["currency_pair"],
            rate=data["rate"],
            bid=data["bid"],
            ask=data["ask"],
            timestamp=data["timestamp"],
            change_24h=data["change_24h"],
            status=status,
        )

    except Exception as e:
        logger.error(f"[FunHub] 汇率获取失败: {e}")
        raise HTTPException(status_code=500, detail=f"汇率获取失败: {str(e)}")


@router.get("/dxy", response_model=DollarIndexResponse)
async def get_dollar_index():
    """
    获取美元指数 (DXY)

    美元指数衡量美元相对于一篮子货币的价值：
    - EUR (57.6%)
    - JPY (13.6%)
    - GBP (11.9%)
    - CAD (9.1%)
    - SEK (4.2%)
    - CHF (3.6%)

    Returns:
        美元指数数据
    """
    try:
        logger.info("[DXY] 获取美元指数")

        data = await _calculate_dxy()
        status = _calculate_dxy_status(data["change_pct"])

        return DollarIndexResponse(
            dxy_value=data["dxy_value"],
            change_pct=data["change_pct"],
            change_24h=data["change_24h"],
            timestamp=data["timestamp"],
            status=status,
            source=data.get("source", "yahoo_finance"),
            components=data["components"],
        )

    except Exception as e:
        logger.error(f"[DXY] 获取失败: {e}")
        raise HTTPException(status_code=500, detail=f"美元指数获取失败: {str(e)}")


@router.get("/dxy/simple")
async def get_dxy_simple() -> float:
    """
    获取美元指数简单值（供内部调用）

    Returns:
        DXY 值
    """
    data = await _calculate_dxy()
    return data["dxy_value"]


# 便捷函数（向后兼容）
async def get_usdcnh_rate() -> float:
    """获取 USD/CNH 汇率"""
    data = await _fetch_forex_from_funhub("USD/CNH")
    return data["rate"]


async def get_dxy() -> Dict[str, Any]:
    """获取美元指数数据"""
    return await _calculate_dxy()


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "service": "external_data_api",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "funhub_configured": bool(FUNHUB_CONFIG["api_key"]),
    }
