"""
AI TradeBot - 五维评估模型

核心评估维度（0-10分评分系统）：
1. 重塑性 (Reshaping) - 事件对市场格局的重塑能力
2. 持续性 (Persistence) - 趋势/事件的持续能力
3. 地缘政治传导 (Geopolitical) - 地缘政治因素对市场的影响传导
4. 市场定价偏离 (Mispricing) - 当前价格与内在价值的偏离程度
5. 流动性环境 (Liquidity) - 市场流动性条件

综合评分用于决定交易机会的优先级和仓位配置
"""
import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from shared.logging import get_logger
from shared.llm.clients import get_glm5_client, GLM5Client


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

SCORER_CONFIG = {
    # 各维度权重
    "dimension_weights": {
        "reshaping": 0.25,      # 重塑性权重
        "persistence": 0.20,   # 持续性权重
        "geopolitical": 0.15,  # 地缘政治权重
        "mispricing": 0.25,    # 定价偏离权重
        "liquidity": 0.15,     # 流动性权重
    },

    # 评分阈值
    "score_thresholds": {
        "excellent": 8.0,   # 优秀
        "good": 6.5,        # 良好
        "fair": 5.0,        # 一般
        "poor": 3.0,        # 较差
    },

    # AI 模型配置
    "ai_model": "glm-5",
    "max_tokens": 2000,
    "temperature": 0.3,
}


# =============================================================================
# 数据类
# =============================================================================

class ScoreLevel(Enum):
    """评分等级"""
    EXCELLENT = "excellent"  # 8.0+
    GOOD = "good"           # 6.5-8.0
    FAIR = "fair"           # 5.0-6.5
    POOR = "poor"           # 3.0-5.0
    AVOID = "avoid"         # <3.0


@dataclass
class DimensionScore:
    """单维度评分"""
    dimension: str
    score: float  # 0-10
    reasoning: str
    key_factors: List[str] = field(default_factory=list)
    confidence: float = 0.8  # 置信度 0-1

    @property
    def level(self) -> ScoreLevel:
        """获取评分等级"""
        if self.score >= 8.0:
            return ScoreLevel.EXCELLENT
        elif self.score >= 6.5:
            return ScoreLevel.GOOD
        elif self.score >= 5.0:
            return ScoreLevel.FAIR
        elif self.score >= 3.0:
            return ScoreLevel.POOR
        else:
            return ScoreLevel.AVOID


@dataclass
class FiveDimensionAssessment:
    """五维评估结果"""
    # 输入信息
    ticker: str
    event_description: str
    current_price: float

    # 五维评分
    reshaping: Optional[DimensionScore] = None      # 重塑性
    persistence: Optional[DimensionScore] = None    # 持续性
    geopolitical: Optional[DimensionScore] = None   # 地缘政治传导
    mispricing: Optional[DimensionScore] = None     # 市场定价偏离
    liquidity: Optional[DimensionScore] = None      # 流动性环境

    # 综合评分
    weighted_score: float = 0.0
    overall_level: ScoreLevel = ScoreLevel.FAIR

    # 投资建议
    recommendation: str = ""
    position_suggestion: str = ""

    # 元数据
    assessed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_ai_response: str = ""

    def get_all_scores(self) -> Dict[str, DimensionScore]:
        """获取所有维度评分"""
        return {
            "reshaping": self.reshaping,
            "persistence": self.persistence,
            "geopolitical": self.geopolitical,
            "mispricing": self.mispricing,
            "liquidity": self.liquidity,
        }

    def calculate_weighted_score(self) -> float:
        """计算加权综合评分"""
        weights = SCORER_CONFIG["dimension_weights"]
        total_score = 0.0
        total_weight = 0.0

        scores = self.get_all_scores()
        for dimension, score in scores.items():
            if score:
                weight = weights.get(dimension, 0.2)
                total_score += score.score * weight
                total_weight += weight

        if total_weight > 0:
            self.weighted_score = round(total_score / total_weight, 2)
        else:
            self.weighted_score = 0.0

        # 更新整体等级
        if self.weighted_score >= 8.0:
            self.overall_level = ScoreLevel.EXCELLENT
        elif self.weighted_score >= 6.5:
            self.overall_level = ScoreLevel.GOOD
        elif self.weighted_score >= 5.0:
            self.overall_level = ScoreLevel.FAIR
        elif self.weighted_score >= 3.0:
            self.overall_level = ScoreLevel.POOR
        else:
            self.overall_level = ScoreLevel.AVOID

        return self.weighted_score


# =============================================================================
# 五维评估引擎
# =============================================================================

class FiveDimensionScorer:
    """
    五维评估引擎

    基于 AI 的五维评分系统，用于评估交易机会的质量
    """

    # 维度定义
    DIMENSION_DEFINITIONS = {
        "reshaping": {
            "name": "重塑性",
            "description": "事件对市场格局的重塑能力",
            "high_score_criteria": [
                "颠覆性技术或商业模式创新",
                "行业格局重大变化",
                "监管政策重大转向",
                "市场领导地位的确立或动摇",
            ],
            "low_score_criteria": [
                "常规业务调整",
                "短期波动事件",
                "无长期影响的消息",
            ],
        },
        "persistence": {
            "name": "持续性",
            "description": "趋势/事件的持续能力和时间跨度",
            "high_score_criteria": [
                "长期结构性变化",
                "可持续的竞争优势",
                "政策/法规长期支持",
                "消费习惯根本性改变",
            ],
            "low_score_criteria": [
                "一次性事件",
                "短期季节性因素",
                "可快速逆转的变化",
            ],
        },
        "geopolitical": {
            "name": "地缘政治传导",
            "description": "地缘政治因素对市场的影响传导程度",
            "high_score_criteria": [
                "主要经济体政策变化",
                "贸易关系重大调整",
                "区域冲突或制裁影响",
                "汇率重大波动预期",
            ],
            "low_score_criteria": [
                "局部小范围事件",
                "对外贸市场无直接影响",
                "地缘局势稳定",
            ],
        },
        "mispricing": {
            "name": "市场定价偏离",
            "description": "当前价格与内在价值的偏离程度",
            "high_score_criteria": [
                "市场明显过度反应",
                "信息不对称导致定价错误",
                "短期情绪驱动偏离基本面",
                "估值处于历史极端位置",
            ],
            "low_score_criteria": [
                "价格接近公允价值",
                "市场定价充分反映信息",
                "估值处于合理区间",
            ],
        },
        "liquidity": {
            "name": "流动性环境",
            "description": "市场流动性和资金环境条件",
            "high_score_criteria": [
                "央行宽松政策支持",
                "市场风险偏好高",
                "资金充裕易于建仓",
                "交易成本低",
            ],
            "low_score_criteria": [
                "流动性紧缩",
                "市场恐慌情绪蔓延",
                "大额交易困难",
                "波动性极高",
            ],
        },
    }

    def __init__(self):
        """初始化评估引擎"""
        self.glm5_client: Optional[GLM5Client] = None
        self.config = SCORER_CONFIG

        logger.info(
            f"[五维评估] 初始化完成: "
            f"模型={self.config['ai_model']}, "
            f"权重={self.config['dimension_weights']}"
        )

    async def assess(
        self,
        ticker: str,
        event_description: str,
        current_price: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> FiveDimensionAssessment:
        """
        执行五维评估

        Args:
            ticker: 股票代码
            event_description: 事件描述
            current_price: 当前价格
            context: 额外上下文信息（行业、市场环境等）

        Returns:
            FiveDimensionAssessment 五维评估结果
        """
        logger.info(f"[五维评估] 开始评估: {ticker} - {event_description[:50]}...")

        # 初始化 AI 客户端
        if not self.glm5_client:
            self.glm5_client = get_glm5_client()

        # 构建评估提示词
        prompt = self._build_assessment_prompt(
            ticker, event_description, current_price, context
        )

        # 调用 AI 进行评估
        try:
            response = await self.glm5_client.call(
                prompt=prompt,
                max_tokens=self.config["max_tokens"],
                temperature=self.config["temperature"],
            )

            if not response.success:
                logger.error(f"[五维评估] AI 调用失败: {response.error_message}")
                return self._create_error_assessment(
                    ticker, event_description, current_price, response.error_message
                )

            # 解析 AI 响应
            assessment = self._parse_ai_response(
                ticker, event_description, current_price, response.content
            )
            assessment.raw_ai_response = response.content

            logger.info(
                f"[五维评估] 评估完成: {ticker} "
                f"综合评分={assessment.weighted_score} "
                f"等级={assessment.overall_level.value}"
            )

            return assessment

        except Exception as e:
            logger.error(f"[五维评估] 评估异常: {e}")
            return self._create_error_assessment(
                ticker, event_description, current_price, str(e)
            )

    def _build_assessment_prompt(
        self,
        ticker: str,
        event_description: str,
        current_price: float,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """构建评估提示词"""
        context_info = ""
        if context:
            context_info = f"""
【额外上下文】
- 行业: {context.get('industry', 'N/A')}
- 市场环境: {context.get('market_condition', 'N/A')}
- 相关新闻: {context.get('related_news', 'N/A')}
- 分析师观点: {context.get('analyst_view', 'N/A')}
"""

        return f"""你是 AI TradeBot 的五维评估专家。请对以下交易机会进行五维评分。

【评估标的】
- 股票代码: {ticker}
- 当前价格: {current_price} 元
- 事件描述: {event_description}
{context_info}

【五维评估框架】

1. 重塑性 (Reshaping) - 0-10分
   定义: 事件对市场格局的重塑能力
   高分标准: 颠覆性创新、行业格局变化、重大政策转向
   低分标准: 常规调整、短期波动、无长期影响

2. 持续性 (Persistence) - 0-10分
   定义: 趋势/事件的持续能力和时间跨度
   高分标准: 长期结构变化、可持续竞争优势、长期政策支持
   低分标准: 一次性事件、季节性因素、快速可逆

3. 地缘政治传导 (Geopolitical) - 0-10分
   定义: 地缘政治因素对市场的影响传导程度
   高分标准: 主要经济体政策变化、贸易关系调整、汇率重大波动
   低分标准: 局部小事件、无直接影响、地缘稳定

4. 市场定价偏离 (Mispricing) - 0-10分
   定义: 当前价格与内在价值的偏离程度
   高分标准: 市场过度反应、信息不对称、情绪驱动偏离
   低分标准: 价格接近公允、定价充分、估值合理

5. 流动性环境 (Liquidity) - 0-10分
   定义: 市场流动性和资金环境条件
   高分标准: 央行宽松、风险偏好高、资金充裕
   低分标准: 流动性紧缩、恐慌蔓延、交易困难

【输出格式】
请严格按以下 JSON 格式返回评估结果:
{{
    "reshaping": {{
        "score": 7.5,
        "reasoning": "简要说明评分理由",
        "key_factors": ["因素1", "因素2"],
        "confidence": 0.85
    }},
    "persistence": {{
        "score": 6.0,
        "reasoning": "简要说明",
        "key_factors": ["因素1"],
        "confidence": 0.8
    }},
    "geopolitical": {{
        "score": 4.0,
        "reasoning": "简要说明",
        "key_factors": [],
        "confidence": 0.7
    }},
    "mispricing": {{
        "score": 8.0,
        "reasoning": "简要说明",
        "key_factors": ["因素1", "因素2", "因素3"],
        "confidence": 0.9
    }},
    "liquidity": {{
        "score": 7.0,
        "reasoning": "简要说明",
        "key_factors": ["因素1"],
        "confidence": 0.85
    }},
    "recommendation": "综合投资建议（1-2句话）",
    "position_suggestion": "仓位建议：高/中/低 配置"
}}

请直接输出 JSON，不要添加其他内容。"""

    def _parse_ai_response(
        self,
        ticker: str,
        event_description: str,
        current_price: float,
        response: str,
    ) -> FiveDimensionAssessment:
        """解析 AI 响应"""
        assessment = FiveDimensionAssessment(
            ticker=ticker,
            event_description=event_description,
            current_price=current_price,
        )

        try:
            # 提取 JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            # 解析各维度评分
            assessment.reshaping = self._parse_dimension_score(
                "reshaping", data.get("reshaping", {})
            )
            assessment.persistence = self._parse_dimension_score(
                "persistence", data.get("persistence", {})
            )
            assessment.geopolitical = self._parse_dimension_score(
                "geopolitical", data.get("geopolitical", {})
            )
            assessment.mispricing = self._parse_dimension_score(
                "mispricing", data.get("mispricing", {})
            )
            assessment.liquidity = self._parse_dimension_score(
                "liquidity", data.get("liquidity", {})
            )

            # 提取建议
            assessment.recommendation = data.get("recommendation", "")
            assessment.position_suggestion = data.get("position_suggestion", "")

            # 计算综合评分
            assessment.calculate_weighted_score()

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"[五维评估] JSON 解析失败: {e}")
            # 设置默认评分
            assessment.reshaping = DimensionScore(
                dimension="reshaping",
                score=5.0,
                reasoning="解析失败，使用默认评分",
                confidence=0.3
            )
            assessment.calculate_weighted_score()

        return assessment

    def _parse_dimension_score(
        self,
        dimension: str,
        data: Dict[str, Any]
    ) -> DimensionScore:
        """解析单维度评分"""
        return DimensionScore(
            dimension=dimension,
            score=float(data.get("score", 5.0)),
            reasoning=data.get("reasoning", ""),
            key_factors=data.get("key_factors", []),
            confidence=float(data.get("confidence", 0.8)),
        )

    def _create_error_assessment(
        self,
        ticker: str,
        event_description: str,
        current_price: float,
        error_msg: str,
    ) -> FiveDimensionAssessment:
        """创建错误评估结果"""
        assessment = FiveDimensionAssessment(
            ticker=ticker,
            event_description=event_description,
            current_price=current_price,
        )

        # 设置默认错误评分
        default_score = DimensionScore(
            dimension="error",
            score=0.0,
            reasoning=f"评估失败: {error_msg}",
            confidence=0.0,
        )

        assessment.reshaping = default_score
        assessment.persistence = default_score
        assessment.geopolitical = default_score
        assessment.mispricing = default_score
        assessment.liquidity = default_score
        assessment.recommendation = "评估失败，建议谨慎处理"
        assessment.calculate_weighted_score()

        return assessment


# =============================================================================
# 全局单例
# =============================================================================

_five_dimension_scorer: Optional[FiveDimensionScorer] = None


def get_five_dimension_scorer() -> FiveDimensionScorer:
    """获取全局五维评估器实例"""
    global _five_dimension_scorer
    if _five_dimension_scorer is None:
        _five_dimension_scorer = FiveDimensionScorer()
    return _five_dimension_scorer


# =============================================================================
# 便捷函数
# =============================================================================

async def assess_trading_opportunity(
    ticker: str,
    event_description: str,
    current_price: float,
    context: Optional[Dict[str, Any]] = None,
) -> FiveDimensionAssessment:
    """
    评估交易机会（便捷函数）

    Args:
        ticker: 股票代码
        event_description: 事件描述
        current_price: 当前价格
        context: 额外上下文信息

    Returns:
        FiveDimensionAssessment 五维评估结果
    """
    scorer = get_five_dimension_scorer()
    return await scorer.assess(ticker, event_description, current_price, context)


# =============================================================================
# 主程序（用于测试）
# =============================================================================

async def main():
    """主程序（用于测试）"""
    print("=" * 60)
    print("AI TradeBot - 五维评估模型测试")
    print("=" * 60)
    print()

    # 测试用例
    test_cases = [
        {
            "ticker": "600000.SH",
            "event": "美联储暗示降息周期可能提前，市场预期流动性改善",
            "price": 95.0,
            "context": {
                "industry": "银行",
                "market_condition": "震荡上行",
            }
        },
        {
            "ticker": "300750.SZ",
            "event": "宁德时代发布新一代固态电池技术，能量密度提升50%",
            "price": 180.0,
            "context": {
                "industry": "新能源",
                "market_condition": "高景气度",
            }
        },
    ]

    scorer = get_five_dimension_scorer()

    for i, case in enumerate(test_cases, 1):
        print(f"\n测试用例 #{i}: {case['ticker']}")
        print(f"事件: {case['event']}")
        print("-" * 60)

        result = await scorer.assess(
            ticker=case["ticker"],
            event_description=case["event"],
            current_price=case["price"],
            context=case.get("context"),
        )

        print(f"\n综合评分: {result.weighted_score} ({result.overall_level.value})")
        print(f"投资建议: {result.recommendation}")
        print(f"仓位建议: {result.position_suggestion}")
        print()

        print("【五维评分明细】")
        for dim_name, score in result.get_all_scores().items():
            if score:
                print(f"  {score.dimension}: {score.score}/10")
                print(f"    理由: {score.reasoning}")
                print(f"    关键因素: {', '.join(score.key_factors) if score.key_factors else 'N/A'}")
                print()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
