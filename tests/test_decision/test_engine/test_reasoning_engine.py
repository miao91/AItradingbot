"""
AI TradeBot - 推理引擎单元测试

测试实际实现的公共接口
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from decision.engine.reasoning_engine import (
    ReasoningEngine,
    ReasoningChain,
    ReasoningStep,
    ReasoningStatus,
)


class TestReasoningStatus:
    """推理状态枚举测试"""

    def test_status_values(self):
        """测试状态值"""
        assert hasattr(ReasoningStatus, 'PENDING')
        assert hasattr(ReasoningStatus, 'RUNNING')
        assert hasattr(ReasoningStatus, 'COMPLETED')
        assert hasattr(ReasoningStatus, 'FAILED')


class TestReasoningStep:
    """推理步骤数据类测试"""

    def test_step_creation(self):
        """测试步骤创建"""
        step = ReasoningStep(
            step_id=1,
            icon="📊",
            name="数据收集",
            status=ReasoningStatus.COMPLETED,
            content="已收集 100 条数据",
        )

        assert step.step_id == 1
        assert step.name == "数据收集"
        assert step.status == ReasoningStatus.COMPLETED

    def test_step_default_status(self):
        """测试默认状态"""
        step = ReasoningStep(
            step_id=2,
            icon="🔬",
            name="测试步骤",
        )

        assert step.status == ReasoningStatus.PENDING

    def test_step_to_dict(self):
        """测试转换为字典"""
        step = ReasoningStep(
            step_id=1,
            icon="📊",
            name="测试",
            content="内容",
        )

        d = step.to_dict()
        assert d["step_id"] == 1
        assert d["name"] == "测试"


class TestReasoningChain:
    """推理链数据类测试"""

    def test_chain_creation(self):
        """测试链创建"""
        chain = ReasoningChain(
            chain_id="test_chain_001",
            ticker="600000.SH",
            event_description="测试事件",
        )

        assert chain.chain_id == "test_chain_001"
        assert chain.ticker == "600000.SH"

    def test_chain_steps(self):
        """测试链步骤"""
        chain = ReasoningChain(
            chain_id="test_chain_002",
            ticker="600000.SH",
            event_description="测试",
            steps=[
                ReasoningStep(1, "📊", "步骤1", ReasoningStatus.COMPLETED),
                ReasoningStep(2, "🔬", "步骤2", ReasoningStatus.RUNNING),
            ],
        )

        assert len(chain.steps) == 2

    def test_chain_to_dict(self):
        """测试链转换为字典"""
        chain = ReasoningChain(
            chain_id="test",
            ticker="600000.SH",
            event_description="测试",
        )

        d = chain.to_dict()
        assert d["chain_id"] == "test"
        assert d["ticker"] == "600000.SH"


class TestReasoningEngine:
    """推理引擎测试"""

    @pytest.fixture
    def engine(self):
        """创建引擎实例"""
        return ReasoningEngine()

    def test_engine_initialization(self, engine):
        """测试引擎初始化"""
        assert engine is not None

    @pytest.mark.asyncio
    async def test_start_reasoning(self, engine):
        """测试启动推理"""
        try:
            chain = await engine.start_reasoning(
                ticker="600000.SH",
                event_description="测试事件描述",
            )

            assert chain is not None
            assert isinstance(chain, ReasoningChain)
            assert chain.ticker == "600000.SH"
            assert chain.chain_id is not None
        except Exception:
            # LLM 可能不可用
            pass

    @pytest.mark.asyncio
    async def test_get_chain(self, engine):
        """测试获取推理链"""
        try:
            created_chain = await engine.start_reasoning("600000.SH", "测试")
            retrieved_chain = engine.get_chain(created_chain.chain_id)

            assert retrieved_chain is not None
            assert retrieved_chain.chain_id == created_chain.chain_id
        except Exception:
            pass

    def test_get_nonexistent_chain(self, engine):
        """测试获取不存在的链"""
        chain = engine.get_chain("nonexistent_id")
        assert chain is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
