"""
AI TradeBot - 智能去重器

基于余弦相似度的语义去重算法
阈值: 0.85 (认为同一事件)
"""
import asyncio
import math
import re
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from collections import Counter
from datetime import datetime, timedelta

from shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class NewsItem:
    """新闻项"""
    id: str
    title: str
    content: str
    source: str
    publish_time: datetime
    url: str = ""
    
    def __hash__(self):
        return hash(self.id)


@dataclass
class DuplicateGroup:
    """重复新闻组"""
    canonical_item: NewsItem  # 可信度最高的代表
    duplicates: List[NewsItem]  # 其他重复项
    similarity_scores: Dict[str, float]  # 相似度分数


class NewsDeduplicator:
    """
    新闻去重器
    
    使用基于词频的余弦相似度进行语义去重
    支持时间窗口过滤（同一事件在48小时内的报道）
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.85,
        time_window_hours: int = 48,
        min_word_length: int = 2
    ):
        """
        初始化去重器
        
        Args:
            similarity_threshold: 相似度阈值，超过则认为重复
            time_window_hours: 时间窗口（小时），只比较窗口内的内容
            min_word_length: 最小词长度
        """
        self.similarity_threshold = similarity_threshold
        self.time_window = timedelta(hours=time_window_hours)
        self.min_word_length = min_word_length
        
        # 停用词
        self.stopwords = self._load_stopwords()
        
        logger.info(
            f"[去重器] 初始化完成: 阈值={similarity_threshold}, "
            f"时间窗口={time_window_hours}h"
        )
    
    def _load_stopwords(self) -> Set[str]:
        """加载中文停用词"""
        return {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这', '那',
            '我们', '为', '之', '与', '及', '等', '或', '但', '而', '因',
            '于', '即', '使', '则', '若', '乃', '被', '把', '向', '到',
            '公司', '股份', '股票', '市场', '投资', '交易', '万元', '亿元'
        }
    
    def _tokenize(self, text: str) -> List[str]:
        """
        分词（简化版，基于字符n-gram）
        
        Args:
            text: 输入文本
            
        Returns:
            词列表
        """
        # 清洗文本
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)
        text = text.lower()
        
        # 提取中文词（2-4字）
        words = []
        chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        
        for i in range(len(chars) - 1):
            for j in range(2, min(5, len(chars) - i + 1)):
                word = ''.join(chars[i:i+j])
                if len(word) >= self.min_word_length and word not in self.stopwords:
                    words.append(word)
        
        # 提取英文单词
        english_words = re.findall(r'[a-z]+', text)
        words.extend([w for w in english_words if len(w) >= 3])
        
        return words
    
    def _compute_tf_idf(self, texts: List[str]) -> List[Dict[str, float]]:
        """
        计算TF-IDF向量
        
        Args:
            texts: 文本列表
            
        Returns:
            TF-IDF向量列表
        """
        # 分词
        tokenized = [self._tokenize(text) for text in texts]
        
        # 构建词汇表
        vocab = set()
        for tokens in tokenized:
            vocab.update(tokens)
        vocab = sorted(list(vocab))
        word_to_idx = {word: idx for idx, word in enumerate(vocab)}
        
        # 计算DF（文档频率）
        df = Counter()
        for tokens in tokenized:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                df[token] += 1
        
        # 计算TF-IDF
        vectors = []
        n_docs = len(texts)
        
        for tokens in tokenized:
            tf = Counter(tokens)
            vector = {}
            
            for word, count in tf.items():
                if word in word_to_idx:
                    tf_val = count / len(tokens) if tokens else 0
                    idf_val = math.log(n_docs / (df[word] + 1)) + 1
                    vector[word] = tf_val * idf_val
            
            vectors.append(vector)
        
        return vectors
    
    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """
        计算余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            相似度分数 (0-1)
        """
        # 获取所有维度
        all_keys = set(vec1.keys()) | set(vec2.keys())
        
        # 计算点积
        dot_product = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in all_keys)
        
        # 计算模
        norm1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        norm2 = math.sqrt(sum(v ** 2 for v in vec2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def deduplicate(self, items: List[NewsItem]) -> List[DuplicateGroup]:
        """
        去重主函数
        
        Args:
            items: 新闻列表
            
        Returns:
            去重后的新闻组列表
        """
        if not items:
            return []
        
        if len(items) == 1:
            return [DuplicateGroup(items[0], [], {items[0].id: 1.0})]
        
        logger.info(f"[去重器] 开始处理 {len(items)} 条新闻")
        
        # 按时间排序
        sorted_items = sorted(items, key=lambda x: x.publish_time, reverse=True)
        
        # 准备文本
        texts = [f"{item.title} {item.content}" for item in sorted_items]
        
        # 计算TF-IDF向量
        vectors = self._compute_tf_idf(texts)
        
        # 计算相似度矩阵
        n = len(sorted_items)
        similar_pairs: List[Tuple[int, int, float]] = []
        
        for i in range(n):
            for j in range(i + 1, n):
                # 检查时间窗口
                time_diff = abs((sorted_items[i].publish_time - sorted_items[j].publish_time).total_seconds())
                if time_diff > self.time_window.total_seconds():
                    continue
                
                # 计算相似度
                sim = self._cosine_similarity(vectors[i], vectors[j])
                if sim >= self.similarity_threshold:
                    similar_pairs.append((i, j, sim))
        
        # 使用并查集分组
        parent = list(range(n))
        
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            parent[find(x)] = find(y)
        
        for i, j, _ in similar_pairs:
            union(i, j)
        
        # 构建分组
        groups: Dict[int, List[int]] = {}
        for idx in range(n):
            root = find(idx)
            if root not in groups:
                groups[root] = []
            groups[root].append(idx)
        
        # 构建结果
        result = []
        for group_indices in groups.values():
            group_items = [sorted_items[i] for i in group_indices]
            
            # 选择可信度最高的作为代表
            # 简单规则：官方来源优先，然后是时间最新
            source_priority = {
                '财联社': 5, '证券时报': 5, '上海证券报': 5,
                '中国证券报': 5, '证监会': 5, '交易所': 5,
                '新浪财经': 4, '东方财富': 4, '同花顺': 4,
                '雪球': 3, '股吧': 2, '自媒体': 1
            }
            
            canonical = max(group_items, key=lambda x: (
                source_priority.get(x.source, 1),
                x.publish_time
            ))
            
            duplicates = [item for item in group_items if item.id != canonical.id]
            
            # 记录相似度
            similarity_scores = {canonical.id: 1.0}
            canonical_idx = sorted_items.index(canonical)
            for item in duplicates:
                item_idx = sorted_items.index(item)
                for i, j, sim in similar_pairs:
                    if (i == canonical_idx and j == item_idx) or (i == item_idx and j == canonical_idx):
                        similarity_scores[item.id] = sim
                        break
            
            result.append(DuplicateGroup(
                canonical_item=canonical,
                duplicates=duplicates,
                similarity_scores=similarity_scores
            ))
        
        logger.info(
            f"[去重器] 完成: {len(items)} 条 → {len(result)} 组, "
            f"去重率 {(1 - len(result)/len(items))*100:.1f}%"
        )
        
        return result
    
    async def is_duplicate(self, new_item: NewsItem, existing_items: List[NewsItem]) -> Tuple[bool, float]:
        """
        检查单条新闻是否与已有列表重复
        
        Args:
            new_item: 新新闻
            existing_items: 已有新闻列表
            
        Returns:
            (是否重复, 最高相似度)
        """
        if not existing_items:
            return False, 0.0
        
        all_items = existing_items + [new_item]
        texts = [f"{item.title} {item.content}" for item in all_items]
        vectors = self._compute_tf_idf(texts)
        
        new_idx = len(all_items) - 1
        max_sim = 0.0
        
        for i in range(len(existing_items)):
            # 检查时间窗口
            time_diff = abs((new_item.publish_time - existing_items[i].publish_time).total_seconds())
            if time_diff > self.time_window.total_seconds():
                continue
            
            sim = self._cosine_similarity(vectors[i], vectors[new_idx])
            max_sim = max(max_sim, sim)
            
            if sim >= self.similarity_threshold:
                return True, sim
        
        return False, max_sim
