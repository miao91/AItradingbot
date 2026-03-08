# AI TradeBot - 投资者信息获取优化任务

## 🎯 任务目标
以投资者信息获取视角，优化 AI TradeBot 的信息感知层，构建智能信息聚合中心。

## 📍 当前工作目录
D:\AI\AItradebot

## ✅ 当前优点（保持）
1. Tavily搜索 + Tushare新闻 + AkShare行情 多源采集
2. DeepSeek AI评分(1-10分)快速过滤
3. 关键词双轨过滤（核心词/忽略词）
4. Token防火墙（1000字符截断）
5. 三级过滤机制

## ❌ 关键不足（需优化）

### 【P0 - 最高优先级】
1. **信息源单一**：缺少雪球/股吧舆情、机构研报、宏观数据
2. **信息聚合弱**：无去重机制、无关联分析

### 【P1 - 高优先级】
3. **情感分析缺失**：无市场情绪指标
4. **历史对比缺失**：无类似事件历史表现对比

## 🔧 具体任务

请在 perception/ 目录下创建以下模块：

### 1. 信息聚合中心 (perception/fusion/)
创建以下文件：
- __init__.py
- fusion_engine.py - 核心聚合引擎
- deduplicator.py - 基于余弦相似度的智能去重（阈值0.85）
- credibility_scorer.py - 信息可信度评级（根据来源+时效性+作者）
- event_graph.py - 事件关联图谱（基于共现实体）

### 2. 情感分析系统 (perception/sentiment/)
创建：
- __init__.py
- emotion_analyzer.py - 使用简单关键词+规则的情感分析（无需大模型）
- trend_tracker.py - 情感趋势追踪（24h/7d滑动窗口）
- market_mood.py - 市场情绪指数（恐慌/贪婪）

### 3. 多源采集扩展 (perception/sources/)
创建：
- __init__.py
- xueqiu.py - 雪球热帖采集（使用akshare）
- eastmoney_report.py - 东方财富研报摘要（使用akshare）
- macro_data.py - 宏观经济指标（USD/CNH、DXY、10Y国债）

### 4. 事件记忆系统 (perception/memory/)
创建：
- __init__.py
- event_template.py - 事件模板结构
- similarity_search.py - 基于关键词的相似事件检索

## 📋 技术要求

1. **所有模块必须异步(async/await)**
2. **必须包含限流保护**（每秒最多5次调用）
3. **必须记录日志**（使用现有的 from shared.logging import get_logger）
4. **必须处理异常**（不要中断主流程）
5. **保持与现有系统松耦合**（可独立运行）

## 🚫 约束条件

1. 不修改现有数据库表
2. 不删除现有代码
3. 使用现有工具：akshare、tushare（已有）
4. 无需额外付费API

## 📊 验收标准

- [ ] fusion/ 目录下5个文件可正常导入
- [ ] sentiment/ 目录下4个文件可正常导入
- [ ] sources/ 目录下4个文件可正常导入
- [ ] memory/ 目录下3个文件可正常导入
- [ ] 所有模块可通过简单测试（无语法错误）

## 💡 代码模板参考

### 文件头部模板
```python
"""
AI TradeBot - [模块名称]

功能描述...
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from shared.logging import get_logger

logger = get_logger(__name__)
```

### 限流装饰器模板
```python
def rate_limit(max_calls: int = 5, period: float = 1.0):
    """简单限流装饰器"""
    def decorator(func):
        last_call = [0]
        async def wrapper(*args, **kwargs):
            now = asyncio.get_event_loop().time()
            if now - last_call[0] < period / max_calls:
                await asyncio.sleep(period / max_calls - (now - last_call[0]))
            last_call[0] = asyncio.get_event_loop().time()
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### 异步类模板
```python
class FusionEngine:
    """信息聚合引擎"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
    async def process(self, items: List[NewsItem]) -> List[AggregatedNews]:
        """处理信息"""
        try:
            # 实现逻辑
            pass
        except Exception as e:
            self.logger.error(f"处理失败: {e}")
            return []
```

## ⏱️ 时间预算

你有3小时自由发挥。当前时间：18:15
请立即开始工作，完成后汇报：
1. 创建了哪些文件
2. 每个模块的功能说明
3. 测试运行情况

开始执行！
