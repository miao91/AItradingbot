"""
AI TradeBot - 蒙特卡洛引擎单元测试
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from decision.engine.monte_carlo_engine import (
    MonteCarloEngine,
    SimulationResult,
    ComputeBackend,
    detect_gpu_backend,
    run_monte_carlo_simulation,
)


class TestComputeBackend:
    """后端类型枚举测试"""

    def test_backend_types_exist(self):
        """测试后端类型存在"""
        assert hasattr(ComputeBackend, 'CUPY')
        assert hasattr(ComputeBackend, 'PYTORCH')
        assert hasattr(ComputeBackend, 'NUMPY')

    def test_backend_values(self):
        """测试后端类型值"""
        assert ComputeBackend.CUPY.value == "cupy"
        assert ComputeBackend.PYTORCH.value == "pytorch"
        assert ComputeBackend.NUMPY.value == "numpy"


class TestSimulationResult:
    """模拟结果数据类测试"""

    def test_result_creation(self):
        """测试结果创建"""
        result = SimulationResult(
            ticker="600000.SH",
            current_price=95.0,
            final_prices=np.array([100.0, 105.0, 90.0]),
            mean_price=100.0,
            std_price=10.0,
            var_95=85.0,
            var_99=80.0,
            expected_shortfall_95=82.0,
            expected_shortfall_99=78.0,
            upside_probability=0.55,
            downside_probability=0.45,
            histogram=np.array([10, 20, 30, 20, 10]),
            bin_edges=np.array([80.0, 90.0, 100.0, 110.0, 120.0, 130.0]),
            num_simulations=10000,
            backend_used="numpy",
            execution_time_ms=100.0,
        )

        assert result.ticker == "600000.SH"
        assert result.current_price == 95.0
        assert result.num_simulations == 10000
        assert result.backend_used == "numpy"

    def test_result_probabilities(self):
        """测试概率计算"""
        result = SimulationResult(
            ticker="600000.SH",
            current_price=100.0,
            final_prices=np.array([100.0]),
            mean_price=100.0,
            std_price=10.0,
            var_95=85.0,
            var_99=80.0,
            expected_shortfall_95=82.0,
            expected_shortfall_99=78.0,
            upside_probability=0.6,
            downside_probability=0.4,
            histogram=np.array([]),
            bin_edges=np.array([]),
            num_simulations=10000,
            backend_used="numpy",
            execution_time_ms=50.0,
        )

        # 上涨和下跌概率之和应该接近 1
        total_prob = result.upside_probability + result.downside_probability
        assert 0.95 <= total_prob <= 1.05


class TestDetectGPUBackend:
    """GPU 后端检测测试"""

    def test_detect_backend_returns_tuple(self):
        """测试检测返回元组"""
        backend_type, message = detect_gpu_backend()

        assert isinstance(backend_type, ComputeBackend)
        assert isinstance(message, str)

    def test_detect_backend_fallback(self):
        """测试降级到 CPU"""
        with patch('decision.engine.monte_carlo_engine.importlib.util.find_spec') as mock_find:
            # 模拟 CuPy 和 PyTorch 都不可用
            mock_find.return_value = None

            backend_type, message = detect_gpu_backend()

            # 应该降级到 NumPy
            assert backend_type == ComputeBackend.NUMPY


class TestMonteCarloEngine:
    """蒙特卡洛引擎测试"""

    @pytest.fixture
    def engine_numpy(self):
        """创建 NumPy 后端引擎"""
        return MonteCarloEngine(backend=ComputeBackend.NUMPY)

    def test_engine_initialization(self, engine_numpy):
        """测试引擎初始化"""
        assert engine_numpy is not None
        assert engine_numpy.backend == ComputeBackend.NUMPY

    def test_engine_run_simulation(self, engine_numpy):
        """测试运行模拟"""
        result = engine_numpy.run_simulation(
            ticker="600000.SH",
            current_price=95.0,
            growth_mean=0.10,
            growth_std=0.20,
            time_horizon_days=252,
            num_simulations=1000,  # 使用较少的模拟次数加快测试
        )

        assert result is not None
        assert isinstance(result, SimulationResult)
        assert result.ticker == "600000.SH"
        assert result.current_price == 95.0
        assert result.num_simulations == 1000

    def test_engine_simulation_statistics(self, engine_numpy):
        """测试模拟统计量"""
        result = engine_numpy.run_simulation(
            ticker="600000.SH",
            current_price=100.0,
            growth_mean=0.08,
            growth_std=0.15,
            time_horizon_days=252,
            num_simulations=1000,
        )

        # 检查统计量
        assert result.mean_price > 0
        assert result.std_price > 0
        assert result.var_95 > 0
        assert result.var_99 > 0
        assert result.var_99 <= result.var_95  # 99% VaR 应该更保守

    def test_engine_var_calculation(self, engine_numpy):
        """测试 VaR 计算"""
        result = engine_numpy.run_simulation(
            ticker="600000.SH",
            current_price=100.0,
            growth_mean=0.10,
            growth_std=0.20,
            time_horizon_days=252,
            num_simulations=1000,
        )

        # VaR 应该小于当前价格（风险是下行）
        assert result.var_95 <= result.current_price
        assert result.var_99 <= result.current_price

    def test_engine_expected_shortfall(self, engine_numpy):
        """测试 Expected Shortfall 计算"""
        result = engine_numpy.run_simulation(
            ticker="600000.SH",
            current_price=100.0,
            growth_mean=0.10,
            growth_std=0.20,
            time_horizon_days=252,
            num_simulations=1000,
        )

        # ES 应该比 VaR 更保守（更低）
        assert result.expected_shortfall_95 <= result.var_95
        assert result.expected_shortfall_99 <= result.var_99

    def test_engine_histogram(self, engine_numpy):
        """测试直方图生成"""
        result = engine_numpy.run_simulation(
            ticker="600000.SH",
            current_price=100.0,
            growth_mean=0.10,
            growth_std=0.20,
            time_horizon_days=252,
            num_simulations=1000,
        )

        assert result.histogram is not None
        assert result.bin_edges is not None
        assert len(result.histogram) > 0
        assert len(result.bin_edges) == len(result.histogram) + 1

    def test_engine_execution_time(self, engine_numpy):
        """测试执行时间记录"""
        result = engine_numpy.run_simulation(
            ticker="600000.SH",
            current_price=100.0,
            num_simulations=1000,
        )

        assert result.execution_time_ms > 0
        assert result.execution_time_ms < 10000  # 应该在 10 秒内完成

    def test_engine_different_tickers(self, engine_numpy):
        """测试不同股票代码"""
        tickers = ["600000.SH", "000001.SZ", "AAPL"]

        for ticker in tickers:
            result = engine_numpy.run_simulation(
                ticker=ticker,
                current_price=100.0,
                num_simulations=100,
            )
            assert result.ticker == ticker

    def test_engine_extreme_parameters(self, engine_numpy):
        """测试极端参数"""
        # 极高波动率
        result = engine_numpy.run_simulation(
            ticker="600000.SH",
            current_price=100.0,
            growth_mean=0.0,
            growth_std=0.50,  # 50% 波动率
            num_simulations=100,
        )

        assert result is not None
        # 高波动率应该导致更大的标准差
        assert result.std_price > 0


class TestConvenienceFunction:
    """便捷函数测试"""

    def test_run_monte_carlo_simulation(self):
        """测试便捷函数"""
        result = run_monte_carlo_simulation(
            ticker="600000.SH",
            current_price=95.0,
            num_simulations=100,
        )

        assert result is not None
        assert isinstance(result, SimulationResult)
        assert result.ticker == "600000.SH"


class TestEngineBackends:
    """后端兼容性测试"""

    def test_numpy_backend_available(self):
        """测试 NumPy 后端可用"""
        engine = MonteCarloEngine(backend=ComputeBackend.NUMPY)
        assert engine.backend == ComputeBackend.NUMPY

        result = engine.run_simulation(
            ticker="TEST",
            current_price=100.0,
            num_simulations=100,
        )
        assert result.backend_used == "numpy"

    @pytest.mark.skipif(
        not pytest.importorskip("cupy", reason="CuPy not installed"),
        reason="CuPy not available"
    )
    def test_cupy_backend_if_available(self):
        """测试 CuPy 后端（如果可用）"""
        try:
            engine = MonteCarloEngine(backend=ComputeBackend.CUPY)
            result = engine.run_simulation(
                ticker="TEST",
                current_price=100.0,
                num_simulations=100,
            )
            assert result.backend_used in ["cupy", "numpy"]  # 可能降级
        except Exception:
            pytest.skip("CuPy backend not available")

    @pytest.mark.skipif(
        not pytest.importorskip("torch", reason="PyTorch not installed"),
        reason="PyTorch not available"
    )
    def test_pytorch_backend_if_available(self):
        """测试 PyTorch 后端（如果可用）"""
        try:
            import torch
            if not torch.cuda.is_available():
                pytest.skip("CUDA not available")

            engine = MonteCarloEngine(backend=ComputeBackend.PYTORCH)
            result = engine.run_simulation(
                ticker="TEST",
                current_price=100.0,
                num_simulations=100,
            )
            assert result.backend_used in ["pytorch", "numpy"]  # 可能降级
        except Exception:
            pytest.skip("PyTorch GPU backend not available")


class TestEdgeCases:
    """边界情况测试"""

    @pytest.fixture
    def engine(self):
        return MonteCarloEngine(backend=ComputeBackend.NUMPY)

    def test_zero_price(self, engine):
        """测试零价格"""
        # 零价格可能导致问题，但不应崩溃
        try:
            result = engine.run_simulation(
                ticker="TEST",
                current_price=0.0,
                num_simulations=100,
            )
            # 如果不抛异常，检查结果
            assert result is not None
        except (ValueError, ZeroDivisionError):
            # 预期的异常
            pass

    def test_negative_price(self, engine):
        """测试负价格"""
        try:
            result = engine.run_simulation(
                ticker="TEST",
                current_price=-100.0,
                num_simulations=100,
            )
            # 如果不抛异常，检查结果
            assert result is not None
        except ValueError:
            # 预期的异常
            pass

    def test_very_small_simulation_count(self, engine):
        """测试非常少的模拟次数"""
        result = engine.run_simulation(
            ticker="TEST",
            current_price=100.0,
            num_simulations=10,
        )
        assert result is not None
        assert result.num_simulations == 10

    def test_single_day_horizon(self, engine):
        """测试单日时间范围"""
        result = engine.run_simulation(
            ticker="TEST",
            current_price=100.0,
            time_horizon_days=1,
            num_simulations=100,
        )
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
