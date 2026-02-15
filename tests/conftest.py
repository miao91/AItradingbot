"""
AI TradeBot - pytest 配置文件
"""
import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def test_env():
    """设置测试环境变量"""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["DEBUG"] = "true"
    os.environ["SIMULATION_MODE"] = "true"
    return os.environ


@pytest.fixture
def mock_ai_keys(test_env):
    """模拟 API Keys"""
    test_env.update({
        "KIMI_API_KEY": "test_kimi_key",
        "ZHIPU_API_KEY": "test_zhipu_key",
        "MINIMAX_API_KEY": "test_minimax_key",
        "MINIMAX_GROUP_ID": "test_group_id",
        "TAVILY_API_KEY": "test_tavily_key",
        "TUSHARE_TOKEN": "test_tushare_token",
    })
    return test_env


@pytest.fixture
def sample_event():
    """示例事件数据"""
    return {
        "event_id": "EVT_TEST_001",
        "source": "test",
        "type": "announcement",
        "symbol": "600000.SH",
        "title": "测试公告",
        "content": "这是一条测试公告内容",
        "timestamp": "2025-01-11 10:00:00",
    }


@pytest.fixture
def sample_decision_bundle():
    """示例决策包"""
    return {
        "event_id": "EVT_TEST_001",
        "action": "BUY",
        "symbol": "600000.SH",
        "quantity": 1000,
        "entry_logic": "测试买入逻辑",
        "exit_plan": {
            "take_profit": {
                "price": 12.50,
                "logic": "测试止盈逻辑"
            },
            "stop_loss": {
                "price": 11.20,
                "logic": "测试止损逻辑"
            },
            "expiration": {
                "date": "2025-03-31",
                "logic": "测试失效时间逻辑"
            }
        },
        "confidence": 0.75,
        "reasoning_chain": ["reason1", "reason2"],
    }


@pytest.fixture
def mock_qmt_position():
    """模拟 QMT 持仓数据"""
    return {
        "symbol": "600000.SH",
        "quantity": 1000,
        "available": 1000,
        "cost_price": 10.00,
        "current_price": 10.50,
        "market_value": 10500.0,
        "pnl": 500.0,
        "pnl_ratio": 0.05,
    }


@pytest.fixture
def mock_trade_result():
    """模拟交易结果"""
    return {
        "order_id": "ORD_TEST_001",
        "status": "filled",
        "symbol": "600000.SH",
        "side": "buy",
        "quantity": 1000,
        "price": 10.50,
        "timestamp": "2025-01-11 10:30:00",
    }


# Async 测试支持
@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于异步测试"""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# 数据库测试 fixture
@pytest.fixture
async def test_db():
    """创建测试数据库"""
    from core.database.base import Base
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield async_session

    await engine.dispose()
