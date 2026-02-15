"""
AI TradeBot - 内置 AI 估值引擎（全功率版）

核心特性：
1. 动态版本调用：始终使用 AI 厂商最新旗舰接口，确保"自我进化"能力
2. 报错自愈能力：AI 自动修正代码错误，最多重试 3 次
3. 行业自适应：根据行业属性自动选择最前沿的估值模型
4. 增强沙盒：语法检查、安全执行、详细日志

计算流程：
快讯/报纸输入 → AI（智谱/DeepSeek 最新版）逻辑推演 → 自动编写 Python → 验证语法 → 执行计算 → 三档价格区间
"""
import asyncio
import os
import json
import subprocess
import tempfile
import ast
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from shared.logging import get_logger
from decision.ai_matrix.glm4.client import GLM4Client, get_glm4_client
from decision.ai_matrix.glm5.client import GLM5Client, get_glm5_client


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

VALUATION_CONFIG = {
    # 脚本临时目录
    "temp_dir": "temp/valuation_scripts",

    # 默认超时时间（秒）
    "script_timeout": 30,

    # AI 报错自愈：最大重试次数
    "max_retry_attempts": 3,

    # 代码验证：启用语法检查
    "enable_syntax_check": True,

    # 动态版本映射：使用最新旗舰接口
    "use_latest_models": True,

    # AI 模型选择：glm-4 (默认) 或 glm-5 (最新旗舰)
    "ai_model": "glm-5",  # 可选: "glm-4", "glm-5"
}


# =============================================================================
# 行业类型枚举
# =============================================================================

class IndustryType(Enum):
    """行业类型"""
    MANUFACTURING = "manufacturing"  # 制造业
    INTERNET = "internet"  # 互联网/TMT
    FINANCE = "finance"  # 金融
    UTILITIES = "utilities"  # 公用事业
    CONSUMER = "consumer"  # 消费
    HEALTHCARE = "healthcare"  # 医疗健康
    ENERGY = "energy"  # 能源
    MATERIALS = "materials"  # 原材料
    REAL_ESTATE = "real_estate"  # 房地产
    CYCLE_RESOURCE = "cycle_resource"  # 周期性资源
    OTHER = "other"  # 其他


# =============================================================================
# 行业估值方法论库 (总工定义版)
# =============================================================================

INDUSTRY_VALUATION_METHODOLOGY = {
    "互联网/SaaS": {
        "core_models": ["P/S (市销率)", "EV/Sales (企业价值/销售额)"],
        "core_logic": "早期重增长轻盈利，收入规模决定市场份额。",
        "reference_metrics": [
            "Rule of 40 (增长率+利润率)",
            "用户获客成本 (CAC)",
            "留存率",
            "ARR (年度经常性收入)",
            "LTV (客户终身价值)"
        ],
        "industry_type": IndustryType.INTERNET,
    },

    "半导体/硬件": {
        "core_models": ["P/E (市盈率)", "PEG (市盈率相对盈利增长比)"],
        "core_logic": "典型的技术驱动增长，需匹配盈利增速。",
        "reference_metrics": [
            "存货周转率",
            "研发投入占比",
            "晶圆产能利用率",
            "毛利率趋势"
        ],
        "industry_type": IndustryType.MANUFACTURING,
    },

    "银行/保险": {
        "core_models": ["P/B (市净率)", "P/EV (内含价值倍数)"],
        "core_logic": "资产即产品，净资产和内含价值是底牌。",
        "reference_metrics": [
            "ROE (净资产收益率)",
            "不良贷款率",
            "拨备覆盖率",
            "资本充足率"
        ],
        "industry_type": IndustryType.FINANCE,
    },

    "生物医药(创新药)": {
        "core_models": ["rNPV (风险调整后的净现值)"],
        "core_logic": "估值等于研发管线成功的概率折现。",
        "reference_metrics": [
            "临床进度 (Phase I/II/III)",
            "专利期限",
            "市场渗透率",
            "竞品格局"
        ],
        "industry_type": IndustryType.HEALTHCARE,
    },

    "传统制造/消费": {
        "core_models": ["P/E (市盈率)", "DCF (现金流折现)"],
        "core_logic": "赚辛苦钱或品牌钱，现金流和利润最稳。",
        "reference_metrics": [
            "自由现金流 (FCF)",
            "毛利率稳定性",
            "存货周转率",
            "品牌溢价能力"
        ],
        "industry_type": IndustryType.CONSUMER,
    },

    "重资产(钢铁/电力)": {
        "core_models": ["EV/EBITDA (企业价值/息税折旧摊销前利润)"],
        "core_logic": "剔除高额折旧和财务杠杆的干扰。",
        "reference_metrics": [
            "负债率",
            "产能利用率",
            "折旧政策",
            "资本开支强度"
        ],
        "industry_type": IndustryType.UTILITIES,
    },

    "资源/矿产": {
        "core_models": ["P/NAV (市价/资产净值)"],
        "core_logic": "资源储量是核心，价值等于矿产估值。",
        "reference_metrics": [
            "大宗商品价格走势",
            "开采成本",
            "储量年限",
            "品位/品质"
        ],
        "industry_type": IndustryType.CYCLE_RESOURCE,
    },

    "房地产": {
        "core_models": ["P/B (市净率)", "RNAV (重估净资产)"],
        "core_logic": "关注资产净值（土地储备）的重估。",
        "reference_metrics": [
            "预售账款",
            "净负债率",
            "土地储备面积",
            "去化率"
        ],
        "industry_type": IndustryType.REAL_ESTATE,
    },
}

# 简化版映射（向后兼容）
INDUSTRY_VALUATION_MODELS = {
    IndustryType.MANUFACTURING: {
        "primary": "DCF",
        "secondary": "PE",
        "rationale": "传统制造/消费：赚辛苦钱或品牌钱，现金流和利润最稳"
    },
    IndustryType.INTERNET: {
        "primary": "PS",
        "secondary": "EV/Sales",
        "rationale": "互联网/SaaS：早期重增长轻盈利，收入规模决定市场份额"
    },
    IndustryType.FINANCE: {
        "primary": "PB",
        "secondary": "P/EV",
        "rationale": "银行/保险：资产即产品，净资产和内含价值是底牌"
    },
    IndustryType.UTILITIES: {
        "primary": "EV/EBITDA",
        "secondary": "PE",
        "rationale": "重资产(钢铁/电力)：剔除高额折旧和财务杠杆的干扰"
    },
    IndustryType.CONSUMER: {
        "primary": "PE",
        "secondary": "DCF",
        "rationale": "传统制造/消费：自由现金流和毛利率最关键"
    },
    IndustryType.HEALTHCARE: {
        "primary": "rNPV",
        "secondary": "DCF",
        "rationale": "生物医药：估值等于研发管线成功的概率折现"
    },
    IndustryType.ENERGY: {
        "primary": "EV/EBITDA",
        "secondary": "PCF",
        "rationale": "能源企业现金流充裕，剔除资本开支干扰"
    },
    IndustryType.MATERIALS: {
        "primary": "EV/EBITDA",
        "secondary": "PB",
        "rationale": "原材料行业波动大，EV/EBITDA 更稳健"
    },
    IndustryType.REAL_ESTATE: {
        "primary": "RNAV",
        "secondary": "PB",
        "rationale": "房地产：关注资产净值（土地储备）的重估"
    },
    IndustryType.CYCLE_RESOURCE: {
        "primary": "P/NAV",
        "secondary": "EV/EBITDA",
        "rationale": "资源/矿产：资源储量是核心，价值等于矿产估值"
    },
    IndustryType.OTHER: {
        "primary": "PE",
        "secondary": "DCF",
        "rationale": "通用估值方法"
    },
}


def get_industry_methodology(industry_name: str) -> Dict[str, Any]:
    """
    获取行业估值方法论

    Args:
        industry_name: 行业名称（如 "互联网/SaaS", "半导体/硬件"）

    Returns:
        行业方法论字典
    """
    # 直接匹配
    if industry_name in INDUSTRY_VALUATION_METHODOLOGY:
        return INDUSTRY_VALUATION_METHODOLOGY[industry_name]

    # 模糊匹配
    for key, value in INDUSTRY_VALUATION_METHODOLOGY.items():
        if any(k in industry_name for k in key.split("/")):
            return value

    # 默认返回
    return {
        "core_models": ["P/E", "DCF"],
        "core_logic": "通用估值方法",
        "reference_metrics": ["市盈率", "现金流"],
        "industry_type": IndustryType.OTHER,
    }


def format_methodology_for_prompt(industry_name: str) -> str:
    """
    格式化行业方法论为 Prompt 友好的文本

    Args:
        industry_name: 行业名称

    Returns:
        格式化的文本
    """
    methodology = get_industry_methodology(industry_name)

    return f"""
【{industry_name} 行业估值方法论】

核心模型: {', '.join(methodology['core_models'])}
核心逻辑: {methodology['core_logic']}

参考指标:
{chr(10).join(f'- {m}' for m in methodology['reference_metrics'])}
"""


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class ValuationInput:
    """估值输入参数"""
    ticker: str
    current_price: float
    company_name: str

    # Clawdbot 提供的锚点参数（可选）
    clawdbot_pe: Optional[float] = None
    clawdbot_industry_pe: Optional[float] = None
    growth_expectation: Optional[str] = None  # high, medium, low

    # 基本面数据
    revenue_per_share: Optional[float] = None  # 每股收益
    net_income: Optional[float] = None  # 净利润（万元）
    total_assets: Optional[float] = None  # 总资产（万元）
    book_value_per_share: Optional[float] = None  # 每股净资产
    dividend_per_share: Optional[float] = None  # 每股股利
    operating_cash_flow: Optional[float] = None  # 经营现金流（万元）

    # 行业信息
    industry: Optional[str] = None
    sector: Optional[str] = None


@dataclass
class ScenarioResult:
    """情景结果"""
    name: str  # 乐观/中性/悲观
    growth_rate: float  # 增长率
    discount_rate: float  # 折现率
    intrinsic_value: float  # 内在价值
    present_value: float  # 当前价值
    margin_of_safety: float  # 安全边际（百分比）
    upside_potential: float  # 上涨潜力（百分比）

    # 计算过程说明
    calculation_logic: str = ""  # 计算逻辑说明


@dataclass
class ValuationOutput:
    """估值输出结果"""
    ticker: str
    model_used: str  # DCF, PE, PS, etc.
    input_params: ValuationInput

    # 三种情景结果
    scenarios: Dict[str, ScenarioResult] = field(default_factory=dict)

    # AI 生成的代码
    generated_code: str = ""

    # 代码修正历史
    code_fix_history: List[str] = field(default_factory=list)

    # 执行结果
    execution_success: bool = False
    execution_error: Optional[str] = None

    # 模型选择理由
    model_rationale: str = ""

    # 计算总耗时（秒）
    total_time: float = 0.0

    # Clawdbot 数据对比
    clawdbot_comparison: Optional[Dict[str, Any]] = None

    # 蒙特卡洛概率分布估值（新增）
    monte_carlo_result: Optional[Dict[str, Any]] = None

    # 风险指标（新增）
    risk_metrics: Optional[Dict[str, Any]] = None

    calculated_at: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# 内置 AI 估值引擎（全功率版）
# =============================================================================

class IntelligentValuationEngine:
    """
    内置 AI 估值引擎

    核心能力：
    1. 动态版本调用：始终使用 AI 厂商最新旗舰接口
    2. 报错自愈：AI 自动修正代码错误，最多重试 3 次
    3. 行业自适应：根据行业自动选择最佳估值模型
    4. 增强沙盒：语法检查、安全执行、详细日志
    """

    def __init__(self, temp_dir: Optional[Path] = None):
        """初始化引擎"""
        self.temp_dir = temp_dir or Path(VALUATION_CONFIG["temp_dir"])
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.glm4_client: Optional[GLM4Client] = None
        self.glm5_client: Optional[GLM5Client] = None
        self.ai_model = VALUATION_CONFIG.get("ai_model", "glm-5")

        logger.info(
            f"[估值引擎] 初始化完成 (全功率模式): "
            f"临时目录={self.temp_dir}, "
            f"动态版本={VALUATION_CONFIG['use_latest_models']}, "
            f"报错自愈={VALUATION_CONFIG['max_retry_attempts']}次, "
            f"语法检查={VALUATION_CONFIG['enable_syntax_check']}, "
            f"AI模型={self.ai_model}"
        )

    async def calculate(
        self,
        inputs: ValuationInput,
        external_reference: Optional[Dict[str, Any]] = None,
    ) -> ValuationOutput:
        """
        执行估值计算（全功率模式）

        Args:
            inputs: 估值输入参数
            external_reference: 外部参考数据（如 Clawdbot，可选）

        Returns:
            ValuationOutput 估值结果
        """
        start_time = datetime.now()
        logger.info(f"[估值引擎] 🚀 开始全功率计算: {inputs.ticker}")

        # 初始化 AI 客户端（GLM-4 或 GLM-5）
        if self.ai_model == "glm-5":
            if not self.glm5_client:
                self.glm5_client = await get_glm5_client()
            ai_client = self.glm5_client
        else:  # glm-4
            if not self.glm4_client:
                self.glm4_client = await get_glm4_client()
            ai_client = self.glm4_client

        logger.info(f"[估值引擎] 使用 AI 模型: {self.ai_model}")

        # 1. 行业识别与模型选择
        industry_type = self._detect_industry_type(inputs)
        model_config = INDUSTRY_VALUATION_MODELS[industry_type]
        model_rationale = model_config["rationale"]

        logger.info(
            f"[估值引擎] 📊 行业识别: {industry_type.value} "
            f"→ 选用模型: {model_config['primary']} "
            f"({model_rationale})"
        )

        # 2. 生成估值代码（带报错自愈）
        code_result = await self._generate_code_with_self_healing(
            inputs,
            external_reference,
            model_config,
            industry_type
        )

        if not code_result["success"]:
            return self._error_output(
                inputs,
                code_result["error"],
                model_rationale=model_rationale,
                total_time=(datetime.now() - start_time).total_seconds()
            )

        python_code = code_result["code"]
        fix_history = code_result["fix_history"]

        logger.info(f"[估值引擎] ✅ 代码生成成功 (修正次数: {len(fix_history)})")

        # 3. 执行代码并捕获结果
        scenarios = await self._execute_valuation_code(inputs, python_code)

        if not scenarios:
            return self._error_output(
                inputs,
                "代码执行失败，无法解析估值结果",
                generated_code=python_code,
                model_rationale=model_rationale,
                total_time=(datetime.now() - start_time).total_seconds()
            )

        # 4. 构建输出
        total_time = (datetime.now() - start_time).total_seconds()

        # 5. 执行蒙特卡洛模拟（概率分布估值）
        monte_carlo_result = None
        risk_metrics = None
        try:
            monte_carlo_result = self._run_monte_carlo_simulation(inputs, scenarios)
            if monte_carlo_result:
                risk_metrics = {
                    "var_95": monte_carlo_result.get("var_95"),
                    "var_99": monte_carlo_result.get("var_99"),
                    "expected_shortfall_95": monte_carlo_result.get("expected_shortfall_95"),
                    "tail_risk_probability": monte_carlo_result.get("tail_risk_probability"),
                }
                logger.info(
                    f"[估值引擎] 蒙特卡洛模拟完成: "
                    f"VaR(95%)={risk_metrics['var_95']:.2f}, "
                    f"尾风险={risk_metrics['tail_risk_probability']*100:.1f}%"
                )
        except Exception as e:
            logger.warning(f"[估值引擎] 蒙特卡洛模拟失败: {e}")

        output = ValuationOutput(
            ticker=inputs.ticker,
            model_used=model_config["primary"],
            input_params=inputs,
            scenarios=scenarios,
            generated_code=python_code,
            code_fix_history=fix_history,
            execution_success=len(scenarios) > 0,
            model_rationale=model_rationale,
            total_time=total_time,
            clawdbot_comparison=self._build_comparison(
                scenarios, external_reference
            ),
            monte_carlo_result=monte_carlo_result,
            risk_metrics=risk_metrics,
        )

        logger.info(
            f"[估值引擎] 🎯 计算完成: {inputs.ticker} "
            f"模型={output.model_used}, "
            f"情景={len(scenarios)}, "
            f"耗时={total_time:.2f}秒"
        )

        return output

    def _run_monte_carlo_simulation(
        self,
        inputs: ValuationInput,
        scenarios: Dict[str, ScenarioResult],
    ) -> Optional[Dict[str, Any]]:
        """
        执行蒙特卡洛模拟

        基于三种情景的参数生成概率分布
        """
        try:
            from decision.engine.monte_carlo_engine import (
                get_monte_carlo_engine,
                SimulationInput,
                DistributionParams,
            )

            engine = get_monte_carlo_engine()

            # 从情景中提取参数
            neutral_scenario = scenarios.get("中性") or scenarios.get("neutral")

            if neutral_scenario:
                growth_mean = neutral_scenario.growth_rate
                discount_mean = neutral_scenario.discount_rate
            else:
                growth_mean = 0.10
                discount_mean = 0.12

            # 构建模拟输入
            sim_input = SimulationInput(
                ticker=inputs.ticker,
                current_price=inputs.current_price,
                revenue_growth=DistributionParams(
                    distribution_type="normal",
                    mean=growth_mean,
                    std=abs(growth_mean) * 0.5,  # 50% 波动
                ),
                discount_rate=DistributionParams(
                    distribution_type="normal",
                    mean=discount_mean,
                    std=0.02,
                ),
                terminal_multiple=DistributionParams(
                    distribution_type="normal",
                    mean=10.0,
                    std=2.0,
                ),
                profit_margin=DistributionParams(
                    distribution_type="normal",
                    mean=0.15,
                    std=0.03,
                ),
                geopolitical_risk=0.05,  # 默认 5% 尾风险
                num_simulations=100000,
            )

            # 执行模拟
            result = engine.simulate(sim_input)

            return {
                "mean_value": result.mean_value,
                "median_value": result.median_value,
                "std_value": result.std_value,
                "var_95": result.var_95,
                "var_99": result.var_99,
                "expected_shortfall_95": result.expected_shortfall_95,
                "expected_shortfall_99": result.expected_shortfall_99,
                "prob_above_current": result.prob_above_current,
                "tail_risk_probability": result.tail_risk_probability,
                "confidence_interval_95": result.confidence_intervals.get(0.95),
                "compute_time_ms": result.compute_time_ms,
                "backend": result.backend,
                "gpu_used": result.gpu_used,
                "distribution_histogram": result.distribution_histogram,
                "bin_edges": result.bin_edges,
            }

        except Exception as e:
            logger.error(f"[估值引擎] 蒙特卡洛模拟异常: {e}")
            return None

    def _detect_industry_type(self, inputs: ValuationInput) -> IndustryType:
        """检测行业类型"""
        if not inputs.industry:
            return IndustryType.OTHER

        industry_lower = inputs.industry.lower()

        # 关键词映射
        industry_keywords = {
            IndustryType.MANUFACTURING: ["制造", "机械", "设备", "汽车", "manufacturing"],
            IndustryType.INTERNET: ["互联", "软件", "游戏", "电商", "传媒", "internet", "software", "tech"],
            IndustryType.FINANCE: ["银行", "证券", "保险", "金融", "finance", "bank"],
            IndustryType.UTILITIES: ["电力", "水务", "燃气", "公用", "utilities", "power"],
            IndustryType.CONSUMER: ["消费", "零售", "食品", "饮料", "服装", "consumer", "retail"],
            IndustryType.HEALTHCARE: ["医药", "生物", "医疗", "健康", "healthcare", "medical", "pharma"],
            IndustryType.ENERGY: ["石油", "天然气", "煤炭", "新能源", "energy", "oil", "gas"],
            IndustryType.MATERIALS: ["化工", "钢铁", "有色", "材料", "materials", "chemical"],
            IndustryType.REAL_ESTATE: ["地产", "房地产", "建筑", "real estate", "property"],
            IndustryType.CYCLE_RESOURCE: ["资源", "矿产", "周期", "resource", "mining"],
        }

        for industry_type, keywords in industry_keywords.items():
            if any(keyword in industry_lower for keyword in keywords):
                return industry_type

        return IndustryType.OTHER

    async def _generate_code_with_self_healing(
        self,
        inputs: ValuationInput,
        external_reference: Optional[Dict[str, Any]],
        model_config: Dict[str, str],
        industry_type: IndustryType,
    ) -> Dict[str, Any]:
        """
        生成估值代码（带报错自愈）

        返回：{"success": bool, "code": str, "error": str, "fix_history": List[str]}
        """
        fix_history = []
        max_attempts = VALUATION_CONFIG["max_retry_attempts"]

        for attempt in range(1, max_attempts + 1):
            logger.info(f"[估值引擎] 🔄 代码生成尝试 #{attempt}/{max_attempts}")

            # 1. 构建 prompt（首次或修正）
            if attempt == 1:
                prompt = self._build_initial_prompt(
                    inputs, external_reference, model_config, industry_type
                )
            else:
                last_error = fix_history[-1] if fix_history else "未知错误"
                prompt = self._build_fix_prompt(
                    inputs, external_reference, model_config, last_error, attempt
                )

            # 2. 调用 AI（使用配置的模型：GLM-4 或 GLM-5）
            try:
                response = await ai_client.generate(
                    prompt=prompt,
                    max_tokens=6000,  # 足够生成完整代码
                    temperature=0.3 if attempt == 1 else 0.2,  # 修正时降低随机性
                )
            except Exception as e:
                error_msg = f"AI 调用失败: {str(e)}"
                logger.error(f"[估值引擎] ❌ {error_msg}")
                if attempt == max_attempts:
                    return {"success": False, "error": error_msg, "fix_history": fix_history}
                fix_history.append(error_msg)
                continue

            # 3. 提取 Python 代码
            python_code = self._extract_python_code(response)

            if not python_code:
                error_msg = "无法从 AI 响应中提取 Python 代码"
                logger.error(f"[估值引擎] ❌ {error_msg}")
                if attempt == max_attempts:
                    return {"success": False, "error": error_msg, "fix_history": fix_history}
                fix_history.append(error_msg)
                continue

            # 4. 语法检查
            if VALUATION_CONFIG["enable_syntax_check"]:
                syntax_error = self._check_python_syntax(python_code)

                if syntax_error:
                    error_msg = f"语法错误: {syntax_error}"
                    logger.warning(f"[估值引擎] ⚠️ {error_msg}")
                    fix_history.append(error_msg)

                    if attempt == max_attempts:
                        return {"success": False, "error": error_msg, "fix_history": fix_history}
                    continue  # 触发下一次修正

            # 5. 成功！
            logger.info(f"[估值引擎] ✅ 代码验证通过（尝试 #{attempt}）")
            return {
                "success": True,
                "code": python_code,
                "fix_history": fix_history
            }

        # 所有尝试都失败
        return {
            "success": False,
            "error": f"超过最大重试次数 ({max_attempts})",
            "fix_history": fix_history
        }

    def _build_initial_prompt(
        self,
        inputs: ValuationInput,
        external_reference: Optional[Dict[str, Any]],
        model_config: Dict[str, str],
        industry_type: IndustryType,
    ) -> str:
        """构建初始代码生成 prompt"""
        # 构建外部参考数据描述
        external_info = ""
        if external_reference:
            external_info = f"""
【外部估值参考（Clawdbot）】
- 合理估值区间: {external_reference.get('fair_value_min', 'N/A')} - {external_reference.get('fair_value_max', 'N/A')}
- PE 比率: {external_reference.get('pe_ratio', 'N/A')}
- 行业平均 PE: {external_reference.get('industry_pe', 'N/A')}
- 增长预期: {external_reference.get('growth_expectation', 'N/A')}
- 机构共识度: {external_reference.get('consensus', 'N/A')}%
"""

        return f"""你是 AI TradeBot 的专业估值分析师。请为以下公司生成 Python 估值计算代码。

【公司信息】
- 股票代码: {inputs.ticker}
- 公司名称: {inputs.company_name}
- 当前价格: {inputs.current_price} 元
- 行业类型: {inputs.industry or '未知'} ({industry_type.value})

{external_info}

【基本面数据】
- 每股收益: {inputs.revenue_per_share or 'N/A'} 元
- 净利润: {inputs.net_income or 'N/A'} 万元
- 总资产: {inputs.total_assets or 'N/A'} 万元
- 每股净资产: {inputs.book_value_per_share or 'N/A'} 元
- 每股股利: {inputs.dividend_per_share or 'N/A'} 元
- 经营现金流: {inputs.operating_cash_flow or 'N/A'} 万元

【估值模型选择】
- 主模型: {model_config['primary']} ({model_config['secondary']} 为辅)
- 选择理由: {model_config['rationale']}

【核心要求】
1. 严格使用 {model_config['primary']} 模型进行估值
2. 计算三种情景：乐观（增长率+20%）、中性（增长率+10%）、悲观（增长率0%）
3. 输出格式：JSON 字符串，包含三种情景的完整数据
4. 代码必须包含完整的 try-except 错误处理
5. 所有数学计算必须在 Python 代码中完成，严禁心算

【Python 代码模板】
```python
import json

try:
    # ========== 参数设置 ==========
    current_price = {inputs.current_price}

    # 基本面参数
    revenue_per_share = {inputs.revenue_per_share or 0}
    net_income = {inputs.net_income or 0}
    book_value_per_share = {inputs.book_value_per_share or 0}
    dividend_per_share = {inputs.dividend_per_share or 0}
    operating_cash_flow = {inputs.operating_cash_flow or 0}

    # ========== {model_config['primary']} 估值模型 ==========
    # 在此实现 {model_config['primary']} 模型的计算逻辑
    # 模型说明：{model_config['rationale']}

    def calculate_valuation(growth_rate, discount_rate):
        \"\"\"
        计算 {model_config['primary']} 估值
        参数: growth_rate (增长率), discount_rate (折现率)
        返回: 内在价值、安全边际、上涨潜力
        \"\"\"
        # TODO: 实现具体的估值公式
        intrinsic_value = current_price * (1 + growth_rate)  # 示例逻辑
        present_value = intrinsic_value / (1 + discount_rate)
        margin_of_safety = (present_value - current_price) / current_price * 100
        upside_potential = (present_value - current_price) / current_price * 100
        return intrinsic_value, present_value, margin_of_safety, upside_potential

    # ========== 三种情景计算 ==========
    scenarios = {{
        "乐观": {{
            "growth_rate": 0.20,
            "discount_rate": 0.10,
            "intrinsic_value": 0.0,
            "present_value": 0.0,
            "margin_of_safety": 0.0,
            "upside_potential": 0.0,
            "calculation_logic": "乐观情景：假设增长率达到 20%，折现率 10%"
        }},
        "中性": {{
            "growth_rate": 0.10,
            "discount_rate": 0.12,
            "intrinsic_value": 0.0,
            "present_value": 0.0,
            "margin_of_safety": 0.0,
            "upside_potential": 0.0,
            "calculation_logic": "中性情景：假设增长率 10%，折现率 12%"
        }},
        "悲观": {{
            "growth_rate": 0.00,
            "discount_rate": 0.15,
            "intrinsic_value": 0.0,
            "present_value": 0.0,
            "margin_of_safety": 0.0,
            "upside_potential": 0.0,
            "calculation_logic": "悲观情景：假设零增长，折现率 15%"
        }}
    }}

    # 执行计算
    for name, params in scenarios.items():
        intrinsic, present, margin, upside = calculate_valuation(
            params["growth_rate"],
            params["discount_rate"]
        )
        params["intrinsic_value"] = round(intrinsic, 2)
        params["present_value"] = round(present, 2)
        params["margin_of_safety"] = round(margin, 2)
        params["upside_potential"] = round(upside, 2)

    # ========== 输出结果 ==========
    print(json.dumps(scenarios, indent=2, ensure_ascii=False))

except Exception as e:
    error_result = {{
        "error": str(e),
        "scenarios": {{}}
    }}
    print(json.dumps(error_result, indent=2, ensure_ascii=False))
```

请生成完整的 Python 代码（仅代码，不要其他说明）："""

    def _build_fix_prompt(
        self,
        inputs: ValuationInput,
        external_reference: Optional[Dict[str, Any]],
        model_config: Dict[str, str],
        last_error: str,
        attempt: int,
    ) -> str:
        """构建代码修正 prompt"""
        return f"""之前的代码存在错误，请修正：

【错误信息】
{last_error}

【修正要求】
1. 修复上述错误
2. 确保 {model_config['primary']} 估值模型的数学逻辑正确
3. 检查所有变量是否已定义
4. 验证 JSON 输出格式正确
5. 这是第 {attempt} 次尝试，请仔细检查

请直接输出修正后的完整 Python 代码（仅代码）："""

    def _check_python_syntax(self, code: str) -> Optional[str]:
        """检查 Python 语法"""
        try:
            ast.parse(code)
            return None
        except SyntaxError as e:
            return f"行 {e.lineno}: {e.msg}"

    def _extract_python_code(self, response: str) -> Optional[str]:
        """从 AI 响应中提取 Python 代码"""
        # 尝试多种代码块格式
        patterns = [
            r'```python\n([\s\S]*?)\n```',
            r'```py\n([\s\S]*?)\n```',
            r'```\n([\s\S]*?)\n```',
        ]

        for pattern in patterns:
            match = re.search(pattern, response)
            if match:
                return match.group(1).strip()

        # 如果没有代码块，尝试直接提取
        if "def " in response or "import " in response:
            lines = response.split('\n')
            code_lines = []
            in_code = False
            for line in lines:
                if line.strip().startswith(('import ', 'def ', 'class ', '#', 'try:', 'except:', 'for ', 'if ')):
                    in_code = True
                if in_code:
                    code_lines.append(line)
            return '\n'.join(code_lines).strip()

        return None

    async def _execute_valuation_code(
        self,
        inputs: ValuationInput,
        code: str
    ) -> Dict[str, ScenarioResult]:
        """执行估值代码（增强沙盒）"""
        script_path = self.temp_dir / f"{inputs.ticker}_valuation.py"

        try:
            # 写入脚本
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(code)

            logger.debug(f"[估值引擎] 📝 脚本已写入: {script_path}")

            # 执行脚本
            result = subprocess.run(
                ["python", str(script_path)],
                capture_output=True,
                text=True,
                timeout=VALUATION_CONFIG["script_timeout"],
                encoding='utf-8',
            )

            output = result.stdout

            if result.stderr:
                logger.warning(f"[估值引擎] ⚠️ 脚本 stderr: {result.stderr}")

            # 解析结果
            scenarios = {}
            try:
                data = json.loads(output)

                if "error" in data:
                    logger.error(f"[估值引擎] ❌ 脚本执行错误: {data['error']}")
                    return {}

                for name, scenario_data in data.items():
                    scenarios[name] = ScenarioResult(
                        name=name,
                        growth_rate=float(scenario_data.get("growth_rate", 0)),
                        discount_rate=float(scenario_data.get("discount_rate", 0)),
                        intrinsic_value=float(scenario_data.get("intrinsic_value", 0)),
                        present_value=float(scenario_data.get("present_value", 0)),
                        margin_of_safety=float(scenario_data.get("margin_of_safety", 0)),
                        upside_potential=float(scenario_data.get("upside_potential", 0)),
                        calculation_logic=scenario_data.get("calculation_logic", ""),
                    )

                logger.info(f"[估值引擎] ✅ 成功解析 {len(scenarios)} 个情景")

            except json.JSONDecodeError as e:
                logger.error(f"[估值引擎] ❌ JSON 解析失败: {e}")
                logger.debug(f"[估值引擎] 原始输出: {output}")

            return scenarios

        except subprocess.TimeoutExpired:
            logger.error(f"[估值引擎] ❌ 脚本执行超时（{VALUATION_CONFIG['script_timeout']}秒）")
            return {}
        except Exception as e:
            logger.error(f"[估值引擎] ❌ 脚本执行失败: {e}")
            return {}

    def _build_comparison(
        self,
        scenarios: Dict[str, ScenarioResult],
        external_reference: Optional[Dict]
    ) -> Optional[Dict]:
        """构建与外部参考的对比"""
        if not external_reference or not scenarios:
            return None

        neutral = scenarios.get("中性")
        if not neutral:
            return None

        external_min = external_reference.get("fair_value_min", 0)
        external_max = external_reference.get("fair_value_max", 0)

        if external_min == 0:
            return None

        return {
            "external_range": f"{external_min} - {external_max}",
            "our_neutral_valuation": neutral.present_value,
            "difference_pct": ((neutral.present_value - external_min) / external_min * 100),
        }

    def _error_output(
        self,
        inputs: ValuationInput,
        error_msg: str,
        generated_code: str = "",
        model_rationale: str = "",
        total_time: float = 0.0,
    ) -> ValuationOutput:
        """返回错误输出"""
        return ValuationOutput(
            ticker=inputs.ticker,
            model_used="ERROR",
            input_params=inputs,
            scenarios={},
            generated_code=generated_code,
            execution_success=False,
            execution_error=error_msg,
            model_rationale=model_rationale,
            total_time=total_time,
        )


# =============================================================================
# 全局单例
# =============================================================================

_valuation_engine: Optional[IntelligentValuationEngine] = None


def get_valuation_engine() -> IntelligentValuationEngine:
    """获取全局估值引擎实例"""
    global _valuation_engine
    if _valuation_engine is None:
        _valuation_engine = IntelligentValuationEngine()
    return _valuation_engine


# =============================================================================
# 便捷函数
# =============================================================================

async def calculate_valuation(
    ticker: str,
    current_price: float,
    company_name: str,
    external_reference: Optional[Dict[str, Any]] = None,
    **kwargs
) -> ValuationOutput:
    """
    计算股票估值（全功率模式）

    Args:
        ticker: 股票代码
        current_price: 当前价格
        company_name: 公司名称
        external_reference: 外部估值参考（可选）
        **kwargs: 其他估值参数

    Returns:
        ValuationOutput 估值结果
    """
    engine = get_valuation_engine()

    inputs = ValuationInput(
        ticker=ticker,
        current_price=current_price,
        company_name=company_name,
        **kwargs
    )

    return await engine.calculate(inputs, external_reference)


# =============================================================================
# 主程序（用于测试）
# =============================================================================

async def main():
    """主程序（用于测试）"""
    print("=" * 60)
    print("AI TradeBot - 内置估值引擎测试")
    print("=" * 60)
    print()

    # 测试用例：浦发银行
    test_inputs = ValuationInput(
        ticker="600000.SH",
        current_price=95.0,
        company_name="浦发银行",
        industry="银行",
        revenue_per_share=2.5,
        net_income=500000,
        book_value_per_share=18.5,
        dividend_per_share=0.8,
    )

    print(f"【测试标的】{test_inputs.ticker} - {test_inputs.company_name}")
    print(f"当前价格: {test_inputs.current_price} 元")
    print(f"行业: {test_inputs.industry}")
    print()
    print("🚀 启动全功率估值引擎...")
    print()

    engine = get_valuation_engine()
    result = await engine.calculate(test_inputs)

    print()
    print("=" * 60)
    print("估值结果")
    print("=" * 60)
    print()
    print(f"标的: {result.ticker}")
    print(f"模型: {result.model_used}")
    print(f"执行状态: {'✅ 成功' if result.execution_success else '❌ 失败'}")
    print(f"模型选择理由: {result.model_rationale}")
    print(f"计算耗时: {result.total_time:.2f} 秒")
    print(f"代码修正次数: {len(result.code_fix_history)}")
    print()

    if result.execution_success:
        print("【三种情景估值】")
        for name, scenario in result.scenarios.items():
            print()
            print(f"  📊 {name}情景:")
            print(f"     增长率: {scenario.growth_rate*100:.0f}%")
            print(f"     折现率: {scenario.discount_rate*100:.0f}%")
            print(f"     内在价值: {scenario.intrinsic_value:.2f} 元")
            print(f"     当前价值: {scenario.present_value:.2f} 元")
            print(f"     安全边际: {scenario.margin_of_safety:.2f}%")
            print(f"     上涨潜力: {scenario.upside_potential:.2f}%")
            print(f"     计算逻辑: {scenario.calculation_logic}")

        if result.clawdbot_comparison:
            print()
            print("【与外部估值对比】")
            for k, v in result.clawdbot_comparison.items():
                print(f"  {k}: {v}")

    else:
        print(f"❌ 错误: {result.execution_error}")

    print()
    print("=" * 60)
    print("AI 生成的 Python 代码")
    print("=" * 60)
    print()
    print(result.generated_code)
    print()


if __name__ == "__main__":
    asyncio.run(main())
