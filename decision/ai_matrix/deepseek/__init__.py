"""
DeepSeek AI 模型客户端
用于快速新闻分类和评分
"""
from .client import DeepSeekClient, get_deepseek_client

__all__ = [
    "DeepSeekClient",
    "get_deepseek_client",
]
