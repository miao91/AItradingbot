"""
AI TradeBot - 事件关联图谱

基于共现实体构建事件之间的关联关系
"""
import asyncio
import re
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict

from shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EventNode:
    """事件节点"""
    id: str
    title: str
    content: str
    timestamp: datetime
    entities: Set[str] = field(default_factory=set)  # 提取的实体
    keywords: Set[str] = field(default_factory=set)  # 关键词
    sentiment: float = 0.0  # 情感分数
    importance: float = 0.5  # 重要性


@dataclass
class EventEdge:
    """事件边（关联）"""
    source_id: str
    target_id: str
    weight: float  # 关联强度 (0-1)
    relation_type: str  # 关联类型: entity_overlap, keyword_overlap, temporal, causal
    shared_entities: Set[str] = field(default_factory=set)


class EventGraph:
    """
    事件关联图谱
    
    功能：
    1. 提取事件中的实体（公司、产品、人物）
    2. 基于实体共现构建关联
    3. 识别事件链和时间线
    4. 发现热点主题
    """
    
    def __init__(
        self,
        entity_overlap_threshold: float = 0.3,
        time_proximity_hours: int = 72,
        max_edges_per_node: int = 10
    ):
        """
        初始化图谱
        
        Args:
            entity_overlap_threshold: 实体重叠阈值
            time_proximity_hours: 时间接近窗口（小时）
            max_edges_per_node: 每个节点最大边数
        """
        self.entity_overlap_threshold = entity_overlap_threshold
        self.time_proximity = timedelta(hours=time_proximity_hours)
        self.max_edges = max_edges_per_node
        
        # 图谱存储
        self.nodes: Dict[str, EventNode] = {}
        self.edges: Dict[str, List[EventEdge]] = defaultdict(list)
        
        # 实体索引（倒排）
        self.entity_index: Dict[str, Set[str]] = defaultdict(set)
        
        # 预定义实体词典
        self._load_entity_dict()
        
        logger.info(
            f"[事件图谱] 初始化: 实体阈值={entity_overlap_threshold}, "
            f"时间窗口={time_proximity_hours}h"
        )
    
    def _load_entity_dict(self):
        """加载实体词典"""
        # 常见公司名前缀
        self.company_prefixes = ['股份', '科技', '集团', '控股', '生物', '医药', '智能', '能源', '银行', '证券']
        
        # 常见人名后缀（用于识别人物）
        self.person_indicators = ['董事长', '总经理', 'CEO', '总裁', '创始人', '实控人']
        
        # 行业关键词
        self.industry_keywords = {
            '新能源', '半导体', '人工智能', '医药', '芯片', '光伏', '锂电', '电动车',
            '5G', '云计算', '大数据', '区块链', '元宇宙', '机器人', '储能'
        }
    
    def _extract_entities(self, text: str) -> Set[str]:
        """
        提取实体（简化版NER）
        
        Args:
            text: 输入文本
            
        Returns:
            实体集合
        """
        entities = set()
        
        # 提取股票代码模式
        stock_codes = re.findall(r'\d{6}\.[A-Z]{2}', text)
        entities.update(stock_codes)
        
        # 提取公司名称模式（XX股份、XX科技等）
        for prefix in self.company_prefixes:
            pattern = f'([\u4e00-\u9fa5]{{2,6}}{prefix})'
            matches = re.findall(pattern, text)
            entities.update(matches)
        
        # 提取人物（XX董事长、XXCEO等）
        for indicator in self.person_indicators:
            pattern = f'([\u4e00-\u9fa5]{{2,4}}){indicator}'
            matches = re.findall(pattern, text)
            entities.update([m + indicator for m in matches])
        
        # 提取行业关键词
        for keyword in self.industry_keywords:
            if keyword in text:
                entities.add(keyword)
        
        return entities
    
    def _extract_keywords(self, text: str) -> Set[str]:
        """
        提取关键词
        
        Args:
            text: 输入文本
            
        Returns:
            关键词集合
        """
        # 基于词频的关键词提取（简化版）
        import jieba
        
        words = jieba.lcut(text)
        
        # 过滤停用词和短词
        stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '我们'}
        keywords = {w for w in words if len(w) >= 2 and w not in stopwords}
        
        return keywords
    
    def _calculate_entity_overlap(
        self,
        entities1: Set[str],
        entities2: Set[str]
    ) -> Tuple[float, Set[str]]:
        """
        计算实体重叠度
        
        Args:
            entities1: 实体集合1
            entities2: 实体集合2
            
        Returns:
            (重叠度, 共享实体)
        """
        if not entities1 or not entities2:
            return 0.0, set()
        
        shared = entities1 & entities2
        
        # Jaccard相似度
        union = entities1 | entities2
        overlap = len(shared) / len(union) if union else 0.0
        
        return overlap, shared
    
    def _calculate_keyword_overlap(
        self,
        keywords1: Set[str],
        keywords2: Set[str]
    ) -> float:
        """计算关键词重叠度"""
        if not keywords1 or not keywords2:
            return 0.0
        
        shared = keywords1 & keywords2
        union = keywords1 | keywords2
        
        return len(shared) / len(union) if union else 0.0
    
    async def add_event(self, event_id: str, title: str, content: str, timestamp: datetime) -> EventNode:
        """
        添加事件到图谱
        
        Args:
            event_id: 事件ID
            title: 标题
            content: 内容
            timestamp: 时间戳
            
        Returns:
            创建的事件节点
        """
        full_text = f"{title} {content}"
        
        # 提取实体和关键词
        entities = self._extract_entities(full_text)
        keywords = self._extract_keywords(full_text)
        
        # 创建节点
        node = EventNode(
            id=event_id,
            title=title,
            content=content,
            timestamp=timestamp,
            entities=entities,
            keywords=keywords,
            sentiment=0.0,  # 可由外部设置
            importance=0.5
        )
        
        self.nodes[event_id] = node
        
        # 更新实体索引
        for entity in entities:
            self.entity_index[entity].add(event_id)
        
        logger.debug(f"[事件图谱] 添加节点: {event_id}, 实体={len(entities)}, 关键词={len(keywords)}")
        
        return node
    
    async def build_relations(self) -> List[EventEdge]:
        """
        构建事件间的关系
        
        Returns:
            创建的边列表
        """
        edges = []
        
        event_ids = list(self.nodes.keys())
        
        for i, id1 in enumerate(event_ids):
            node1 = self.nodes[id1]
            
            for id2 in event_ids[i+1:]:
                node2 = self.nodes[id2]
                
                # 检查时间接近度
                time_diff = abs((node1.timestamp - node2.timestamp).total_seconds())
                if time_diff > self.time_proximity.total_seconds():
                    continue
                
                # 计算实体重叠
                entity_overlap, shared_entities = self._calculate_entity_overlap(
                    node1.entities, node2.entities
                )
                
                # 计算关键词重叠
                keyword_overlap = self._calculate_keyword_overlap(
                    node1.keywords, node2.keywords
                )
                
                # 综合权重
                weight = max(entity_overlap, keyword_overlap * 0.5)
                
                if weight >= self.entity_overlap_threshold:
                    # 确定关系类型
                    if entity_overlap > keyword_overlap:
                        relation_type = "entity_overlap"
                    elif time_diff < timedelta(hours=24).total_seconds():
                        relation_type = "temporal"
                    else:
                        relation_type = "keyword_overlap"
                    
                    edge = EventEdge(
                        source_id=id1,
                        target_id=id2,
                        weight=weight,
                        relation_type=relation_type,
                        shared_entities=shared_entities
                    )
                    
                    edges.append(edge)
                    self.edges[id1].append(edge)
                    self.edges[id2].append(edge)
        
        # 限制每个节点的边数，保留权重最高的
        for node_id in self.edges:
            self.edges[node_id] = sorted(
                self.edges[node_id],
                key=lambda e: e.weight,
                reverse=True
            )[:self.max_edges]
        
        logger.info(f"[事件图谱] 构建关系: 节点={len(self.nodes)}, 边={len(edges)}")
        
        return edges
    
    def get_related_events(
        self,
        event_id: str,
        min_weight: float = 0.5
    ) -> List[Tuple[EventNode, float]]:
        """
        获取相关事件
        
        Args:
            event_id: 事件ID
            min_weight: 最小关联权重
            
        Returns:
            (相关事件, 权重) 列表
        """
        if event_id not in self.nodes:
            return []
        
        related = []
        for edge in self.edges.get(event_id, []):
            if edge.weight >= min_weight:
                other_id = edge.target_id if edge.source_id == event_id else edge.source_id
                if other_id in self.nodes:
                    related.append((self.nodes[other_id], edge.weight))
        
        # 按权重排序
        related.sort(key=lambda x: x[1], reverse=True)
        
        return related
    
    def get_event_chain(
        self,
        start_event_id: str,
        max_depth: int = 3
    ) -> List[List[str]]:
        """
        获取事件链（时间线）
        
        Args:
            start_event_id: 起始事件ID
            max_depth: 最大深度
            
        Returns:
            事件链列表
        """
        if start_event_id not in self.nodes:
            return []
        
        chains = []
        visited = {start_event_id}
        
        async def dfs(current_id: str, current_chain: List[str], depth: int):
            if depth >= max_depth:
                chains.append(current_chain[:])
                return
            
            for edge in self.edges.get(current_id, []):
                next_id = edge.target_id if edge.source_id == current_id else edge.source_id
                
                if next_id not in visited:
                    visited.add(next_id)
                    current_chain.append(next_id)
                    await dfs(next_id, current_chain, depth + 1)
                    current_chain.pop()
                    visited.remove(next_id)
        
        # 运行DFS
        asyncio.create_task(dfs(start_event_id, [start_event_id], 0))
        
        return chains
    
    def get_hot_topics(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """
        获取热点主题
        
        Args:
            top_n: 返回前N个
            
        Returns:
            (主题, 提及次数) 列表
        """
        entity_counts = defaultdict(int)
        
        for node in self.nodes.values():
            for entity in node.entities:
                entity_counts[entity] += 1
        
        # 排序并返回
        sorted_topics = sorted(
            entity_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_topics[:top_n]
    
    def get_timeline(self) -> List[EventNode]:
        """
        获取按时间排序的事件列表
        
        Returns:
            事件节点列表
        """
        return sorted(self.nodes.values(), key=lambda x: x.timestamp)
    
    def get_subgraph(self, event_ids: List[str]) -> Dict:
        """
        获取子图（用于可视化）
        
        Args:
            event_ids: 事件ID列表
            
        Returns:
            子图数据
        """
        nodes = []
        edges = []
        
        for eid in event_ids:
            if eid in self.nodes:
                node = self.nodes[eid]
                nodes.append({
                    'id': node.id,
                    'title': node.title,
                    'timestamp': node.timestamp.isoformat(),
                    'entity_count': len(node.entities),
                    'sentiment': node.sentiment
                })
                
                # 添加相关边
                for edge in self.edges.get(eid, []):
                    other_id = edge.target_id if edge.source_id == eid else edge.source_id
                    if other_id in event_ids:
                        edges.append({
                            'source': edge.source_id,
                            'target': edge.target_id,
                            'weight': edge.weight,
                            'type': edge.relation_type
                        })
        
        return {'nodes': nodes, 'edges': edges}
    
    def clear(self):
        """清空图谱"""
        self.nodes.clear()
        self.edges.clear()
        self.entity_index.clear()
        logger.info("[事件图谱] 已清空")
