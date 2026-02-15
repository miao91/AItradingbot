"""
AI TradeBot - 蒙特卡洛金融工程引擎 (GPU 加速版)

核心能力：
1. 利用 RTX 5080 GPU 进行大规模并行模拟 (100,000+ 次)
2. 基于概率分布的估值模型
3. 计算 VaR (风险价值) 和 Expected Shortfall (预期亏损)
4. 自动检测 GPU 环境，无缝降级到 CPU 多进程

技术栈：
- CuPy (NumPy GPU 版本) - 首选
- PyTorch CUDA - 备选
- NumPy + Multiprocessing - CPU 降级模式
"""
import os
import time
import asyncio
import multiprocessing as mp
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import json

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

MONTE_CARLO_CONFIG = {
    # 模拟参数
    "num_simulations": 100000,     # 默认模拟次数
    "random_seed": 42,              # 随机种子（可复现）

    # GPU 配置
    "gpu_device": 0,                # GPU 设备 ID
    "gpu_memory_fraction": 0.5,     # GPU 内存使用比例

    # CPU 降级配置
    "cpu_num_processes": mp.cpu_count(),  # CPU 进程数
    "cpu_chunk_size": 10000,        # 每个进程处理的模拟数

    # 统计参数
    "confidence_levels": [0.90, 0.95, 0.99],  # 置信水平

    # 分布类型
    "distribution_types": {
        "normal": "正态分布",
        "lognormal": "对数正态分布",
        "triangular": "三角分布",
        "uniform": "均匀分布",
    },
}


# =============================================================================
# GPU 环境检测
# =============================================================================

class ComputeBackend(Enum):
    """计算后端类型"""
    CUPY = "cupy"           # CuPy GPU
    PYTORCH = "pytorch"     # PyTorch GPU
    NUMPY = "numpy"         # NumPy CPU (降级)


def detect_gpu_backend() -> Tuple[ComputeBackend, str]:
    """
    检测可用的 GPU 计算后端

    Returns:
        (backend, message) 后端类型和状态消息
    """
    # 优先尝试 CuPy
    try:
        import cupy as cp
        # 测试 CUDA 可用性
        array = cp.array([1, 2, 3])
        del array
        gpu_name = cp.cuda.Device().compute_capability
        return ComputeBackend.CUPY, f"CuPy GPU 可用 (CUDA Compute: {gpu_name})"
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"[GPU检测] CuPy 检测失败: {e}")

    # 尝试 PyTorch
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            return ComputeBackend.PYTORCH, f"PyTorch GPU 可用 ({gpu_name})"
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"[GPU检测] PyTorch 检测失败: {e}")

    # 降级到 CPU
    return ComputeBackend.NUMPY, "CPU 模式 (NumPy 多进程)"


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class DistributionParams:
    """分布参数"""
    distribution_type: str  # normal, lognormal, triangular, uniform
    mean: float = 0.0
    std: float = 0.1
    low: float = 0.0        # 三角/均匀分布下限
    high: float = 0.0       # 三角/均匀分布上限
    mode: float = 0.0       # 三角分布众数


@dataclass
class SimulationInput:
    """模拟输入参数"""
    ticker: str
    current_price: float

    # 核心参数分布
    revenue_growth: DistributionParams      # 营收增长率
    discount_rate: DistributionParams       # 折现率
    terminal_multiple: DistributionParams   # 终端倍数
    profit_margin: DistributionParams       # 利润率

    # 模拟配置
    num_simulations: int = 100000
    time_horizon: int = 5  # 预测年限

    # 地缘政治风险调整
    geopolitical_risk: float = 0.0  # 0-1, 极端事件概率


@dataclass
class SimulationResult:
    """模拟结果"""
    ticker: str
    num_simulations: int
    compute_time_ms: float
    backend: str

    # 分布统计
    mean_value: float
    median_value: float
    std_value: float
    min_value: float
    max_value: float

    # 分位数
    percentiles: Dict[str, float] = field(default_factory=dict)

    # 风险指标
    var_95: float = 0.0           # 95% VaR
    var_99: float = 0.0           # 99% VaR
    expected_shortfall_95: float = 0.0  # 95% ES
    expected_shortfall_99: float = 0.0  # 99% ES

    # 概率分析
    prob_above_current: float = 0.0     # 高于当前价格的概率
    prob_above_mean: float = 0.5        # 高于均值的概率
    tail_risk_probability: float = 0.0  # 长尾风险概率

    # 置信区间
    confidence_intervals: Dict[float, Tuple[float, float]] = field(default_factory=dict)

    # 原始分布数据（用于可视化）
    distribution_histogram: List[float] = field(default_factory=list)
    bin_edges: List[float] = field(default_factory=list)

    # 元数据
    gpu_used: bool = False
    gpu_name: str = ""
    parallel_threads: int = 1
    simulated_at: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# 计算后端抽象
# =============================================================================

class ComputeBackendBase(ABC):
    """计算后端基类"""

    @abstractmethod
    def random_normal(self, size: int, mean: float, std: float, seed: int = None) -> Any:
        """生成正态分布随机数"""
        pass

    @abstractmethod
    def random_lognormal(self, size: int, mean: float, std: float, seed: int = None) -> Any:
        """生成对数正态分布随机数"""
        pass

    @abstractmethod
    def random_triangular(self, size: int, low: float, high: float, mode: float, seed: int = None) -> Any:
        """生成三角分布随机数"""
        pass

    @abstractmethod
    def calculate_percentile(self, data: Any, percentile: float) -> float:
        """计算分位数"""
        pass

    @abstractmethod
    def mean(self, data: Any) -> float:
        """计算均值"""
        pass

    @abstractmethod
    def std(self, data: Any) -> float:
        """计算标准差"""
        pass

    @abstractmethod
    def histogram(self, data: Any, bins: int = 50) -> Tuple[List[float], List[float]]:
        """计算直方图"""
        pass

    @abstractmethod
    def to_cpu(self, data: Any) -> Any:
        """将数据转移到 CPU"""
        pass


class NumPyBackend(ComputeBackendBase):
    """NumPy CPU 后端"""

    def __init__(self):
        import numpy as np
        self.np = np
        self.name = "NumPy CPU"

    def random_normal(self, size: int, mean: float, std: float, seed: int = None) -> Any:
        if seed is not None:
            self.np.random.seed(seed)
        return self.np.random.normal(mean, std, size)

    def random_lognormal(self, size: int, mean: float, std: float, seed: int = None) -> Any:
        if seed is not None:
            self.np.random.seed(seed)
        return self.np.random.lognormal(mean, std, size)

    def random_triangular(self, size: int, low: float, high: float, mode: float, seed: int = None) -> Any:
        if seed is not None:
            self.np.random.seed(seed)
        return self.np.random.triangular(low, mode, high, size)

    def calculate_percentile(self, data: Any, percentile: float) -> float:
        return float(self.np.percentile(data, percentile))

    def mean(self, data: Any) -> float:
        return float(self.np.mean(data))

    def std(self, data: Any) -> float:
        return float(self.np.std(data))

    def histogram(self, data: Any, bins: int = 50) -> Tuple[List[float], List[float]]:
        hist, edges = self.np.histogram(data, bins=bins, density=True)
        return hist.tolist(), edges.tolist()

    def to_cpu(self, data: Any) -> Any:
        return data


class CuPyBackend(ComputeBackendBase):
    """CuPy GPU 后端"""

    def __init__(self):
        import cupy as cp
        self.cp = cp
        self.name = "CuPy GPU"

        # 获取 GPU 信息
        try:
            device = cp.cuda.Device()
            self.gpu_name = f"CUDA {device.compute_capability}"
        except:
            self.gpu_name = "Unknown GPU"

    def random_normal(self, size: int, mean: float, std: float, seed: int = None) -> Any:
        if seed is not None:
            self.cp.random.seed(seed)
        return self.cp.random.normal(mean, std, size)

    def random_lognormal(self, size: int, mean: float, std: float, seed: int = None) -> Any:
        if seed is not None:
            self.cp.random.seed(seed)
        return self.cp.random.lognormal(mean, std, size)

    def random_triangular(self, size: int, low: float, high: float, mode: float, seed: int = None) -> Any:
        if seed is not None:
            self.cp.random.seed(seed)
        # CuPy 没有直接的 triangular，使用公式生成
        u = self.cp.random.random(size)
        # 使用逆变换采样
        c = (mode - low) / (high - low)
        result = self.cp.where(
            u <= c,
            low + self.cp.sqrt(u * (high - low) * (mode - low)),
            high - self.cp.sqrt((1 - u) * (high - low) * (high - mode))
        )
        return result

    def calculate_percentile(self, data: Any, percentile: float) -> float:
        return float(self.cp.percentile(data, percentile))

    def mean(self, data: Any) -> float:
        return float(self.cp.mean(data))

    def std(self, data: Any) -> float:
        return float(self.cp.std(data))

    def histogram(self, data: Any, bins: int = 50) -> Tuple[List[float], List[float]]:
        hist, edges = self.cp.histogram(data, bins=bins)
        return hist.tolist(), edges.tolist()

    def to_cpu(self, data: Any) -> Any:
        return self.cp.asnumpy(data)


class PyTorchBackend(ComputeBackendBase):
    """PyTorch GPU 后端"""

    def __init__(self):
        import torch
        self.torch = torch
        self.device = torch.device("cuda:0")
        self.name = f"PyTorch GPU ({torch.cuda.get_device_name(0)})"

    def random_normal(self, size: int, mean: float, std: float, seed: int = None) -> Any:
        if seed is not None:
            self.torch.manual_seed(seed)
        return self.torch.normal(mean, std, (size,), device=self.device)

    def random_lognormal(self, size: int, mean: float, std: float, seed: int = None) -> Any:
        if seed is not None:
            self.torch.manual_seed(seed)
        # lognormal = exp(normal)
        normal = self.torch.normal(mean, std, (size,), device=self.device)
        return self.torch.exp(normal)

    def random_triangular(self, size: int, low: float, high: float, mode: float, seed: int = None) -> Any:
        if seed is not None:
            self.torch.manual_seed(seed)
        # 使用逆变换采样
        u = self.torch.rand(size, device=self.device)
        c = (mode - low) / (high - low)
        result = self.torch.where(
            u <= c,
            low + self.torch.sqrt(u * (high - low) * (mode - low)),
            high - self.torch.sqrt((1 - u) * (high - low) * (high - mode))
        )
        return result

    def calculate_percentile(self, data: Any, percentile: float) -> float:
        return float(self.torch.quantile(data, percentile / 100.0))

    def mean(self, data: Any) -> float:
        return float(self.torch.mean(data.float()))

    def std(self, data: Any) -> float:
        return float(self.torch.std(data.float()))

    def histogram(self, data: Any, bins: int = 50) -> Tuple[List[float], List[float]]:
        hist = self.torch.histc(data.float(), bins=bins)
        # 计算边
        min_val = float(self.torch.min(data.float()))
        max_val = float(self.torch.max(data.float()))
        edges = self.torch.linspace(min_val, max_val, bins + 1)
        return hist.tolist(), edges.tolist()

    def to_cpu(self, data: Any) -> Any:
        return data.cpu().numpy()


# =============================================================================
# 蒙特卡洛引擎
# =============================================================================

class MonteCarloEngine:
    """
    蒙特卡洛金融工程引擎

    支持 GPU 加速的大规模并行模拟
    """

    def __init__(self, config: Dict = None):
        """初始化引擎"""
        self.config = config or MONTE_CARLO_CONFIG
        self.backend: Optional[ComputeBackendBase] = None
        self.backend_type: Optional[ComputeBackend] = None
        self._init_backend()

    def _init_backend(self):
        """初始化计算后端"""
        backend_type, message = detect_gpu_backend()
        self.backend_type = backend_type

        if backend_type == ComputeBackend.CUPY:
            self.backend = CuPyBackend()
            logger.info(f"[蒙特卡洛] GPU 后端初始化: {message}")
        elif backend_type == ComputeBackend.PYTORCH:
            self.backend = PyTorchBackend()
            logger.info(f"[蒙特卡洛] GPU 后端初始化: {message}")
        else:
            self.backend = NumPyBackend()
            logger.info(f"[蒙特卡洛] CPU 后端初始化: {message}")

    def simulate(self, inputs: SimulationInput) -> SimulationResult:
        """
        执行蒙特卡洛模拟

        Args:
            inputs: 模拟输入参数

        Returns:
            SimulationResult 模拟结果
        """
        start_time = time.time()
        num_sims = inputs.num_simulations

        logger.info(
            f"[蒙特卡洛] 开始模拟: {inputs.ticker}, "
            f"模拟次数={num_sims}, "
            f"后端={self.backend.name}"
        )

        # 1. 生成随机参数
        growth_rates = self._generate_random(
            inputs.revenue_growth, num_sims
        )
        discount_rates = self._generate_random(
            inputs.discount_rate, num_sims
        )
        terminal_multiples = self._generate_random(
            inputs.terminal_multiple, num_sims
        )
        profit_margins = self._generate_random(
            inputs.profit_margin, num_sims
        )

        # 2. 计算估值（并行）
        valuations = self._calculate_valuations(
            inputs.current_price,
            growth_rates,
            discount_rates,
            terminal_multiples,
            profit_margins,
            inputs.time_horizon,
        )

        # 3. 应用地缘政治风险调整
        if inputs.geopolitical_risk > 0:
            valuations = self._apply_tail_risk(
                valuations, inputs.geopolitical_risk
            )

        # 4. 计算统计数据
        result = self._compute_statistics(
            inputs, valuations, start_time
        )

        logger.info(
            f"[蒙特卡洛] 模拟完成: 耗时={result.compute_time_ms:.0f}ms, "
            f"均值={result.mean_value:.2f}, "
            f"95% VaR={result.var_95:.2f}"
        )

        return result

    def _generate_random(
        self,
        params: DistributionParams,
        size: int
    ) -> Any:
        """生成随机数"""
        seed = self.config.get("random_seed")

        if params.distribution_type == "normal":
            return self.backend.random_normal(size, params.mean, params.std, seed)
        elif params.distribution_type == "lognormal":
            return self.backend.random_lognormal(size, params.mean, params.std, seed)
        elif params.distribution_type == "triangular":
            return self.backend.random_triangular(size, params.low, params.high, params.mode, seed)
        else:
            # 默认正态分布
            return self.backend.random_normal(size, params.mean, params.std, seed)

    def _calculate_valuations(
        self,
        current_price: float,
        growth_rates: Any,
        discount_rates: Any,
        terminal_multiples: Any,
        profit_margins: Any,
        time_horizon: int,
    ) -> Any:
        """
        计算估值（DCF 模型的蒙特卡洛版本）

        使用向量化的并行计算
        """
        # 使用后端特定的计算
        if self.backend_type == ComputeBackend.CUPY:
            import cupy as cp
            # 现金流预测
            cash_flows = current_price * (1 + growth_rates) * profit_margins

            # 折现因子
            discount_factors = 1 / (1 + discount_rates) ** time_horizon

            # 终值
            terminal_values = cash_flows * terminal_multiples * discount_factors

            # 总估值
            valuations = cash_flows * discount_factors + terminal_values

            return valuations

        elif self.backend_type == ComputeBackend.PYTORCH:
            import torch
            # 现金流预测
            cash_flows = current_price * (1 + growth_rates) * profit_margins

            # 折现因子
            discount_factors = 1 / (1 + discount_rates) ** time_horizon

            # 终值
            terminal_values = cash_flows * terminal_multiples * discount_factors

            # 总估值
            valuations = cash_flows * discount_factors + terminal_values

            return valuations

        else:
            # NumPy
            import numpy as np
            cash_flows = current_price * (1 + growth_rates) * profit_margins
            discount_factors = 1 / (1 + discount_rates) ** time_horizon
            terminal_values = cash_flows * terminal_multiples * discount_factors
            valuations = cash_flows * discount_factors + terminal_values
            return valuations

    def _apply_tail_risk(self, valuations: Any, risk_prob: float) -> Any:
        """
        应用地缘政治长尾风险

        以一定概率将估值大幅降低
        """
        if self.backend_type == ComputeBackend.CUPY:
            import cupy as cp
            risk_mask = cp.random.random(len(valuations)) < risk_prob
            # 极端情况下估值下跌 50-80%
            crash_factor = cp.random.uniform(0.2, 0.5, len(valuations))
            return cp.where(risk_mask, valuations * crash_factor, valuations)

        elif self.backend_type == ComputeBackend.PYTORCH:
            import torch
            risk_mask = torch.rand(len(valuations), device=valuations.device) < risk_prob
            crash_factor = torch.rand(len(valuations), device=valuations.device) * 0.3 + 0.2
            return torch.where(risk_mask, valuations * crash_factor, valuations)

        else:
            import numpy as np
            risk_mask = np.random.random(len(valuations)) < risk_prob
            crash_factor = np.random.uniform(0.2, 0.5, len(valuations))
            return np.where(risk_mask, valuations * crash_factor, valuations)

    def _compute_statistics(
        self,
        inputs: SimulationInput,
        valuations: Any,
        start_time: float
    ) -> SimulationResult:
        """计算统计结果"""
        # 转换到 CPU 进行统计
        valuations_cpu = self.backend.to_cpu(valuations)

        # 基础统计
        mean_val = self.backend.mean(valuations)
        std_val = self.backend.std(valuations)

        # 分位数
        percentiles = {}
        for p in [5, 10, 25, 50, 75, 90, 95]:
            percentiles[f"p{p}"] = self.backend.calculate_percentile(valuations, p)

        # VaR (Value at Risk) - 95% 和 99%
        var_95 = self.backend.calculate_percentile(valuations, 5)  # 5% 分位数
        var_99 = self.backend.calculate_percentile(valuations, 1)  # 1% 分位数

        # Expected Shortfall (条件尾部期望)
        # 低于 VaR 的值的平均
        if self.backend_type == ComputeBackend.CUPY:
            import cupy as cp
            es_95 = float(cp.mean(valuations[valuations <= var_95]))
            es_99 = float(cp.mean(valuations[valuations <= var_99]))
        elif self.backend_type == ComputeBackend.PYTORCH:
            import torch
            es_95 = float(torch.mean(valuations[valuations <= var_95].float()))
            es_99 = float(torch.mean(valuations[valuations <= var_99].float()))
        else:
            import numpy as np
            es_95 = float(np.mean(valuations_cpu[valuations_cpu <= var_95]))
            es_99 = float(np.mean(valuations_cpu[valuations_cpu <= var_99]))

        # 概率分析
        if self.backend_type == ComputeBackend.CUPY:
            import cupy as cp
            prob_above_current = float(cp.sum(valuations > inputs.current_price) / len(valuations))
            prob_above_mean = float(cp.sum(valuations > mean_val) / len(valuations))
            # 长尾风险：低于当前价格 50% 的概率
            tail_threshold = inputs.current_price * 0.5
            tail_risk_prob = float(cp.sum(valuations < tail_threshold) / len(valuations))
        elif self.backend_type == ComputeBackend.PYTORCH:
            import torch
            prob_above_current = float(torch.sum(valuations > inputs.current_price) / len(valuations))
            prob_above_mean = float(torch.sum(valuations > mean_val) / len(valuations))
            tail_threshold = inputs.current_price * 0.5
            tail_risk_prob = float(torch.sum(valuations < tail_threshold) / len(valuations))
        else:
            import numpy as np
            prob_above_current = float(np.sum(valuations_cpu > inputs.current_price) / len(valuations_cpu))
            prob_above_mean = float(np.sum(valuations_cpu > mean_val) / len(valuations_cpu))
            tail_threshold = inputs.current_price * 0.5
            tail_risk_prob = float(np.sum(valuations_cpu < tail_threshold) / len(valuations_cpu))

        # 置信区间
        confidence_intervals = {}
        for level in self.config["confidence_levels"]:
            lower_p = (1 - level) / 2 * 100
            upper_p = (1 + level) / 2 * 100
            confidence_intervals[level] = (
                self.backend.calculate_percentile(valuations, lower_p),
                self.backend.calculate_percentile(valuations, upper_p),
            )

        # 直方图（用于可视化）
        hist, edges = self.backend.histogram(valuations, bins=50)

        # 计算时间
        compute_time_ms = (time.time() - start_time) * 1000

        # GPU 信息
        gpu_used = self.backend_type in [ComputeBackend.CUPY, ComputeBackend.PYTORCH]
        gpu_name = getattr(self.backend, 'gpu_name', '') if gpu_used else ''
        parallel_threads = inputs.num_simulations if gpu_used else self.config["cpu_num_processes"]

        return SimulationResult(
            ticker=inputs.ticker,
            num_simulations=inputs.num_simulations,
            compute_time_ms=compute_time_ms,
            backend=self.backend.name,
            mean_value=mean_val,
            median_value=percentiles["p50"],
            std_value=std_val,
            min_value=float(min(valuations_cpu)) if hasattr(valuations_cpu, '__iter__') else float(valuations_cpu),
            max_value=float(max(valuations_cpu)) if hasattr(valuations_cpu, '__iter__') else float(valuations_cpu),
            percentiles=percentiles,
            var_95=var_95,
            var_99=var_99,
            expected_shortfall_95=es_95,
            expected_shortfall_99=es_99,
            prob_above_current=prob_above_current,
            prob_above_mean=prob_above_mean,
            tail_risk_probability=tail_risk_prob,
            confidence_intervals=confidence_intervals,
            distribution_histogram=hist,
            bin_edges=edges,
            gpu_used=gpu_used,
            gpu_name=gpu_name,
            parallel_threads=parallel_threads,
        )


# =============================================================================
# 全局单例
# =============================================================================

_monte_carlo_engine: Optional[MonteCarloEngine] = None


def get_monte_carlo_engine() -> MonteCarloEngine:
    """获取全局蒙特卡洛引擎实例"""
    global _monte_carlo_engine
    if _monte_carlo_engine is None:
        _monte_carlo_engine = MonteCarloEngine()
    return _monte_carlo_engine


# =============================================================================
# 便捷函数
# =============================================================================

def run_monte_carlo_simulation(
    ticker: str,
    current_price: float,
    growth_mean: float = 0.10,
    growth_std: float = 0.05,
    discount_mean: float = 0.12,
    discount_std: float = 0.02,
    terminal_mean: float = 10.0,
    terminal_std: float = 2.0,
    margin_mean: float = 0.15,
    margin_std: float = 0.03,
    geopolitical_risk: float = 0.0,
    num_simulations: int = 100000,
) -> SimulationResult:
    """
    运行蒙特卡洛模拟（便捷函数）

    Args:
        ticker: 股票代码
        current_price: 当前价格
        growth_mean: 增长率均值
        growth_std: 增长率标准差
        discount_mean: 折现率均值
        discount_std: 折现率标准差
        terminal_mean: 终端倍数均值
        terminal_std: 终端倍数标准差
        margin_mean: 利润率均值
        margin_std: 利润率标准差
        geopolitical_risk: 地缘政治风险 (0-1)
        num_simulations: 模拟次数

    Returns:
        SimulationResult 模拟结果
    """
    engine = get_monte_carlo_engine()

    inputs = SimulationInput(
        ticker=ticker,
        current_price=current_price,
        revenue_growth=DistributionParams(
            distribution_type="normal",
            mean=growth_mean,
            std=growth_std,
        ),
        discount_rate=DistributionParams(
            distribution_type="normal",
            mean=discount_mean,
            std=discount_std,
        ),
        terminal_multiple=DistributionParams(
            distribution_type="normal",
            mean=terminal_mean,
            std=terminal_std,
        ),
        profit_margin=DistributionParams(
            distribution_type="normal",
            mean=margin_mean,
            std=margin_std,
        ),
        geopolitical_risk=geopolitical_risk,
        num_simulations=num_simulations,
    )

    return engine.simulate(inputs)


# =============================================================================
# 测试
# =============================================================================

def test_monte_carlo():
    """测试蒙特卡洛引擎"""
    print("=" * 60)
    print("AI TradeBot - 蒙特卡洛引擎测试")
    print("=" * 60)

    # 检测后端
    backend_type, message = detect_gpu_backend()
    print(f"\n计算后端: {message}")

    # 运行模拟
    result = run_monte_carlo_simulation(
        ticker="600000.SH",
        current_price=95.0,
        growth_mean=0.10,
        growth_std=0.05,
        discount_mean=0.12,
        discount_std=0.02,
        terminal_mean=10.0,
        terminal_std=2.0,
        margin_mean=0.15,
        margin_std=0.03,
        geopolitical_risk=0.05,
        num_simulations=100000,
    )

    print(f"\n{'='*60}")
    print("模拟结果")
    print(f"{'='*60}")
    print(f"标的: {result.ticker}")
    print(f"模拟次数: {result.num_simulations:,}")
    print(f"计算时间: {result.compute_time_ms:.0f}ms")
    print(f"后端: {result.backend}")
    print(f"GPU 使用: {'是' if result.gpu_used else '否'}")

    print(f"\n【估值分布】")
    print(f"  均值: {result.mean_value:.2f}")
    print(f"  中位数: {result.median_value:.2f}")
    print(f"  标准差: {result.std_value:.2f}")
    print(f"  范围: {result.min_value:.2f} - {result.max_value:.2f}")

    print(f"\n【风险指标】")
    print(f"  95% VaR: {result.var_95:.2f}")
    print(f"  99% VaR: {result.var_99:.2f}")
    print(f"  95% ES: {result.expected_shortfall_95:.2f}")
    print(f"  99% ES: {result.expected_shortfall_99:.2f}")

    print(f"\n【概率分析】")
    print(f"  高于当前价格概率: {result.prob_above_current*100:.1f}%")
    print(f"  长尾风险概率: {result.tail_risk_probability*100:.2f}%")

    print(f"\n【95% 置信区间】")
    ci = result.confidence_intervals.get(0.95, (0, 0))
    print(f"  {ci[0]:.2f} - {ci[1]:.2f}")

    # 投资建议
    if result.prob_above_current > 0.7:
        recommendation = "当前价格处于低估值区间，胜率较高"
    elif result.prob_above_current > 0.5:
        recommendation = "当前价格处于合理区间"
    else:
        recommendation = "当前价格可能被高估，需谨慎"

    print(f"\n【投资建议】{recommendation}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    test_monte_carlo()
