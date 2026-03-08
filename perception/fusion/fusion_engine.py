"""
AI TradeBot - 信息聚合引擎

整合去重、评分、图谱构建的完整流程
"""
import asyncio
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from shared.logging import get_logger

from perception.fusion.deduplicator import NewsDeduplicator, NewsItem, DuplicateGroup
from perception.fusion.credibility_scorer import CredibilityScorer, ScoredNews
from perception.fusion.event_graph import EventGraph, EventNode

logger = get_logger(__name__)


@dataclass
class AggregatedNews:
    """聚合后的新闻"""
    # 基础信息
    id: str
    title: str
    content: str
    source: str
    publish_time: datetime
    url: str
    
    # 聚合信息
    duplicate_sources: List[str] = field(default_factory=list)  # 重复来源列表
    duplicate_count: int = 0  # 重复次数（多源报道）
    
    # 可信度
    credibility_score: float = 0.5
    confidence_level: str = "medium"
    
    # 关联信息
    related_events: List[Dict[str, Any]] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    
    # 元数据
    aggregation_time: datetime = field(default_factory=datetime.now)


class FusionEngine:
    """
    信息聚合引擎
    
    完整流程：
    1. 去重 -> 合并重复报道
    2. 评分 -> 评估可信度
    3. 建图 -> 构建事件关联
    4. 输出 -> 生成聚合结果
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.85,
        credibility_threshold: float = 0.3,
        enable_graph: bool = True
    ):
        """
        初始化聚合引擎
        
        Args:
            similarity_threshold: 相似度去重阈值
            credibility_threshold: 可信度过滤阈值
            enable_graph: 是否启用事件图谱
        """
        self.deduplicator = NewsDeduplicator(similarity_threshold=similarity_threshold)
        self.scorer = CredibilityScorer(min_credibility_threshold=credibility_threshold)
        self.enable_graph = enable_graph
        
        if enable_graph:
            self.event_graph = EventGraph()
        else:
            self.event_graph = None
        
        logger.info(
            f"[聚合引擎] 初始化: 去重阈值={similarity_threshold}, "
            f"可信度阈值={credibility_threshold}, 图谱={enable_graph}"
        )
    
    async def process(
        self,
        raw_news: List[NewsItem],
        build_relations: bool = True
    ) -> List[AggregatedNews]:
        """
        处理原始新闻列表
        
        Args:
            raw_news: 原始新闻列表
            build_relations: 是否构建关系图谱
            
        Returns:
            聚合后的新闻列表
        """
        if not raw_news:
            logger.warning("[聚合引擎] 输入为空")
            return []
        
        logger.info(f"[聚合引擎] 开始处理 {len(raw_news)} 条新闻")
        
        # Step 1: 去重
        duplicate_groups = await self.deduplicator.deduplicate(raw_news)
        logger.info(f"[聚合引擎] 去重完成: {len(duplicate_groups)} 组")
        
        # Step 2: 提取代表新闻进行评分
        canonical_items = [group.canonical_item for group in duplicate_groups]
        scored_news = await self.scorer.batch_score(canonical_items)
        
        # 建立id到评分的映射
        score_map = {s.id: s for s in scored_news}
        
        # Step 3: 构建事件图谱（可选）
        if self.enable_graph and build_relations and self.event_graph:
            self.event_graph.clear()
            
            # 添加节点
            for news in canonical_items:
                await self.event_graph.add_event(
                    event_id=news.id,
                    title=news.title,
                    content=news.content,
                    timestamp=news.publish_time
                )
            
            # 构建关系
            await self.event_graph.build_relations()
            logger.info("[聚合引擎] 事件图谱构建完成")
        
        # Step 4: 组装聚合结果
        aggregated = []
        for group in duplicate_groups:
            canonical = group.canonical_item
            scored = score_map.get(canonical.id)
            
            if not scored:
                continue
            
            # 构建聚合对象
            agg = AggregatedNews(
                id=canonical.id,
                title=canonical.title,
                content=canonical.content,
                source=canonical.source,
                publish_time=canonical.publish_time,
                url=canonical.url,
                duplicate_sources=[d.source for d in group.duplicates],
                duplicate_count=len(group.duplicates),
                credibility_score=scored.credibility_score,
                confidence_level=scored.confidence_level
            )
            
            # 添加图谱信息
            if self.enable_graph and self.event_graph:
                node = self.event_graph.nodes.get(canonical.id)
                if node:
                    agg.entities = list(node.entities)
                    
                    # 获取相关事件
                    related = self.event_graph.get_related_events(canonical.id, min_weight=0.4)
                    agg.related_events = [
                        {
                            'id': r.id,
                            'title': r.title,
                            'weight': w,
                            'source': r.source
                        }
                        for r, w in related[:5]  # 最多5个相关
                    ]
            
            aggregated.append(agg)
        
        # 按可信度排序
        aggregated.sort(key=lambda x: x.credibility_score, reverse=True)
        
        logger.info(
            f"[聚合引擎] 处理完成: {len(raw_news)} 条 → {len(aggregated)} 条, "
            f"高可信度={sum(1 for x in aggregated if x.confidence_level=='high')}"
        )
        
        return aggregated
    
    async def process_stream(
        self,
        news_stream,
        batch_size: int = 10,
        max_wait_seconds: float = 5.0
    ):
        """
        流式处理新闻
        
        Args:
            news_stream: 异步新闻生成器
            batch_size: 批处理大小
            max_wait_seconds: 最大等待时间
            
        Yields:
            聚合后的新闻
        """
        batch = []
        last_process_time = asyncio.get_event_loop().time()
        
        async for news in news_stream:
            batch.append(news)
            
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - last_process_time
            
            # 触发条件：批满或超时
            if len(batch) >= batch_size or time_since_last >= max_wait_seconds:
                if batch:
                    results = await self.process(batch)
                    for result in results:
                        yield result
                    
                    batch = []
                    last_process_time = current_time
        
        # 处理剩余
        if batch:
            results = await self.process(batch)
            for result in results:
                yield result
    
    def filter_high_credibility(
        self,
        aggregated: List[AggregatedNews],
        min_score: Optional[float] = None
    ) -> List[AggregatedNews]:
        """
        过滤高可信度新闻
        
        Args:
            aggregated: 聚合新闻列表
            min_score: 最低分数
            
        Returns:
            过滤后的列表
        """
        threshold = min_score if min_score is not None else self.scorer.min_threshold
        
        filtered = [
            news for news in aggregated
            if news.credibility_score >= threshold
        ]
        
        logger.info(f"[聚合引擎] 可信度过滤: {len(aggregated)} → {len(filtered)}")
        
        return filtered
    
    def get_hot_topics(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        获取热点主题
        
        Args:
            top_n: 前N个
            
        Returns:
            热点主题列表
        """
        if not self.event_graph:
            return []
        
        topics = self.event_graph.get_hot_topics(top_n)
        
        return [
            {
                'topic': topic,
                'mention_count': count,
                'related_events': list(self.event_graph.entity_index.get(topic, set()))[:5]
            }
            for topic, count in topics
        ]
    
    def get_event_timeline(
        self,
        entity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取事件时间线
        
        Args:
            entity: 可选的实体过滤
            
        Returns:
            时间线数据
        """
        if not self.event_graph:
            return []
        
        timeline = self.event_graph.get_timeline()
        
        if entity:
            timeline = [n for n in timeline if entity in n.entities]
        
        return [
            {
                'id': node.id,
                'title': node.title,
                'timestamp': node.timestamp.isoformat(),
                'entities': list(node.entities),
                'sentiment': node.sentiment
            }
            for node in timeline
        ]
    
    async def add_single_news(
        self,
        news: NewsItem,
        check_duplicate: bool = True
    ) -> Optional[AggregatedNews]:
        """
        添加单条新闻（增量处理）
        
        Args:
            news: 新闻项
            check_duplicate: 是否检查重复
            
        Returns:
            聚合结果（如果是重复则返回None）
        """
        # 检查重复
        if check_duplicate and self.event_graph:
            existing_ids = list(self.event_graph.nodes.keys())
            existing_items = [
                NewsItem(
                    id=n.id,
                    title=n.title,
                    content=n.content,
                    source="existing",
                    publish_time=n.timestamp,
                    url=""
                )
                for n in self.event_graph.nodes.values()
            ]
            
            is_dup, sim = await self.deduplicator.is_duplicate(news, existing_items)
            if is_dup:
                logger.info(f"[聚合引擎] 重复新闻，跳过: {news.title[:30]}...")
                return None
        
        # 处理单条
        results = await self.process([news], build_relations=False)
        
        if results:
            # 添加到图谱
            if self.event_graph:
                await self.event_graph.add_event(
                    event_id=news.id,
                    title=news.title,
                    content=news.content,
                    timestamp=news.publish_time
                )
            
            return results[0]
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取引擎统计信息
        
        Returns:
            统计信息
        """
        stats = {
            'deduplicator_threshold': self.deduplicator.similarity_threshold,
            'credibility_threshold': self.scorer.min_threshold,
            'graph_enabled': self.enable_graph,
        }
        
        if self.event_graph:
            stats['graph_nodes'] = len(self.event_graph.nodes)
            stats['graph_edges'] = sum(len(edges) for edges in self.event_graph.edges.values()) // 2
            stats['hot_topics'] = self.get_hot_topics(3)
        
        return stats
