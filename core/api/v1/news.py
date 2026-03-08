"""
AI TradeBot - Tushare 快讯流 API

支持实时快讯获取（已禁用模拟数据）
"""
import os
from datetime import datetime, timedelta
from fastapi import APIRouter
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


# =============================================================================
# 状态管理
# =============================================================================

_news_service_state = {
    "enabled": False,
    "last_fetch": None,
    "news_count": 0,
}


# =============================================================================
# 辅助函数
# =============================================================================

def get_tushare_client():
    """获取Tushare客户端"""
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token:
        raise ValueError("Tushare Token未配置")
    
    import tushare as ts
    ts.set_token(tushare_token)
    return ts.pro_api()


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/feed")
async def get_news_feed(
    limit: int = 20,
    min_score: float = 0.0,
):
    """
    获取新闻快讯流

    Args:
        limit: 返回数量限制
        min_score: 最低评分过滤
    """
    # 检查Tushare Token
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token:
        return {
            "success": False,
            "error": "数据无法连接：Tushare Token未配置",
            "error_code": "TOKEN_NOT_CONFIGURED"
        }
    
    # 使用Tushare获取数据
    try:
        pro = get_tushare_client()
        
        # 获取财联社快讯
        df_cls = pro.major_news(fields="title,pub_time,src,url")
        
        # 获取新浪财经快讯
        df_sina = pro.news(fields="datetime,content,title")
        
        news_items = []
        
        # 处理财联社数据
        if df_cls is not None and not df_cls.empty:
            for _, row in df_cls.head(limit // 2).iterrows():
                pub_time = str(row.get("pub_time", ""))
                try:
                    publish_time = datetime.strptime(pub_time, "%Y-%m-%d %H:%M:%S").isoformat()
                except:
                    publish_time = datetime.now().isoformat()
                
                news_items.append({
                    "id": f"cls_{hash(row.get('title', '')) % 100000}",
                    "title": str(row.get("title", ""))[:100],
                    "content": "",
                    "source": str(row.get("src", "财联社")),
                    "publish_time": publish_time,
                    "score": 7.0,
                    "category": "财经快讯",
                    "sentiment": "neutral",
                    "ticker": None,
                })
        
        # 处理新浪数据
        if df_sina is not None and not df_sina.empty:
            for _, row in df_sina.head(limit // 2).iterrows():
                dt_str = str(row.get("datetime", ""))
                try:
                    publish_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").isoformat()
                except:
                    publish_time = datetime.now().isoformat()
                
                title = str(row.get("title", ""))[:100] if row.get("title") else ""
                content = str(row.get("content", ""))[:200] if row.get("content") else ""
                
                if not title and content:
                    title = content[:100]
                
                news_items.append({
                    "id": f"sina_{hash(title) % 100000}",
                    "title": title,
                    "content": content,
                    "source": "新浪财经",
                    "publish_time": publish_time,
                    "score": 7.0,
                    "category": "财经快讯",
                    "sentiment": "neutral",
                    "ticker": None,
                })
        
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
                "mode": "live",
            }
        }

    except Exception as e:
        logger.error(f"[新闻 API] 获取实时数据失败: {e}")
        return {
            "success": False,
            "error": f"数据无法连接: {str(e)}",
            "error_code": "DATA_CONNECTION_FAILED",
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
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token:
        return {
            "success": False,
            "error": "数据无法连接：Tushare Token未配置",
            "error_code": "TOKEN_NOT_CONFIGURED"
        }
    
    try:
        pro = get_tushare_client()
        df_cls = pro.major_news(fields="title,pub_time,src,url")
        
        news_items = []
        if df_cls is not None and not df_cls.empty:
            for _, row in df_cls.iterrows():
                pub_time = str(row.get("pub_time", ""))
                try:
                    publish_time = datetime.strptime(pub_time, "%Y-%m-%d %H:%M:%S").isoformat()
                except:
                    publish_time = datetime.now().isoformat()
                
                news_items.append({
                    "id": f"cls_{hash(row.get('title', '')) % 100000}",
                    "title": str(row.get("title", ""))[:100],
                    "content": "",
                    "source": str(row.get("src", "财联社")),
                    "publish_time": publish_time,
                    "score": 7.0,
                    "category": "财经快讯",
                    "sentiment": "neutral",
                    "ticker": None,
                })
        
        # 过滤评分
        high_score_items = [n for n in news_items if n.get("score", 0) >= threshold][:limit]
        
        return {
            "success": True,
            "data": {
                "items": high_score_items,
                "count": len(high_score_items),
                "threshold": threshold,
                "mode": "live",
            }
        }
    except Exception as e:
        logger.error(f"[新闻 API] 获取高分新闻失败: {e}")
        return {
            "success": False,
            "error": f"数据无法连接: {str(e)}",
            "error_code": "DATA_CONNECTION_FAILED",
        }


@router.post("/toggle")
async def toggle_news_service(request: NewsToggleRequest):
    """切换新闻服务状态"""
    _news_service_state["enabled"] = request.enabled
    _news_service_state["last_fetch"] = datetime.now().isoformat()

    status = "enabled" if request.enabled else "disabled"
    logger.info(f"[新闻 API] 服务状态: {status}")

    return {
        "success": True,
        "data": {
            "enabled": request.enabled,
            "message": f"新闻服务已{'启用' if request.enabled else '禁用'}",
        }
    }


@router.get("/status")
async def get_news_status():
    """获取新闻服务状态"""
    return {
        "success": True,
        "data": {
            **_news_service_state,
            "tushare_configured": bool(os.getenv("TUSHARE_TOKEN")),
        }
    }


@router.get("/latest")
async def get_latest_news(minutes: int = 60):
    """获取最近指定分钟内的新闻"""
    tushare_token = os.getenv("TUSHARE_TOKEN")
    if not tushare_token:
        return {
            "success": False,
            "error": "数据无法连接：Tushare Token未配置",
            "error_code": "TOKEN_NOT_CONFIGURED"
        }
    
    try:
        pro = get_tushare_client()
        df_cls = pro.major_news(fields="title,pub_time,src,url")
        
        news_items = []
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        if df_cls is not None and not df_cls.empty:
            for _, row in df_cls.iterrows():
                pub_time = str(row.get("pub_time", ""))
                try:
                    publish_time = datetime.strptime(pub_time, "%Y-%m-%d %H:%M:%S")
                    if publish_time >= cutoff_time:
                        news_items.append({
                            "id": f"cls_{hash(row.get('title', '')) % 100000}",
                            "title": str(row.get("title", ""))[:100],
                            "content": "",
                            "source": str(row.get("src", "财联社")),
                            "publish_time": publish_time.isoformat(),
                            "score": 7.0,
                            "category": "财经快讯",
                            "sentiment": "neutral",
                            "ticker": None,
                        })
                except:
                    pass
        
        return {
            "success": True,
            "data": {
                "items": news_items,
                "count": len(news_items),
                "time_range_minutes": minutes,
                "mode": "live",
            }
        }
    except Exception as e:
        logger.error(f"[新闻 API] 获取最新新闻失败: {e}")
        return {
            "success": False,
            "error": f"数据无法连接: {str(e)}",
            "error_code": "DATA_CONNECTION_FAILED",
        }


__all__ = ["router"]
