"""
AI TradeBot - 实时决策路由器

接收实时新闻 -> 初筛 -> 触发完整分析 -> 存储到数据库
支持流式WebSocket推送，实时展示AI工作状态
"""
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger

from perception.openclaw.live_monitor import NewsItem
from decision.workflows.event_analyzer import analyze_event
from shared.utils.ticker_extractor import extract_tickers


# =============================================================================
# 导入WebSocket广播函数
# =============================================================================
def _get_broadcast_functions():
    """延迟导入避免循环依赖"""
    try:
        from core.api.app import (
            broadcast_perception_start,
            broadcast_perception_captured,
            broadcast_analysis_start,
            broadcast_ai_thinking,
            broadcast_decision_complete,
            broadcast_event_filtered
        )
        return {
            'perception_start': broadcast_perception_start,
            'perception_captured': broadcast_perception_captured,
            'analysis_start': broadcast_analysis_start,
            'ai_thinking': broadcast_ai_thinking,
            'decision_complete': broadcast_decision_complete,
            'event_filtered': broadcast_event_filtered,
        }
    except ImportError:
        logger.warning("无法导入WebSocket广播函数，实时推送功能不可用")
        return {}


# =============================================================================
# 配置
# =============================================================================

ROUTER_CONFIG = {
    # 初筛 AI 配置
    "filter_model": "zhipuai",  # 使用智谱进行轻量级过滤

    # 初筛阈值
    "min_relevance_score": 0.6,  # 最低相关性分数

    # 自动分析配置
    "auto_analyze": True,  # 是否自动触发完整分析
    "auto_confirm": False,  # 是否自动确认（设为 False 需要人工确认）
}


# =============================================================================
# 初筛提示词
# =============================================================================

LIGHTWEIGHT_FILTER_PROMPT = """
你是一个专业的股市新闻初筛助手。请快速判断以下新闻是否具有交易价值。

新闻标题：{title}
新闻来源：{source}
发布时间：{time}
新闻内容：{content}

请回答以下问题（JSON 格式）：
{{
    "has_trading_value": true/false,  // 是否具有交易价值
    "relevance_score": 0.0-1.0,       // 相关性评分
    "ticker": "股票代码或null",         // 提取的股票代码（如 600519）
    "reason": "判断理由（简短，50字以内）"
}}

判断标准：
1. 具有交易价值的新闻类型：业绩预告/财报、重大合同、重组并购、股权变动、分红送转、重大利好/利空、监管政策变化
2. 无交易价值的新闻类型：例行公告、人事变动（非关键）、诉讼进展（非重大）、投资者关系活动、无明显实质内容的新闻

请只返回 JSON，不要其他内容。
"""


# =============================================================================
# 实时路由器
# =============================================================================

class RealtimeRouter:
    """实时决策路由器"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or ROUTER_CONFIG
        self.processed_count = 0
        self.filtered_count = 0
        self.analyzed_count = 0

    async def process_news(self, news: NewsItem) -> Optional[str]:
        """
        处理实时新闻（支持流式推送）

        Returns:
            event_id: 创建的事件ID，如果被过滤则返回 None
        """
        self.processed_count += 1
        broadcast = _get_broadcast_functions()

        logger.info(f"[路由器] 收到新闻 #{self.processed_count}: {news.title[:50]}...")

        # 广播：感知开始
        if broadcast.get('perception_start'):
            await broadcast['perception_start'](source=news.source)

        try:
            # 步骤1: 初筛过滤
            filter_result = await self._lightweight_filter(news)

            if not filter_result or not filter_result.get("has_trading_value"):
                self.filtered_count += 1
                reason = filter_result.get('reason', '无交易价值')
                logger.info(f"[路由器] 已过滤: {reason}")

                # 广播：事件被过滤
                if broadcast.get('event_filtered'):
                    await broadcast['event_filtered'](reason=reason)
                return None

            relevance = filter_result.get("relevance_score", 0)
            if relevance < self.config["min_relevance_score"]:
                self.filtered_count += 1
                reason = f"相关性不足 ({relevance:.2f})"
                logger.info(f"[路由器] {reason}: {news.title[:30]}...")

                # 广播：事件被过滤
                if broadcast.get('event_filtered'):
                    await broadcast['event_filtered'](reason=reason)
                return None

            logger.info(f"[路由器] ✅ 通过初筛 (相关性: {relevance:.2f})")

            # 步骤2: 提取股票代码
            ticker = filter_result.get("ticker") or news.ticker
            if not ticker:
                # 使用正则提取
                tickers = extract_tickers(news.title + " " + (news.content or ""))
                ticker = tickers[0] if tickers else None

            if not ticker:
                logger.warning(f"[路由器] 无法提取股票代码，跳过: {news.title[:30]}...")
                if broadcast.get('event_filtered'):
                    await broadcast['event_filtered'](reason="无法提取股票代码")
                return None

            # 广播：感知捕获
            if broadcast.get('perception_captured'):
                await broadcast['perception_captured'](
                    event_id=f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    ticker=ticker,
                    title=news.title,
                    url=news.url,
                    raw_data={"source": news.source, "content": news.content}
                )

            # 步骤3: 自动触发完整分析
            if self.config["auto_analyze"]:
                event_id = await self._trigger_analysis(news, ticker, filter_result, broadcast)
                self.analyzed_count += 1
                return event_id

            return None

        except Exception as e:
            logger.error(f"[路由器] 处理异常: {e}")
            return None

    async def _lightweight_filter(self, news: NewsItem) -> Optional[Dict[str, Any]]:
        """轻量级初筛"""
        try:
            from shared.llm.clients import ZhipuClient

            client = ZhipuClient()

            prompt = LIGHTWEIGHT_FILTER_PROMPT.format(
                title=news.title,
                source=news.source,
                time=news.publish_time,
                content=news.content or news.title
            )

            # 调用智谱快速判断
            response = await client.call(
                prompt=prompt,
                temperature=0.1,  # 低温度，稳定输出
                max_tokens=200
            )

            if not response:
                return None

            # 解析 JSON 响应
            import json
            import re

            # 提取 JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                logger.warning(f"[路由器] 无法解析初筛响应: {response[:100]}")
                return None

            result = json.loads(json_match.group())

            return {
                "has_trading_value": result.get("has_trading_value", False),
                "relevance_score": result.get("relevance_score", 0.0),
                "ticker": result.get("ticker"),
                "reason": result.get("reason", "")
            }

        except Exception as e:
            logger.error(f"[路由器] 初筛异常: {e}")
            # 发生异常时，保守策略：不过滤，继续分析
            return {
                "has_trading_value": True,
                "relevance_score": 0.7,
                "ticker": None,
                "reason": "初筛异常，默认通过"
            }

    async def _trigger_analysis(
        self,
        news: NewsItem,
        ticker: str,
        filter_result: Dict[str, Any],
        broadcast: Dict[str, Any]
    ) -> Optional[str]:
        """触发完整事件分析（支持流式推送）"""
        try:
            logger.info(f"[路由器] 🚀 触发完整分析: {ticker}")

            # 构建事件描述
            event_description = f"""
【实时新闻】{news.title}

来源：{news.source}
时间：{news.publish_time}
链接：{news.url}

内容：{news.content or news.title}
""".strip()

            # 生成临时事件ID用于广播
            temp_event_id = f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # 广播：分析开始
            if broadcast.get('analysis_start'):
                await broadcast['analysis_start'](event_id=temp_event_id, ticker=ticker)

            # 广播：AI思考过程
            if broadcast.get('ai_thinking'):
                await broadcast['ai_thinking'](event_id=temp_event_id, model="Kimi", step="清洗新闻内容...")
                await asyncio.sleep(0.3)
                await broadcast['ai_thinking'](event_id=temp_event_id, model="Tavily", step="搜索背景信息...")
                await asyncio.sleep(0.3)
                await broadcast['ai_thinking'](event_id=temp_event_id, model="GLM-4", step="逻辑推演中...")
                await asyncio.sleep(0.3)
                await broadcast['ai_thinking'](event_id=temp_event_id, model="MiniMax", step="生成决策包...")

            # 调用完整分析工作流
            result = await analyze_event(
                ticker=ticker,
                event_url=news.url,
                event_description=event_description,
                event_type="realtime_news"
            )

            if result and result.success:
                event_id = result.event_id
                logger.info(f"[路由器] ✅ 事件已创建: {event_id}")

                # 广播：决策完成
                if broadcast.get('decision_complete'):
                    # 模拟退出计划
                    exit_plan = {
                        "take_profit": "待计算",
                        "stop_loss": "待计算",
                        "expiration": "待计算"
                    }
                    reasoning = f"基于事件 {news.title}，AI矩阵已完成分析。"
                    await broadcast['decision_complete'](
                        event_id=temp_event_id,
                        ticker=ticker,
                        action="HOLD",
                        exit_plan=exit_plan,
                        reasoning=reasoning
                    )

                return event_id
            else:
                logger.error(f"[路由器] ❌ 分析失败")
                return None

        except Exception as e:
            logger.error(f"[路由器] 触发分析异常: {e}")
            return None

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return {
            "processed": self.processed_count,
            "filtered": self.filtered_count,
            "analyzed": self.analyzed_count,
            "passed_rate": f"{(self.analyzed_count / max(self.processed_count, 1) * 100):.1f}%"
        }


# =============================================================================
# 全局单例
# =============================================================================

_realtime_router: Optional[RealtimeRouter] = None


def get_realtime_router() -> RealtimeRouter:
    """获取全局路由器实例"""
    global _realtime_router
    if _realtime_router is None:
        _realtime_router = RealtimeRouter()
    return _realtime_router


# =============================================================================
# 连接 LiveMonitor 和 RealtimeRouter
# =============================================================================

async def on_live_news(news: NewsItem):
    """
    LiveMonitor 的回调函数
    将新闻路由到决策处理器
    """
    router = get_realtime_router()
    await router.process_news(news)


# =============================================================================
# API Endpoints (for FastAPI integration)
# =============================================================================

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/realtime", tags=["realtime"])


class RouterStats(BaseModel):
    """路由器统计"""
    processed: int
    filtered: int
    analyzed: int
    passed_rate: str


@router.get("/stats", response_model=RouterStats)
async def get_router_stats():
    """获取路由器统计信息"""
    rt_router = get_realtime_router()
    return rt_router.get_stats()


@router.post("/test_news")
async def test_news(title: str, content: str = "", source: str = "test"):
    """测试新闻处理（用于调试）"""
    news = NewsItem(
        title=title,
        url="test://local",
        publish_time=datetime.now().strftime("%H:%M:%S"),
        source=source,
        content=content
    )

    router = get_realtime_router()
    event_id = await router.process_news(news)

    return {
        "success": event_id is not None,
        "event_id": event_id,
        "stats": router.get_stats()
    }


@router.post("/manual_trigger")
async def manual_trigger(ticker: str, event_description: str):
    """手动触发分析（绕过初筛）"""
    try:
        result = await analyze_event(
            ticker=ticker,
            event_description=event_description,
            event_type="manual"
        )

        return {
            "success": result.success if result else False,
            "event_id": result.event_id if result else None,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
