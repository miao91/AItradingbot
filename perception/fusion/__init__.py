"""
AI TradeBot - 信息聚合中心

整合多源信息，实现智能去重与关联分析
"""
from perception.fusion.deduplicator import NewsDeduplicator
from perception.fusion.credibility_scorer import CredibilityScorer, SourceCredibility
from perception.fusion.event_graph import EventGraph, EventNode
from perception.fusion.fusion_engine import FusionEngine, AggregatedNews

__all__ = [
    'NewsDeduplicator',
    'CredibilityScorer',
    'SourceCredibility',
    'EventGraph',
    'EventNode',
    'FusionEngine',
    'AggregatedNews',
]
