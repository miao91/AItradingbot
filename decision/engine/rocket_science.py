"""
AI TradeBot - 火箭科学级金融工程引擎

核心特性：
1. 跳跃-扩散概率建模 (Merton Jump-Diffusion)
2. 宏观因子灵敏度矩阵 (Sensitivity Stress Test)
3. 尾部风险度量 (VaR + Expected Shortfall)
4. GPU 加速 (CuPy/CUDA 优化)

性能要求：
- 蒙特卡洛迭代 >= 100,000 次
- RTX 5080 上秒级渲染
"""
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import warnings

from shared.logging import get_logger

# 尝试导入 CuPy (GPU 加速)
try:
    import cupy as cp
    GPU_AVAILABLE = True
except ImportError:
    cp = None
    GPU_AVAILABLE = False

warnings.filterwarnings('ignore')
logger = get_logger(__name__)


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class JumpDiffusionParams:
    """跳跃-扩散模型参数"""
    # 基础参数
    S0: float = 100.0  # 初始价格
    mu: float = 0.05    # 漂移率 (年化)
    sigma: float = 0.25  # 波动率 (年化)

    # 跳跃参数 (泊松过程)
    lambda_jump: float = 0.5    # 年化跳跃频率
    mu_jump: float = -0.05      # 跳跃幅度均值 (负值表示下跌)
    sigma_jump: float = 0.08    # 跳跃幅度波动

    # 模拟参数
    T: float = 1/365    # 时间跨度 (1天)
    n_steps: int = 24   # 时间步数 (小时)
    n_sims: int = 100000  # 模拟次数


@dataclass
class SensitivityMatrix:
    """灵敏度矩阵结果"""
    industry_variable_range: np.ndarray  # 行业变量范围
    macro_variable_range: np.ndarray    # 宏观变量范围
    valuation_matrix: np.ndarray        # 估值矩阵 (2D)
    gradient_matrix: np.ndarray         # 一阶导数矩阵
    hessian_matrix: np.ndarray          # 二阶导数矩阵 (凸性)
    critical_points: List[Dict]         # 临界点列表


@dataclass
class TailRiskMetrics:
    """尾部风险度量"""
    var_95: float      # 95% VaR
    var_99: float      # 99% VaR
    es_95: float       # 95% Expected Shortfall
    es_99: float       # 99% Expected Shortfall
    max_drawdown: float  # 最大回撤
    jump_probability: float  # 跳跃概率
    crash_probability: float  # 崩盘概率 (>10% 下跌)


@dataclass
class ValuationCloud:
    """估值云图数据"""
    prices: np.ndarray       # 价格分布
    probabilities: np.ndarray  # 概率密度
    bullish_peak: float      # 乐观峰值
    neutral_peak: float      # 中性峰值
    bearish_peak: float      # 悲观峰值
    confidence_intervals: Dict[str, Tuple[float, float]]


# =============================================================================
# 跳跃-扩散模型 (Merton Jump-Diffusion)
# =============================================================================

class JumpDiffusionEngine:
    """
    跳跃-扩散概率建模引擎

    Merton (1976) 模型：
    dS/S = (μ - λκ)dt + σdW + (J-1)dN

    其中：
    - μ: 漂移率
    - σ: 波动率
    - λ: 跳跃强度 (泊松过程参数)
    - J: 跳跃幅度
    - κ = E[J-1]: 跳跃补偿项
    """

    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu and GPU_AVAILABLE
        if self.use_gpu:
            logger.info("[跳跃-扩散] 使用 CuPy GPU 加速")
        else:
            logger.info("[跳跃-扩散] 使用 NumPy CPU 计算")

    def simulate(
        self,
        params: JumpDiffusionParams,
    ) -> np.ndarray:
        """
        执行跳跃-扩散模拟

        Returns:
            shape: (n_sims, n_steps+1) 的价格路径矩阵
        """
        xp = cp if self.use_gpu else np

        S0 = params.S0
        mu = params.mu
        sigma = params.sigma
        lambda_jump = params.lambda_jump
        mu_jump = params.mu_jump
        sigma_jump = params.sigma_jump
        T = params.T
        n_steps = params.n_steps
        n_sims = params.n_sims

        dt = T / n_steps

        # 初始化价格矩阵
        S = xp.zeros((n_sims, n_steps + 1))
        S[:, 0] = S0

        # 预生成随机数 (并行优化)
        xp.random.seed(42)

        # 布朗运动增量
        dW = xp.random.normal(0, 1, (n_sims, n_steps)) * xp.sqrt(dt)

        # 跳跃计数 (泊松过程)
        jump_counts = xp.random.poisson(lambda_jump * dt, (n_sims, n_steps))

        # 跳跃幅度
        jump_sizes = xp.random.normal(mu_jump, sigma_jump, (n_sims, n_steps))
        jump_sizes = xp.where(jump_counts > 0, jump_sizes, 0)

        # 漂移补偿
        kappa = xp.exp(mu_jump + 0.5 * sigma_jump**2) - 1
        drift = (mu - lambda_jump * kappa - 0.5 * sigma**2) * dt

        # 模拟路径
        for t in range(n_steps):
            log_return = drift + sigma * dW[:, t] + jump_sizes[:, t]
            S[:, t+1] = S[:, t] * xp.exp(log_return)

        # 如果使用 GPU，转回 CPU
        if self.use_gpu:
            S = cp.asnumpy(S)

        return S

    def compute_jump_probability(
        self,
        paths: np.ndarray,
        threshold: float = -0.05,
        within_hours: int = 24,
    ) -> float:
        """
        计算指定阈值内跳跃的概率

        Args:
            paths: 价格路径 (n_sims, n_steps+1)
            threshold: 跳跃阈值 (负值表示下跌)
            within_hours: 时间窗口 (小时)

        Returns:
            跳跃概率
        """
        # 计算收益率
        returns = (paths[:, -1] - paths[:, 0]) / paths[:, 0]

        # 计算跳跃概率
        jump_prob = np.mean(returns < threshold)

        return float(jump_prob)

    def compute_tail_risk(
        self,
        paths: np.ndarray,
    ) -> TailRiskMetrics:
        """
        计算尾部风险指标

        包括 VaR, Expected Shortfall, 最大回撤等
        """
        # 最终价格分布
        final_prices = paths[:, -1]
        initial_price = paths[0, 0]

        # 收益率分布
        returns = (final_prices - initial_price) / initial_price

        # VaR (风险价值)
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)

        # Expected Shortfall (条件尾部期望)
        es_95 = returns[returns <= var_95].mean()
        es_99 = returns[returns <= var_99].mean()

        # 最大回撤
        cummax = np.maximum.accumulate(paths, axis=1)
        drawdowns = (paths - cummax) / cummax
        max_drawdown = drawdowns.min()

        # 跳跃概率 (>5% 单日波动)
        jump_prob = np.mean(np.abs(returns) > 0.05)

        # 崩盘概率 (>10% 下跌)
        crash_prob = np.mean(returns < -0.10)

        return TailRiskMetrics(
            var_95=float(var_95),
            var_99=float(var_99),
            es_95=float(es_95),
            es_99=float(es_99),
            max_drawdown=float(max_drawdown),
            jump_probability=float(jump_prob),
            crash_probability=float(crash_prob),
        )


# =============================================================================
# 宏观因子灵敏度矩阵
# =============================================================================

class SensitivityAnalyzer:
    """
    宏观因子灵敏度分析器

    计算估值对宏观变量的：
    - 一阶导数 (灵敏度)
    - 二阶导数 (凸性/加速度)
    """

    # 宏观变量定义
    MACRO_VARIABLES = {
        "DXY": {
            "name": "美元指数",
            "base_value": 104.0,
            "range": (96, 112),
            "step": 2,
        },
        "USDCNH": {
            "name": "离岸人民币",
            "base_value": 7.0,
            "range": (6.8, 7.6),
            "step": 0.1,
        },
        "US10Y": {
            "name": "十年期美债收益率",
            "base_value": 4.0,
            "range": (3.0, 5.5),
            "step": 0.25,
        },
    }

    def __init__(self):
        pass

    def generate_sensitivity_matrix(
        self,
        base_valuation: float,
        industry_variable: str = "成本变动",
        industry_range: Tuple[float, float] = (-0.20, 0.20),
        industry_steps: int = 9,
        macro_variable: str = "USDCNH",
    ) -> SensitivityMatrix:
        """
        生成二维灵敏度矩阵

        Args:
            base_valuation: 基准估值
            industry_variable: 行业变量名称
            industry_range: 行业变量范围
            industry_steps: 行业变量步数
            macro_variable: 宏观变量名称

        Returns:
            SensitivityMatrix 灵敏度矩阵
        """
        # 行业变量网格
        ind_values = np.linspace(
            industry_range[0],
            industry_range[1],
            industry_steps
        )

        # 宏观变量网格
        macro_config = self.MACRO_VARIABLES.get(macro_variable, self.MACRO_VARIABLES["USDCNH"])
        macro_values = np.arange(
            macro_config["range"][0],
            macro_config["range"][1] + macro_config["step"],
            macro_config["step"]
        )

        # 初始化估值矩阵
        n_ind = len(ind_values)
        n_macro = len(macro_values)
        valuation_matrix = np.zeros((n_ind, n_macro))

        # 填充估值矩阵 (简化模型)
        for i, ind in enumerate(ind_values):
            for j, macro in enumerate(macro_values):
                # 非线性估值模型
                macro_deviation = (macro - macro_config["base_value"]) / macro_config["base_value"]

                # 一阶效应
                valuation = base_valuation * (1 + ind * 0.8)

                # 二阶效应 (凸性)
                valuation *= (1 - macro_deviation**2 * 0.5)

                # 交叉效应
                valuation *= (1 + ind * macro_deviation * 0.3)

                valuation_matrix[i, j] = max(0, valuation)

        # 计算梯度矩阵 (一阶导数)
        gradient_matrix = np.gradient(valuation_matrix, ind_values, macro_values)

        # 计算 Hessian 矩阵 (二阶导数)
        hessian_ind = np.gradient(gradient_matrix[0], ind_values, axis=0)
        hessian_macro = np.gradient(gradient_matrix[1], macro_values, axis=1)

        hessian_matrix = {
            "d2V_dInd2": hessian_ind,
            "d2V_dMacro2": hessian_macro,
        }

        # 识别临界点
        critical_points = self._find_critical_points(
            valuation_matrix,
            ind_values,
            macro_values,
            industry_variable,
            macro_variable,
        )

        return SensitivityMatrix(
            industry_variable_range=ind_values,
            macro_variable_range=macro_values,
            valuation_matrix=valuation_matrix,
            gradient_matrix=gradient_matrix,
            hessian_matrix=hessian_matrix,
            critical_points=critical_points,
        )

    def _find_critical_points(
        self,
        matrix: np.ndarray,
        ind_values: np.ndarray,
        macro_values: np.ndarray,
        ind_name: str,
        macro_name: str,
    ) -> List[Dict]:
        """识别临界点"""
        critical_points = []

        # 寻找极值点
        for i in range(1, matrix.shape[0] - 1):
            for j in range(1, matrix.shape[1] - 1):
                # 局部最大值
                if (matrix[i, j] > matrix[i-1, j] and
                    matrix[i, j] > matrix[i+1, j] and
                    matrix[i, j] > matrix[i, j-1] and
                    matrix[i, j] > matrix[i, j+1]):
                    critical_points.append({
                        "type": "local_max",
                        "industry_value": float(ind_values[i]),
                        "macro_value": float(macro_values[j]),
                        "valuation": float(matrix[i, j]),
                        "description": f"局部高点: {ind_name}={ind_values[i]:.2%}, {macro_name}={macro_values[j]:.2f}",
                    })

                # 局部最小值
                if (matrix[i, j] < matrix[i-1, j] and
                    matrix[i, j] < matrix[i+1, j] and
                    matrix[i, j] < matrix[i, j-1] and
                    matrix[i, j] < matrix[i, j+1]):
                    critical_points.append({
                        "type": "local_min",
                        "industry_value": float(ind_values[i]),
                        "macro_value": float(macro_values[j]),
                        "valuation": float(matrix[i, j]),
                        "description": f"局部低点: {ind_name}={ind_values[i]:.2%}, {macro_name}={macro_values[j]:.2f}",
                    })

        return critical_points[:5]  # 返回前5个临界点


# =============================================================================
# 估值云图生成器
# =============================================================================

class ValuationCloudGenerator:
    """
    估值云图生成器

    基于蒙特卡洛模拟生成概率密度分布
    """

    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu and GPU_AVAILABLE

    def generate_cloud(
        self,
        paths: np.ndarray,
        n_bins: int = 100,
    ) -> ValuationCloud:
        """
        生成估值云图

        Args:
            paths: 蒙特卡洛路径
            n_bins: 直方图桶数

        Returns:
            ValuationCloud 云图数据
        """
        final_prices = paths[:, -1]

        # 计算概率密度
        hist, bin_edges = np.histogram(final_prices, bins=n_bins, density=True)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        # 平滑处理
        from scipy.ndimage import gaussian_filter1d
        probabilities = gaussian_filter1d(hist, sigma=2)

        # 归一化
        probabilities = probabilities / probabilities.sum()

        # 计算峰值
        sorted_indices = np.argsort(probabilities)[::-1]
        peaks = bin_centers[sorted_indices[:3]]

        # 置信区间
        confidence_intervals = {
            "95%": (float(np.percentile(final_prices, 2.5)), float(np.percentile(final_prices, 97.5))),
            "99%": (float(np.percentile(final_prices, 0.5)), float(np.percentile(final_prices, 99.5))),
        }

        return ValuationCloud(
            prices=bin_centers,
            probabilities=probabilities,
            bullish_peak=float(np.percentile(final_prices, 75)),
            neutral_peak=float(np.median(final_prices)),
            bearish_peak=float(np.percentile(final_prices, 25)),
            confidence_intervals=confidence_intervals,
        )


# =============================================================================
# 行业特定建模约束
# =============================================================================

INDUSTRY_MODELING_CONSTRAINTS = {
    "生物医药(创新药)": {
        "method": "rNPV",
        "probability_weights": {
            "Phase I": 0.10,
            "Phase II": 0.30,
            "Phase III": 0.60,
            "Filed": 0.85,
            "Approved": 1.00,
        },
        "description": "根据临床阶段设定成功概率权重",
    },

    "半导体/高成长": {
        "method": "Two_Stage_Growth",
        "high_growth_years": 5,
        "high_growth_rate_max": 0.30,
        "terminal_growth_cap": 0.03,  # 永续增长率锚定 GDP
        "description": "二阶段增长模型，永续增长率 <= 3%",
    },

    "资源/矿产": {
        "method": "Mean_Reversion",
        "reversion_speed": 0.3,
        "long_term_mean": 1.0,  # 标准化均值
        "volatility_of_variance": 0.5,
        "description": "均值回归模型，大宗商品价格从极端回落",
    },

    "银行/保险": {
        "method": "Book_Value",
        "roe_assumption_range": (0.08, 0.15),
        "dividend_payout_range": (0.30, 0.50),
        "description": "基于账面价值和 ROE",
    },
}


def get_industry_constraints(industry: str) -> Dict[str, Any]:
    """获取行业建模约束"""
    return INDUSTRY_MODELING_CONSTRAINTS.get(
        industry,
        {"method": "DCF", "description": "通用现金流折现模型"}
    )


# =============================================================================
# 便捷函数
# =============================================================================

async def run_jump_diffusion_analysis(
    S0: float,
    n_sims: int = 100000,
    lambda_jump: float = 0.5,
) -> Dict[str, Any]:
    """
    执行跳跃-扩散分析

    Args:
        S0: 初始价格
        n_sims: 模拟次数
        lambda_jump: 跳跃强度

    Returns:
        分析结果
    """
    params = JumpDiffusionParams(
        S0=S0,
        n_sims=n_sims,
        lambda_jump=lambda_jump,
    )

    engine = JumpDiffusionEngine(use_gpu=True)

    # 在线程池中执行计算密集型任务
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        paths = await loop.run_in_executor(
            executor,
            engine.simulate,
            params
        )

    tail_risk = engine.compute_tail_risk(paths)
    jump_prob = engine.compute_jump_probability(paths, threshold=-0.05)

    return {
        "paths": paths,
        "tail_risk": {
            "var_95": tail_risk.var_95,
            "var_99": tail_risk.var_99,
            "es_95": tail_risk.es_95,
            "es_99": tail_risk.es_99,
            "max_drawdown": tail_risk.max_drawdown,
            "jump_probability": tail_risk.jump_probability,
            "crash_probability": tail_risk.crash_probability,
        },
        "jump_5pct_probability": jump_prob,
        "n_simulations": n_sims,
        "gpu_accelerated": GPU_AVAILABLE,
    }


async def generate_sensitivity_heatmap(
    base_valuation: float,
    industry: str = "半导体/硬件",
    macro_variable: str = "USDCNH",
) -> Dict[str, Any]:
    """
    生成灵敏度热力图数据

    Args:
        base_valuation: 基准估值
        industry: 行业名称
        macro_variable: 宏观变量

    Returns:
        热力图数据
    """
    analyzer = SensitivityAnalyzer()

    result = analyzer.generate_sensitivity_matrix(
        base_valuation=base_valuation,
        industry_variable="成本变动",
        industry_range=(-0.20, 0.20),
        industry_steps=9,
        macro_variable=macro_variable,
    )

    return {
        "industry_range": result.industry_variable_range.tolist(),
        "macro_range": result.macro_variable_range.tolist(),
        "valuation_matrix": result.valuation_matrix.tolist(),
        "critical_points": result.critical_points,
        "industry_label": "成本变动",
        "macro_label": analyzer.MACRO_VARIABLES[macro_variable]["name"],
    }
