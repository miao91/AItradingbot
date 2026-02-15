"""
AI TradeBot - AI 驱动的新闻分类器

三级过滤机制：
1. 快速分类：使用 GLM-4-Flash 进行价值打分（0-10分）
2. 深度筛选：仅对 >7 分的新闻启动 Tavily 搜索
3. 估值分析：对高分新闻进行估值重塑分析

评分标准：
- 估值重塑（Weight: 50%）：底层协议更改、融资、监管、供需结构改变
- 持续性（Weight: 30%）：短期情绪 vs 长期反转
- 资产相关性（Weight: 20%）：主流币、高热度板块
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from shared.llm.clients import ZhipuClient, TokenCounter
from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 评分枚举
# =============================================================================

class ValuationImpactLevel(Enum):
    """估值影响级别"""
    NONE = "无影响"
    LOW = "低度影响"
    MEDIUM = "中度影响"
    HIGH = "高度影响"
    EXTREME = "极度影响"


class DurationEstimate(Enum):
    """影响时长预估"""
    HOURS_24 = "24h"  # 短期情绪
    HOURS_72 = "72h"  # 中期影响
    DAYS_14 = "14 days"  # 长期影响
    LONG_TERM = "Long-term"  # 永久性改变


class NewsCategory(Enum):
    """新闻分类"""
    IGNORE = "忽略"  # < 4分：噪音
    TRACKING = "跟踪"  # 4-6分：关注
    ANALYSIS = "分析"  # 7-8分：需分析
    CRITICAL = "关键"  # 9-10分：立即处理


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class ClassificationScore:
    """分类评分"""
    total_score: float  # 总分 0-10

    # 细分得分
    valuation_reshaping: float = 0.0  # 估值重塑得分 0-10
    sustainability: float = 0.0  # 持续性得分 0-10
    asset_relevance: float = 0.0  # 资产相关性得分 0-10

    # 分类结果
    category: NewsCategory = NewsCategory.IGNORE
    valuation_level: ValuationImpactLevel = ValuationImpactLevel.NONE
    duration_estimate: DurationEstimate = DurationEstimate.HOURS_24

    # 推理
    reasoning: str = ""

    # 元数据
    processing_time_ms: float = 0.0
    model_used: str = "glm-4-flash"


@dataclass
class NewsItem:
    """新闻项"""
    title: str
    content: str
    source: str
    ticker: Optional[str] = None
    publish_time: Optional[str] = None
    url: Optional[str] = None


# =============================================================================
# 分类器
# =============================================================================

class NewsClassifier:
    """
    AI 驱动的新闻分类器

    使用 GLM-4-Flash 进行快速分类和评分
    """

    # 评分权重
    WEIGHT_VALUATION = 0.50  # 估值重塑
    WEIGHT_SUSTAINABILITY = 0.30  # 持续性
    WEIGHT_RELEVANCE = 0.20  # 资产相关性

    # 评分阈值
    THRESHOLD_ANALYSIS = 7.0  # >=7分启动深度分析
    THRESHOLD_TRACKING = 4.0  # >=4分纳入跟踪

    def __init__(self):
        """初始化分类器"""
        # 使用 GLM-4-Flash（快速、便宜）
        self.llm = ZhipuClient(
            model="glm-4-flash",  # 使用 Flash 版本
            timeout=30
        )

    async def classify(self, news: NewsItem) -> ClassificationScore:
        """
        对新闻进行分类和评分

        Args:
            news: 新闻项

        Returns:
            ClassificationScore 分类评分
        """
        start_time = time.time()

        logger.info(f"[分类器] 开始分类: {news.title[:50]}...")

        # 构建分类提示词
        prompt = self._build_classification_prompt(news)

        # 调用 LLM
        response = await self.llm.call(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.1,  # 低温度，稳定输出
            max_tokens=500,  # 短输出
            compress_if_needed=False,  # 新闻很短，不需要压缩
        )

        duration_ms = (time.time() - start_time) * 1000

        if not response.success:
            logger.error(f"[分类器] LLM 调用失败: {response.error_message}")
            # 返回默认低分
            return ClassificationScore(
                total_score=0.0,
                category=NewsCategory.IGNORE,
                reasoning=f"LLM 调用失败: {response.error_message}",
                processing_time_ms=duration_ms,
            )

        # 解析响应
        score = self._parse_response(response.content, duration_ms)

        logger.info(
            f"[分类器] 分类完成: 总分={score.total_score:.1f}, "
            f"类别={score.category.value}, 耗时={duration_ms:.0f}ms"
        )

        return score

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的金融新闻分类助手。你的任务是对加密货币/股票新闻进行快速分类和评分。

请严格按照 JSON 格式返回评分结果，不要添加任何其他内容。

评分标准（0-10分）：
1. 估值重塑（50%权重）：
   - 10分：底层协议更改、重大融资（>$100M）、监管法案通过、供需结构改变（如减半）
   - 7-9分：重要合作伙伴、技术升级、中等规模融资
   - 4-6分：常规产品更新、一般性公告
   - 0-3分：社交媒体讨论、博主观点、市场噪音

2. 持续性（30%权重）：
   - 10分：基本面长期反转、永久性政策改变
   - 7-9分：中期趋势（数周至数月）
   - 4-6分：短期事件（数天）
   - 0-3分：瞬间拉升出货、纯情绪炒作

3. 资产相关性（20%权重）：
   - 10分：直接作用于 BTC/ETH 等主流币
   - 7-9分：作用于 Top 20 高市值币种
   - 4-6分：作用于中小市值币种
   - 0-3分：无明确资产或极小市值币

JSON 返回格式：
{
    "valuation_reshaping": 分数(0-10),
    "sustainability": 分数(0-10),
    "asset_relevance": 分数(0-10),
    "total_score": 加权总分(0-10),
    "category": "忽略/跟踪/分析/关键",
    "valuation_level": "无影响/低度/中度/高度/极度",
    "duration_estimate": "24h/72h/14 days/Long-term",
    "reasoning": "简短理由（50字内）"
}"""

    def _build_classification_prompt(self, news: NewsItem) -> str:
        """构建分类提示词"""
        prompt = f"""请对以下新闻进行分类和评分：

标题：{news.title}
来源：{news.source}
发布时间：{news.publish_time or '未知'}
"""

        if news.content:
            prompt += f"\n内容：{news.content[:500]}"

        if news.ticker:
            prompt += f"\n相关资产：{news.ticker}"

        if news.url:
            prompt += f"\n链接：{news.url}"

        prompt += "\n\n请返回 JSON 格式的评分结果。"

        return prompt

    def _parse_response(self, content: str, duration_ms: float) -> ClassificationScore:
        """解析 LLM 响应"""
        try:
            # 提取 JSON
            import re
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)

            if not json_match:
                logger.warning(f"[分类器] 未找到 JSON，使用默认评分")
                return self._default_score(duration_ms)

            data = json.loads(json_match.group())

            # 计算加权总分
            total_score = (
                data.get("valuation_reshaping", 0) * self.WEIGHT_VALUATION +
                data.get("sustainability", 0) * self.WEIGHT_SUSTAINABILITY +
                data.get("asset_relevance", 0) * self.WEIGHT_RELEVANCE
            )

            # 映射类别
            total_score = min(total_score, 10.0)  # 限制在 10 分
            category = self._score_to_category(total_score)
            valuation_level = self._string_to_valuation_level(data.get("valuation_level", "无影响"))
            duration = self._string_to_duration(data.get("duration_estimate", "24h"))

            return ClassificationScore(
                total_score=total_score,
                valuation_reshaping=data.get("valuation_reshaping", 0),
                sustainability=data.get("sustainability", 0),
                asset_relevance=data.get("asset_relevance", 0),
                category=category,
                valuation_level=valuation_level,
                duration_estimate=duration,
                reasoning=data.get("reasoning", ""),
                processing_time_ms=duration_ms,
            )

        except json.JSONDecodeError as e:
            logger.error(f"[分类器] JSON 解析失败: {e}")
            return self._default_score(duration_ms)
        except Exception as e:
            logger.error(f"[分类器] 响应解析异常: {e}")
            return self._default_score(duration_ms)

    def _score_to_category(self, score: float) -> NewsCategory:
        """分数转类别"""
        if score >= 9.0:
            return NewsCategory.CRITICAL
        elif score >= self.THRESHOLD_ANALYSIS:
            return NewsCategory.ANALYSIS
        elif score >= self.THRESHOLD_TRACKING:
            return NewsCategory.TRACKING
        else:
            return NewsCategory.IGNORE

    def _string_to_valuation_level(self, level: str) -> ValuationImpactLevel:
        """字符串转估值级别"""
        mapping = {
            "无影响": ValuationImpactLevel.NONE,
            "低度影响": ValuationImpactLevel.LOW,
            "中度影响": ValuationImpactLevel.MEDIUM,
            "高度影响": ValuationImpactLevel.HIGH,
            "极度影响": ValuationImpactLevel.EXTREME,
        }
        return mapping.get(level, ValuationImpactLevel.NONE)

    def _string_to_duration(self, duration: str) -> DurationEstimate:
        """字符串转时长"""
        mapping = {
            "24h": DurationEstimate.HOURS_24,
            "72h": DurationEstimate.HOURS_72,
            "14 days": DurationEstimate.DAYS_14,
            "Long-term": DurationEstimate.LONG_TERM,
        }
        return mapping.get(duration, DurationEstimate.HOURS_24)

    def _default_score(self, duration_ms: float) -> ClassificationScore:
        """默认评分（解析失败时）"""
        return ClassificationScore(
            total_score=0.0,
            category=NewsCategory.IGNORE,
            reasoning="解析失败，默认忽略",
            processing_time_ms=duration_ms,
        )


# =============================================================================
# 批处理器
# =============================================================================

class BatchNewsProcessor:
    """
    批量新闻处理器

    每 30 秒聚合一批消息，统一交给 AI 批处理分类
    """

    BATCH_INTERVAL = 30  # 批处理间隔（秒）
    MAX_BATCH_SIZE = 20  # 最大批处理大小

    def __init__(self, classifier: NewsClassifier):
        """初始化批处理器"""
        self.classifier = classifier
        self.pending_news: List[NewsItem] = []
        self.processing = False
        self.last_process_time = time.time()

    async def add_news(self, news: NewsItem) -> Optional[ClassificationScore]:
        """
        添加新闻到批处理队列

        如果达到批处理条件（时间到或队列满），触发批处理

        Args:
            news: 新闻项

        Returns:
            ClassificationScore 如果立即处理，否则返回 None
        """
        self.pending_news.append(news)

        # 检查是否需要立即处理
        should_process = (
            len(self.pending_news) >= self.MAX_BATCH_SIZE or
            (time.time() - self.last_process_time) >= self.BATCH_INTERVAL
        )

        if should_process:
            return await self._process_batch()

        return None  # 尚未处理

    async def _process_batch(self) -> Optional[ClassificationScore]:
        """
        处理一批新闻

        Returns:
            最后一条新闻的评分
        """
        if self.processing:
            return None

        self.processing = True
        batch = self.pending_news.copy()
        self.pending_news = []
        self.last_process_time = time.time()

        logger.info(f"[批处理器] 开始处理 {len(batch)} 条新闻...")

        # 并发处理所有新闻
        tasks = [self.classifier.classify(news) for news in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        stats = {
            NewsCategory.IGNORE: 0,
            NewsCategory.TRACKING: 0,
            NewsCategory.ANALYSIS: 0,
            NewsCategory.CRITICAL: 0,
        }

        for result in results:
            if isinstance(result, ClassificationScore):
                stats[result.category] += 1
            elif isinstance(result, Exception):
                logger.error(f"[批处理器] 处理异常: {result}")

        logger.info(
            f"[批处理器] 批处理完成: "
            f"忽略={stats[NewsCategory.IGNORE]}, "
            f"跟踪={stats[NewsCategory.TRACKING]}, "
            f"分析={stats[NewsCategory.ANALYSIS]}, "
            f"关键={stats[NewsCategory.CRITICAL]}"
        )

        self.processing = False

        # 返回最后一条的结果（如果有）
        if results:
            last_result = results[-1]
            return last_result if isinstance(last_result, ClassificationScore) else None

        return None

    async def flush(self):
        """强制刷新所有待处理新闻"""
        if self.pending_news:
            return await self._process_batch()
        return None


# =============================================================================
# 全局单例
# =============================================================================

_news_classifier: Optional[NewsClassifier] = None
_batch_processor: Optional[BatchNewsProcessor] = None


def get_news_classifier() -> NewsClassifier:
    """获取全局分类器实例"""
    global _news_classifier
    if _news_classifier is None:
        _news_classifier = NewsClassifier()
    return _news_classifier


def get_batch_processor() -> BatchNewsProcessor:
    """获取全局批处理器实例"""
    global _batch_processor
    if _batch_processor is None:
        classifier = get_news_classifier()
        _batch_processor = BatchNewsProcessor(classifier)
    return _batch_processor


# =============================================================================
# 便捷函数
# =============================================================================

async def classify_news(
    title: str,
    content: str = "",
    source: str = "",
    ticker: Optional[str] = None,
) -> ClassificationScore:
    """
    对单条新闻进行分类

    Args:
        title: 新闻标题
        content: 新闻内容
        source: 新闻来源
        ticker: 相关资产

    Returns:
        ClassificationScore 分类评分
    """
    news = NewsItem(
        title=title,
        content=content,
        source=source,
        ticker=ticker,
        publish_time=datetime.now().strftime("%H:%M:%S"),
    )

    classifier = get_news_classifier()
    return await classifier.classify(news)
