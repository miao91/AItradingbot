"""
AI TradeBot - Tushare 快讯流 API

支持实时快讯获取和模拟测试模式
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.logging import get_logger


logger = get_logger(__name__)

router = APIRouter(prefix="/news", tags=["news"])


# =============================================================================
# Request Models
# =============================================================================

class NewsToggleRequest(BaseModel):
    """新闻服务开关请求"""
    enabled: bool
    use_mock: bool = False  # 使用模拟数据


# =============================================================================
# 模拟新闻数据
# =============================================================================

MOCK_NEWS_DATA = [
    {
        "id": "mock_001",
        "title": "美联储暗示降息周期可能提前，市场情绪提振",
        "content": "美联储主席在最新讲话中暗示，如果通胀数据持续改善，降息周期可能比预期更早开始。市场分析认为，这一表态显著改善了投资者情绪。",
        "source": "模拟-财联社",
        "publish_time": (datetime.now() - timedelta(minutes=5)).isoformat(),
        "score": 8.5,
        "category": "宏观经济",
        "sentiment": "positive",
        "ticker": None,
    },
    {
        "id": "mock_002",
        "title": "某科技公司发布新一代AI芯片，性能提升200%",
        "content": "国内领先芯片企业今日发布新一代AI训练芯片，相比上一代性能提升200%，能耗降低30%。分析师认为这将重塑国产AI芯片竞争格局。",
        "source": "模拟-新浪财经",
        "publish_time": (datetime.now() - timedelta(minutes=15)).isoformat(),
        "score": 9.0,
        "category": "科技",
        "sentiment": "positive",
        "ticker": "300XXX.SZ",
    },
    {
        "id": "mock_003",
        "title": "新能源汽车销量创新高，行业景气度持续",
        "content": "乘联会数据显示，本月新能源汽车销量达到历史新高，同比增长45%。头部企业市场份额进一步提升。",
        "source": "模拟-财联社",
        "publish_time": (datetime.now() - timedelta(minutes=30)).isoformat(),
        "score": 7.5,
        "category": "汽车",
        "sentiment": "positive",
        "ticker": None,
    },
    {
        "id": "mock_004",
        "title": "央行开展MLF操作，释放流动性信号",
        "content": "央行今日开展1000亿元MLF操作，利率维持不变。市场解读为维持流动性合理充裕的政策信号。",
        "source": "模拟-新华财经",
        "publish_time": (datetime.now() - timedelta(hours=1)).isoformat(),
        "score": 7.0,
        "category": "货币政策",
        "sentiment": "neutral",
        "ticker": None,
    },
    {
        "id": "mock_005",
        "title": "某地产企业债务重组方案获批，风险缓释",
        "content": "知名房企债务重组方案获债权人会议通过，市场对地产行业风险担忧有所缓解。",
        "source": "模拟-财联社",
        "publish_time": (datetime.now() - timedelta(hours=2)).isoformat(),
        "score": 6.5,
        "category": "房地产",
        "sentiment": "neutral",
        "ticker": "000XXX.SZ",
    },
    {
        "id": "mock_006",
        "title": "半导体板块集体走强，国产替代加速推进",
        "content": "受政策利好刺激，半导体板块今日集体上涨。业内人士表示，国产替代进程正在加速，本土企业迎来发展机遇。",
        "source": "模拟-同花顺",
        "publish_time": (datetime.now() - timedelta(minutes=45)).isoformat(),
        "score": 8.0,
        "category": "科技",
        "sentiment": "positive",
        "ticker": "688XXX.SH",
    },
    {
        "id": "mock_007",
        "title": "医药行业集采结果公布，多家企业中标",
        "content": "第十批国家药品集采结果公布，多家国内药企中标。分析认为，集采常态化将加速行业洗牌。",
        "source": "模拟-医药经济报",
        "publish_time": (datetime.now() - timedelta(hours=3)).isoformat(),
        "score": 6.0,
        "category": "医药",
        "sentiment": "neutral",
        "ticker": None,
    },
    {
        "id": "mock_008",
        "title": "跨境电商出口额同比增长35%，政策红利持续释放",
        "content": "商务部数据显示，前三季度跨境电商出口额同比增长35%。RCEP生效后，东南亚市场成为新的增长点。",
        "source": "模拟-商务部",
        "publish_time": (datetime.now() - timedelta(hours=4)).isoformat(),
        "score": 7.5,
        "category": "外贸",
        "sentiment": "positive",
        "ticker": None,
    },
    {
        "id": "mock_009",
        "title": "光伏产业链价格企稳，装机需求旺盛",
        "content": "硅料价格经过前期下跌后开始企稳，下游装机需求保持旺盛。预计全年新增装机将创新高。",
        "source": "模拟-光伏行业协会",
        "publish_time": (datetime.now() - timedelta(hours=5)).isoformat(),
        "score": 7.0,
        "category": "新能源",
        "sentiment": "positive",
        "ticker": "601XXX.SH",
    },
    {
        "id": "mock_010",
        "title": "北向资金净流入超百亿，外资看好A股后市",
        "content": "今日北向资金净流入达120亿元，连续三日净流入。外资机构表示，A股估值处于历史低位，配置价值凸显。",
        "source": "模拟-证券时报",
        "publish_time": (datetime.now() - timedelta(minutes=10)).isoformat(),
        "score": 8.5,
        "category": "资金面",
        "sentiment": "positive",
        "ticker": None,
    },
]


# =============================================================================
# 状态管理
# =============================================================================

_news_service_state = {
    "enabled": False,
    "use_mock": True,  # 默认使用模拟模式
    "last_fetch": None,
    "news_count": 0,
}


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/feed")
async def get_news_feed(
    limit: int = 20,
    min_score: float = 0.0,
    use_mock: bool = True,
):
    """
    获取新闻快讯流

    Args:
        limit: 返回数量限制
        min_score: 最低评分过滤
        use_mock: 是否使用模拟数据
    """
    try:
        if use_mock or not os.getenv("TUSHARE_TOKEN"):
            # 使用模拟数据
            news_items = MOCK_NEWS_DATA.copy()

            # 过滤评分
            if min_score > 0:
                news_items = [n for n in news_items if n.get("score", 0) >= min_score]

            # 限制数量
            news_items = news_items[:limit]

            return {
                "success": True,
                "data": {
                    "items": news_items,
                    "count": len(news_items),
                    "mode": "mock",
                    "message": "使用模拟数据（Tushare Token 未配置或未启用）",
                }
            }
        else:
            # 使用真实 Tushare 数据
            try:
                from perception.news.tushare_sentinel import get_tushare_sentinel

                sentinel = get_tushare_sentinel()

                # 获取新闻（这里简化处理）
                # 实际应该从缓存或数据库获取
                news_items = []

                return {
                    "success": True,
                    "data": {
                        "items": news_items,
                        "count": len(news_items),
                        "mode": "live",
                        "message": "实时数据",
                    }
                }

            except Exception as e:
                logger.error(f"[新闻 API] 获取实时数据失败: {e}")
                # 降级到模拟数据
                return {
                    "success": True,
                    "data": {
                        "items": MOCK_NEWS_DATA[:limit],
                        "count": min(limit, len(MOCK_NEWS_DATA)),
                        "mode": "mock",
                        "message": f"实时数据获取失败，使用模拟数据: {str(e)}",
                    }
                }

    except Exception as e:
        logger.error(f"[新闻 API] 获取新闻失败: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/high-score")
async def get_high_score_news(
    threshold: float = 7.0,
    limit: int = 10,
):
    """
    获取高评分新闻

    返回评分超过阈值的重要新闻
    """
    # 使用模拟数据筛选高分新闻
    high_score_items = [
        item for item in MOCK_NEWS_DATA
        if item.get("score", 0) >= threshold
    ][:limit]

    return {
        "success": True,
        "data": {
            "items": high_score_items,
            "count": len(high_score_items),
            "threshold": threshold,
            "mode": "mock",
        }
    }


@router.post("/toggle")
async def toggle_news_service(request: NewsToggleRequest):
    """
    切换新闻服务状态

    Args:
        enabled: 是否启用
        use_mock: 是否使用模拟数据
    """
    _news_service_state["enabled"] = request.enabled
    _news_service_state["use_mock"] = request.use_mock
    _news_service_state["last_fetch"] = datetime.now().isoformat()

    status = "enabled" if request.enabled else "disabled"
    mode = "mock" if request.use_mock else "live"

    logger.info(f"[新闻 API] 服务状态: {status}, 模式: {mode}")

    return {
        "success": True,
        "data": {
            "enabled": request.enabled,
            "use_mock": request.use_mock,
            "mode": mode,
            "message": f"新闻服务已{'启用' if request.enabled else '禁用'}",
        }
    }


@router.get("/status")
async def get_news_status():
    """
    获取新闻服务状态
    """
    return {
        "success": True,
        "data": {
            **_news_service_state,
            "tushare_configured": bool(os.getenv("TUSHARE_TOKEN")),
        }
    }


@router.get("/latest")
async def get_latest_news(minutes: int = 60):
    """
    获取最近指定分钟内的新闻

    Args:
        minutes: 时间范围（分钟）
    """
    cutoff_time = datetime.now() - timedelta(minutes=minutes)

    # 过滤模拟数据
    recent_items = []
    for item in MOCK_NEWS_DATA:
        try:
            item_time = datetime.fromisoformat(item["publish_time"])
            if item_time >= cutoff_time:
                recent_items.append(item)
        except:
            pass

    return {
        "success": True,
        "data": {
            "items": recent_items,
            "count": len(recent_items),
            "time_range_minutes": minutes,
            "mode": "mock",
        }
    }


__all__ = ["router"]
