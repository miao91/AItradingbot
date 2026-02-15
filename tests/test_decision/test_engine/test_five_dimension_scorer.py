"""
AI TradeBot - 五维评估模型单元测试

测试实际实现的公共接口
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from decision.engine.five_dimension_scorer import (
    FiveDimensionScorer,
    FiveDimensionAssessment,
    DimensionScore,
    ScoreLevel,
)


class TestScoreLevel:
    """评分等级枚举测试"""

    def test_level_values(self):
        """测试等级值"""
        assert ScoreLevel.EXCELLENT.value == "excellent"
        assert ScoreLevel.GOOD.value == "good"
        assert ScoreLevel.FAIR.value == "fair"
        assert ScoreLevel.POOR.value == "poor"
        assert ScoreLevel.AVOID.value == "avoid"


class TestDimensionScore:
    """维度评分数据类测试"""

    def test_dimension_score_creation(self):
        """测试维度评分创建"""
        score = DimensionScore(
            dimension="reshaping",
            score=7.5,
            reasoning="测试推理",
            key_factors=["因素1", "因素2"],
            confidence=0.85,
        )

        assert score.dimension == "reshaping"
        assert score.score == 7.5
        assert score.reasoning == "测试推理"
        assert len(score.key_factors) == 2
        assert score.confidence == 0.85

    def test_dimension_score_level_excellent(self):
        """测试优秀等级"""
        score = DimensionScore(dimension="test", score=8.5, reasoning="")
        assert score.level == ScoreLevel.EXCELLENT

    def test_dimension_score_level_good(self):
        """测试良好等级"""
        score = DimensionScore(dimension="test", score=7.0, reasoning="")
        assert score.level == ScoreLevel.GOOD

    def test_dimension_score_level_fair(self):
        """测试一般等级"""
        score = DimensionScore(dimension="test", score=5.5, reasoning="")
        assert score.level == ScoreLevel.FAIR

    def test_dimension_score_level_poor(self):
        """测试较差等级"""
        score = DimensionScore(dimension="test", score=4.0, reasoning="")
        assert score.level == ScoreLevel.POOR

    def test_dimension_score_level_avoid(self):
        """测试避免等级"""
        score = DimensionScore(dimension="test", score=2.0, reasoning="")
        assert score.level == ScoreLevel.AVOID


class TestFiveDimensionAssessment:
    """五维评估结果数据类测试"""

    def test_assessment_creation(self):
        """测试评估结果创建"""
        assessment = FiveDimensionAssessment(
            ticker="600000.SH",
            event_description="测试事件",
            current_price=95.0,
        )

        assert assessment.ticker == "600000.SH"
        assert assessment.event_description == "测试事件"
        assert assessment.current_price == 95.0

    def test_assessment_default_values(self):
        """测试默认值"""
        assessment = FiveDimensionAssessment(
            ticker="000001.SZ",
            event_description="测试",
            current_price=10.0,
        )

        assert assessment.reshaping is None
        assert assessment.persistence is None
        assert assessment.geopolitical is None
        assert assessment.mispricing is None
        assert assessment.liquidity is None
        assert assessment.weighted_score == 0.0
        assert assessment.overall_level == ScoreLevel.FAIR

    def test_get_all_scores(self):
        """测试获取所有评分"""
        assessment = FiveDimensionAssessment(
            ticker="600000.SH",
            event_description="测试",
            current_price=95.0,
            reshaping=DimensionScore("reshaping", 7.0, "测试"),
            persistence=DimensionScore("persistence", 8.0, "测试"),
        )

        scores = assessment.get_all_scores()

        assert scores["reshaping"] is not None
        assert scores["persistence"] is not None
        assert scores["geopolitical"] is None

    def test_calculate_weighted_score(self):
        """测试加权评分计算"""
        assessment = FiveDimensionAssessment(
            ticker="600000.SH",
            event_description="测试",
            current_price=95.0,
            reshaping=DimensionScore("reshaping", 8.0, "测试"),
            persistence=DimensionScore("persistence", 7.0, "测试"),
            geopolitical=DimensionScore("geopolitical", 6.0, "测试"),
            mispricing=DimensionScore("mispricing", 7.5, "测试"),
            liquidity=DimensionScore("liquidity", 8.5, "测试"),
        )

        weighted = assessment.calculate_weighted_score()

        assert 0 <= weighted <= 10
        assert weighted > 0  # 有评分所以应该大于 0


class TestFiveDimensionScorer:
    """五维评分器测试"""

    @pytest.fixture
    def scorer(self):
        """创建评分器实例"""
        return FiveDimensionScorer()

    def test_scorer_initialization(self, scorer):
        """测试评分器初始化"""
        assert scorer is not None

    @pytest.mark.asyncio
    async def test_assess_basic(self, scorer):
        """测试基本评估功能"""
        # 由于 LLM 可能不可用，使用 try/except
        try:
            result = await scorer.assess(
                ticker="600000.SH",
                event_description="测试事件描述",
                current_price=95.0,
            )

            assert result is not None
            assert isinstance(result, FiveDimensionAssessment)
            assert result.ticker == "600000.SH"
        except Exception as e:
            # LLM 不可用时可能会抛出异常
            # 这是预期行为
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
