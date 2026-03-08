"""
AI TradeBot - 信息可信度评分器

根据来源权威性、时效性、作者等因素评估信息可信度
"""
import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from shared.logging import get_logger

logger = get_logger(__name__)


class SourceType(Enum):
    """来源类型"""
    OFFICIAL = "official"      # 官方来源
    TIER1_MEDIA = "tier1"      # 一线媒体
    TIER2_MEDIA = "tier2"      # 二线媒体
    SOCIAL = "social"          # 社交媒体
    BLOG = "blog"              # 自媒体/博客
    UNKNOWN = "unknown"        # 未知


@dataclass
class SourceCredibility:
    """来源可信度配置"""
    name: str
    source_type: SourceType
    base_score: float          # 基础分数 (0-1)
    weight: float = 1.0        # 权重


@dataclass
class ScoredNews:
    """带可信度分数的新闻"""
    id: str
    title: str
    content: str
    source: str
    publish_time: datetime
    url: str
    
    # 评分维度
    source_score: float        # 来源分数 (0-1)
    freshness_score: float     # 时效分数 (0-1)
    consistency_score: float   # 一致性分数 (0-1)
    
    # 综合分数
    credibility_score: float   # 可信度总分 (0-1)
    confidence_level: str      # 置信等级: high/medium/low


class CredibilityScorer:
    """
    可信度评分器
    
    多维度评分体系:
    1. 来源权威性 (40%): 官方 > 一线媒体 > 二线媒体 > 社交媒体
    2. 时效性 (30%): 越新越高，超过48小时衰减
    3. 一致性 (30%): 与其他可信源的一致性
    """
    
    # 来源可信度配置
    SOURCE_REGISTRY: Dict[str, SourceCredibility] = {
        # 官方来源
        '证监会': SourceCredibility('证监会', SourceType.OFFICIAL, 1.0),
        '交易所': SourceCredibility('交易所', SourceType.OFFICIAL, 1.0),
        '上交所': SourceCredibility('上交所', SourceType.OFFICIAL, 1.0),
        '深交所': SourceCredibility('深交所', SourceType.OFFICIAL, 1.0),
        '北交所': SourceCredibility('北交所', SourceType.OFFICIAL, 1.0),
        '上市公司': SourceCredibility('上市公司', SourceType.OFFICIAL, 0.95),
        
        # 一线媒体
        '财联社': SourceCredibility('财联社', SourceType.TIER1_MEDIA, 0.9),
        '证券时报': SourceCredibility('证券时报', SourceType.TIER1_MEDIA, 0.9),
        '上海证券报': SourceCredibility('上海证券报', SourceType.TIER1_MEDIA, 0.9),
        '中国证券报': SourceCredibility('中国证券报', SourceType.TIER1_MEDIA, 0.9),
        '经济观察报': SourceCredibility('经济观察报', SourceType.TIER1_MEDIA, 0.85),
        '第一财经': SourceCredibility('第一财经', SourceType.TIER1_MEDIA, 0.85),
        '财新': SourceCredibility('财新', SourceType.TIER1_MEDIA, 0.9),
        
        # 二线媒体
        '新浪财经': SourceCredibility('新浪财经', SourceType.TIER2_MEDIA, 0.75),
        '东方财富': SourceCredibility('东方财富', SourceType.TIER2_MEDIA, 0.75),
        '同花顺': SourceCredibility('同花顺', SourceType.TIER2_MEDIA, 0.75),
        '腾讯财经': SourceCredibility('腾讯财经', SourceType.TIER2_MEDIA, 0.7),
        '网易财经': SourceCredibility('网易财经', SourceType.TIER2_MEDIA, 0.7),
        '搜狐财经': SourceCredibility('搜狐财经', SourceType.TIER2_MEDIA, 0.65),
        
        # 社交媒体
        '雪球': SourceCredibility('雪球', SourceType.SOCIAL, 0.5),
        '东方财富股吧': SourceCredibility('东方财富股吧', SourceType.SOCIAL, 0.4),
        '淘股吧': SourceCredibility('淘股吧', SourceType.SOCIAL, 0.35),
        
        # 自媒体
        '知乎': SourceCredibility('知乎', SourceType.BLOG, 0.3),
        '公众号': SourceCredibility('公众号', SourceType.BLOG, 0.25),
        '微博': SourceCredibility('微博', SourceType.BLOG, 0.2),
    }
    
    # 评分权重
    WEIGHTS = {
        'source': 0.40,
        'freshness': 0.30,
        'consistency': 0.30,
    }
    
    def __init__(
        self,
        freshness_decay_hours: int = 48,
        min_credibility_threshold: float = 0.3
    ):
        """
        初始化评分器
        
        Args:
            freshness_decay_hours: 时效性衰减时间（小时）
            min_credibility_threshold: 最低可信度阈值
        """
        self.freshness_decay = timedelta(hours=freshness_decay_hours)
        self.min_threshold = min_credibility_threshold
        
        logger.info(
            f"[可信度评分器] 初始化: 衰减时间={freshness_decay_hours}h, "
            f"阈值={min_credibility_threshold}"
        )
    
    def _get_source_score(self, source: str) -> float:
        """
        获取来源可信度分数
        
        Args:
            source: 来源名称
            
        Returns:
            分数 (0-1)
        """
        # 精确匹配
        if source in self.SOURCE_REGISTRY:
            return self.SOURCE_REGISTRY[source].base_score
        
        # 模糊匹配
        for name, config in self.SOURCE_REGISTRY.items():
            if name in source or source in name:
                return config.base_score
        
        # 默认未知来源
        return 0.3
    
    def _calculate_freshness_score(self, publish_time: datetime) -> float:
        """
        计算时效性分数
        
        Args:
            publish_time: 发布时间
            
        Returns:
            分数 (0-1)
        """
        now = datetime.now()
        age = now - publish_time
        
        if age < timedelta(hours=1):
            return 1.0
        elif age < timedelta(hours=6):
            return 0.9
        elif age < timedelta(hours=24):
            return 0.8
        elif age < timedelta(hours=48):
            return 0.6
        elif age < self.freshness_decay:
            return 0.4
        else:
            # 指数衰减
            days = age.days
            return max(0.1, 0.3 ** (days / 7))  # 一周后衰减到0.1以下
    
    def _calculate_consistency_score(
        self,
        news_item,
        reference_items: Optional[List] = None
    ) -> float:
        """
        计算一致性分数（与其他可信源的交叉验证）
        
        Args:
            news_item: 当前新闻
            reference_items: 参考新闻列表
            
        Returns:
            分数 (0-1)
        """
        if not reference_items:
            # 无参考时，给中等分数
            return 0.5
        
        # 简单实现：检查关键词重叠
        news_words = set(self._extract_keywords(news_item.title + news_item.content))
        
        match_scores = []
        for ref in reference_items:
            ref_words = set(self._extract_keywords(ref.title + ref.content))
            if not ref_words:
                continue
            
            overlap = len(news_words & ref_words)
            union = len(news_words | ref_words)
            
            if union > 0:
                jaccard = overlap / union
                # 加权：可信源的权重更高
                ref_score = self._get_source_score(ref.source)
                match_scores.append(jaccard * ref_score)
        
        if not match_scores:
            return 0.5
        
        # 取加权平均
        avg_score = sum(match_scores) / len(match_scores)
        return min(1.0, avg_score * 2)  # 放大到0-1范围
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简化版）"""
        import re
        # 提取中文字符
        chinese = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        # 提取英文单词
        english = re.findall(r'[a-zA-Z]{3,}', text)
        return chinese + english
    
    def _determine_confidence_level(self, score: float) -> str:
        """确定置信等级"""
        if score >= 0.8:
            return "high"
        elif score >= 0.5:
            return "medium"
        else:
            return "low"
    
    async def score(
        self,
        news_item,
        reference_items: Optional[List] = None
    ) -> ScoredNews:
        """
        对单条新闻进行可信度评分
        
        Args:
            news_item: 新闻项
            reference_items: 参考新闻列表（用于交叉验证）
            
        Returns:
            ScoredNews 带分数的新闻
        """
        try:
            # 计算各维度分数
            source_score = self._get_source_score(news_item.source)
            freshness_score = self._calculate_freshness_score(news_item.publish_time)
            consistency_score = self._calculate_consistency_score(news_item, reference_items)
            
            # 计算综合分数
            credibility_score = (
                source_score * self.WEIGHTS['source'] +
                freshness_score * self.WEIGHTS['freshness'] +
                consistency_score * self.WEIGHTS['consistency']
            )
            
            confidence_level = self._determine_confidence_level(credibility_score)
            
            logger.debug(
                f"[评分] {news_item.title[:30]}... "
                f"来源={source_score:.2f}, 时效={freshness_score:.2f}, "
                f"一致={consistency_score:.2f}, 综合={credibility_score:.2f}"
            )
            
            return ScoredNews(
                id=news_item.id,
                title=news_item.title,
                content=news_item.content,
                source=news_item.source,
                publish_time=news_item.publish_time,
                url=getattr(news_item, 'url', ''),
                source_score=source_score,
                freshness_score=freshness_score,
                consistency_score=consistency_score,
                credibility_score=credibility_score,
                confidence_level=confidence_level
            )
            
        except Exception as e:
            logger.error(f"[评分] 评分失败: {e}")
            # 返回低可信度的默认结果
            return ScoredNews(
                id=getattr(news_item, 'id', ''),
                title=getattr(news_item, 'title', ''),
                content=getattr(news_item, 'content', ''),
                source=getattr(news_item, 'source', 'unknown'),
                publish_time=getattr(news_item, 'publish_time', datetime.now()),
                url=getattr(news_item, 'url', ''),
                source_score=0.3,
                freshness_score=0.5,
                consistency_score=0.5,
                credibility_score=0.4,
                confidence_level="low"
            )
    
    async def batch_score(
        self,
        news_items: List,
        reference_items: Optional[List] = None
    ) -> List[ScoredNews]:
        """
        批量评分
        
        Args:
            news_items: 新闻列表
            reference_items: 参考新闻列表
            
        Returns:
            带分数的新闻列表
        """
        if not news_items:
            return []
        
        logger.info(f"[可信度评分器] 批量评分 {len(news_items)} 条")
        
        # 并发评分
        tasks = [self.score(item, reference_items) for item in news_items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常
        scored_items = []
        for result in results:
            if isinstance(result, ScoredNews):
                scored_items.append(result)
            else:
                logger.error(f"[评分] 异常: {result}")
        
        # 按可信度排序
        scored_items.sort(key=lambda x: x.credibility_score, reverse=True)
        
        logger.info(
            f"[可信度评分器] 完成: "
            f"high={sum(1 for x in scored_items if x.confidence_level=='high')}, "
            f"medium={sum(1 for x in scored_items if x.confidence_level=='medium')}, "
            f"low={sum(1 for x in scored_items if x.confidence_level=='low')}"
        )
        
        return scored_items
    
    def filter_by_credibility(
        self,
        scored_items: List[ScoredNews],
        min_score: Optional[float] = None
    ) -> List[ScoredNews]:
        """
        按可信度过滤
        
        Args:
            scored_items: 已评分的新闻列表
            min_score: 最低分数（默认使用初始化时的阈值）
            
        Returns:
            过滤后的列表
        """
        threshold = min_score if min_score is not None else self.min_threshold
        filtered = [item for item in scored_items if item.credibility_score >= threshold]
        
        logger.info(f"[可信度评分器] 过滤: {len(scored_items)} → {len(filtered)} (阈值={threshold})")
        
        return filtered
