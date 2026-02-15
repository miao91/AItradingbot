"""
AI TradeBot - 计算沙盒验证器

增强估值引擎的验证能力：
1. 行业适配模型验证 - 确保选用的估值模型与行业匹配
2. 输出格式标准化 - 统一估值结果格式
3. 幻觉检测机制 - 检测 AI 生成的不合理数值
"""
import re
import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

SANDBOX_CONFIG = {
    # 合理的财务指标范围
    "reasonable_ranges": {
        "pe_ratio": (0, 200),         # 市盈率
        "pb_ratio": (0, 50),          # 市净率
        "ps_ratio": (0, 100),         # 市销率
        "growth_rate": (-0.5, 2.0),   # 增长率 -50% ~ 200%
        "discount_rate": (0.02, 0.25), # 折现率 2% ~ 25%
        "margin_of_safety": (-0.5, 1.0), # 安全边际 -50% ~ 100%
        "upside_potential": (-0.5, 2.0),  # 上涨潜力 -50% ~ 200%
    },

    # 行业估值模型映射验证规则
    "industry_model_rules": {
        "manufacturing": {
            "allowed_models": ["DCF", "PE", "EV/EBITDA"],
            "preferred_model": "DCF",
            "typical_pe_range": (8, 25),
        },
        "internet": {
            "allowed_models": ["PS", "PCF", "PEG"],
            "preferred_model": "PS",
            "typical_ps_range": (2, 30),
        },
        "finance": {
            "allowed_models": ["PB", "PE", "DDM"],
            "preferred_model": "PB",
            "typical_pb_range": (0.5, 3),
        },
        "utilities": {
            "allowed_models": ["DDM", "PE", "DCF"],
            "preferred_model": "DDM",
            "typical_dividend_yield": (0.02, 0.08),
        },
        "consumer": {
            "allowed_models": ["PE", "DCF", "EV/EBITDA"],
            "preferred_model": "PE",
            "typical_pe_range": (10, 40),
        },
        "healthcare": {
            "allowed_models": ["DCF", "PS", "rNPV"],
            "preferred_model": "DCF",
            "typical_pe_range": (15, 60),
        },
        "energy": {
            "allowed_models": ["PCF", "EV/EBITDA", "P/NAV"],
            "preferred_model": "PCF",
            "typical_pcf_range": (3, 15),
        },
        "materials": {
            "allowed_models": ["EV/EBITDA", "PB", "PCF"],
            "preferred_model": "EV/EBITDA",
            "typical_ev_ebitda": (4, 15),
        },
        "real_estate": {
            "allowed_models": ["NAV", "P/NAV", "FFO"],
            "preferred_model": "NAV",
            "typical_p_nav": (0.5, 1.5),
        },
        "cycle_resource": {
            "allowed_models": ["PB", "EV/EBITDA", "PCF"],
            "preferred_model": "PB",
            "typical_pb_range": (0.5, 3),
        },
    },

    # 幻觉检测阈值
    "hallucination_thresholds": {
        "max_price_change_ratio": 3.0,  # 价格变化不超过 3 倍
        "max_value_deviation": 0.5,     # 与基准偏差不超过 50%
        "suspicious_patterns": [
            r"1000\.\d+",              # 过于精确的大数
            r"999999",                 # 无限大标记
            r"NaN|nan|Infinity",       # 非法数值
        ],
    },
}


# =============================================================================
# 数据类
# =============================================================================

class ValidationSeverity(Enum):
    """验证问题严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """验证问题"""
    severity: ValidationSeverity
    category: str  # industry_model, output_format, hallucination
    message: str
    detail: str = ""
    suggestion: str = ""


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    corrected_values: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return any(i.severity in [ValidationSeverity.ERROR, ValidationSeverity.CRITICAL]
                   for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == ValidationSeverity.WARNING for i in self.issues)


# =============================================================================
# 沙盒验证器
# =============================================================================

class SandboxValidator:
    """
    计算沙盒验证器

    提供三层验证：
    1. 行业适配模型验证
    2. 输出格式标准化
    3. 幻觉检测机制
    """

    def __init__(self):
        """初始化验证器"""
        self.config = SANDBOX_CONFIG
        logger.info("[沙盒验证器] 初始化完成")

    def validate_industry_model(
        self,
        industry: str,
        model: str,
        valuation_data: Dict[str, Any],
    ) -> ValidationResult:
        """
        验证行业估值模型适配性

        Args:
            industry: 行业类型
            model: 使用的估值模型
            valuation_data: 估值数据

        Returns:
            ValidationResult 验证结果
        """
        result = ValidationResult(is_valid=True)

        industry_lower = industry.lower() if industry else "other"
        rules = self.config["industry_model_rules"].get(industry_lower, {})

        if not rules:
            # 未找到行业规则，使用通用验证
            result.issues.append(ValidationIssue(
                severity=ValidationSeverity.INFO,
                category="industry_model",
                message=f"未找到行业 '{industry}' 的专用规则，使用通用验证",
            ))
            return result

        # 检查模型是否在允许列表中
        allowed_models = rules.get("allowed_models", [])
        if allowed_models and model not in allowed_models:
            result.issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                category="industry_model",
                message=f"模型 '{model}' 不是 {industry} 行业的首选模型",
                suggestion=f"建议使用: {', '.join(allowed_models)}",
            ))

        # 检查典型估值范围
        if "pe_ratio" in valuation_data:
            pe_range = rules.get("typical_pe_range")
            if pe_range:
                pe = valuation_data["pe_ratio"]
                if not (pe_range[0] <= pe <= pe_range[1]):
                    result.issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="industry_model",
                        message=f"PE ({pe}) 超出 {industry} 行业典型范围 {pe_range}",
                        suggestion="检查数据来源或考虑行业特殊情况",
                    ))

        return result

    def validate_output_format(
        self,
        output: Dict[str, Any],
        required_fields: List[str] = None,
    ) -> ValidationResult:
        """
        验证输出格式

        Args:
            output: 输出数据
            required_fields: 必需字段列表

        Returns:
            ValidationResult 验证结果
        """
        result = ValidationResult(is_valid=True)

        if required_fields is None:
            required_fields = ["scenarios", "model_used"]

        # 检查必需字段
        for field in required_fields:
            if field not in output:
                result.issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="output_format",
                    message=f"缺少必需字段: {field}",
                    suggestion=f"请添加 {field} 字段",
                ))
                result.is_valid = False

        # 检查情景数据格式
        scenarios = output.get("scenarios", {})
        for scenario_name, scenario_data in scenarios.items():
            if not isinstance(scenario_data, dict):
                result.issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="output_format",
                    message=f"情景 '{scenario_name}' 数据格式错误",
                ))
                continue

            # 检查数值字段
            numeric_fields = [
                "growth_rate", "discount_rate", "intrinsic_value",
                "present_value", "margin_of_safety", "upside_potential"
            ]

            for field in numeric_fields:
                value = scenario_data.get(field)
                if value is not None:
                    try:
                        float(value)
                    except (TypeError, ValueError):
                        result.issues.append(ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            category="output_format",
                            message=f"情景 '{scenario_name}' 字段 '{field}' 不是有效数值: {value}",
                        ))

        return result

    def detect_hallucination(
        self,
        current_price: float,
        valuation_data: Dict[str, Any],
        scenarios: Dict[str, Dict],
    ) -> ValidationResult:
        """
        检测幻觉（不合理的估值结果）

        Args:
            current_price: 当前价格
            valuation_data: 估值数据
            scenarios: 情景数据

        Returns:
            ValidationResult 验证结果
        """
        result = ValidationResult(is_valid=True)
        thresholds = self.config["hallucination_thresholds"]

        for scenario_name, scenario in scenarios.items():
            present_value = scenario.get("present_value", 0)
            intrinsic_value = scenario.get("intrinsic_value", 0)
            growth_rate = scenario.get("growth_rate", 0)
            discount_rate = scenario.get("discount_rate", 0)

            # 检查 1: 估值与当前价格的关系
            if current_price > 0 and present_value > 0:
                price_change_ratio = present_value / current_price
                if price_change_ratio > thresholds["max_price_change_ratio"]:
                    result.issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        category="hallucination",
                        message=f"情景 '{scenario_name}' 估值 ({present_value:.2f}) 是当前价格 ({current_price:.2f}) 的 {price_change_ratio:.1f} 倍",
                        suggestion="检查估值模型参数是否合理",
                    ))
                    # 建议修正
                    corrected_value = current_price * thresholds["max_price_change_ratio"]
                    result.corrected_values[f"{scenario_name}_present_value"] = corrected_value

            # 检查 2: 增长率合理性
            reasonable_growth = self.config["reasonable_ranges"]["growth_rate"]
            if not (reasonable_growth[0] <= growth_rate <= reasonable_growth[1]):
                result.issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="hallucination",
                    message=f"情景 '{scenario_name}' 增长率 ({growth_rate*100:.1f}%) 超出合理范围",
                    suggestion=f"建议范围: {reasonable_growth[0]*100:.0f}% ~ {reasonable_growth[1]*100:.0f}%",
                ))

            # 检查 3: 折现率合理性
            reasonable_discount = self.config["reasonable_ranges"]["discount_rate"]
            if not (reasonable_discount[0] <= discount_rate <= reasonable_discount[1]):
                result.issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="hallucination",
                    message=f"情景 '{scenario_name}' 折现率 ({discount_rate*100:.1f}%) 超出合理范围",
                    suggestion=f"建议范围: {reasonable_discount[0]*100:.0f}% ~ {reasonable_discount[1]*100:.0f}%",
                ))

            # 检查 4: 数值是否为非法值
            for key, value in scenario.items():
                if isinstance(value, (int, float)):
                    # 检查 NaN 和 Infinity
                    if value != value:  # NaN check
                        result.issues.append(ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            category="hallucination",
                            message=f"情景 '{scenario_name}' 字段 '{key}' 为 NaN",
                        ))
                        result.is_valid = False

            # 检查 5: 数值是否过于精确（幻觉指标）
            for key, value in scenario.items():
                if isinstance(value, float):
                    str_value = str(value)
                    for pattern in thresholds["suspicious_patterns"]:
                        if re.search(pattern, str_value):
                            result.issues.append(ValidationIssue(
                                severity=ValidationSeverity.WARNING,
                                category="hallucination",
                                message=f"情景 '{scenario_name}' 字段 '{key}' 值 {value} 可疑",
                                suggestion="检查计算过程是否存在问题",
                            ))

        return result

    def full_validation(
        self,
        industry: str,
        model: str,
        current_price: float,
        output: Dict[str, Any],
    ) -> ValidationResult:
        """
        执行完整验证

        Args:
            industry: 行业类型
            model: 估值模型
            current_price: 当前价格
            output: 完整输出数据

        Returns:
            ValidationResult 综合验证结果
        """
        # 合并所有验证结果
        final_result = ValidationResult(is_valid=True)

        # 1. 行业模型验证
        model_result = self.validate_industry_model(industry, model, output)
        final_result.issues.extend(model_result.issues)

        # 2. 输出格式验证
        format_result = self.validate_output_format(output)
        final_result.issues.extend(format_result.issues)
        if not format_result.is_valid:
            final_result.is_valid = False

        # 3. 幻觉检测
        scenarios = output.get("scenarios", {})
        hallucination_result = self.detect_hallucination(current_price, output, scenarios)
        final_result.issues.extend(hallucination_result.issues)
        final_result.corrected_values.update(hallucination_result.corrected_values)

        # 汇总警告
        final_result.warnings = [
            i.message for i in final_result.issues
            if i.severity in [ValidationSeverity.WARNING, ValidationSeverity.ERROR]
        ]

        # 更新最终状态
        if final_result.has_errors:
            final_result.is_valid = False

        logger.info(
            f"[沙盒验证器] 验证完成: "
            f"有效={final_result.is_valid}, "
            f"问题数={len(final_result.issues)}, "
            f"警告数={len(final_result.warnings)}"
        )

        return final_result


# =============================================================================
# 全局单例
# =============================================================================

_sandbox_validator: Optional[SandboxValidator] = None


def get_sandbox_validator() -> SandboxValidator:
    """获取全局沙盒验证器实例"""
    global _sandbox_validator
    if _sandbox_validator is None:
        _sandbox_validator = SandboxValidator()
    return _sandbox_validator


# =============================================================================
# 便捷函数
# =============================================================================

def validate_valuation_output(
    industry: str,
    model: str,
    current_price: float,
    output: Dict[str, Any],
) -> ValidationResult:
    """
    验证估值输出（便捷函数）

    Args:
        industry: 行业类型
        model: 估值模型
        current_price: 当前价格
        output: 完整输出数据

    Returns:
        ValidationResult 验证结果
    """
    validator = get_sandbox_validator()
    return validator.full_validation(industry, model, current_price, output)


# =============================================================================
# 测试
# =============================================================================

def test_sandbox_validator():
    """测试沙盒验证器"""
    print("=" * 60)
    print("AI TradeBot - 沙盒验证器测试")
    print("=" * 60)

    validator = get_sandbox_validator()

    # 测试用例 1: 正常估值
    normal_output = {
        "scenarios": {
            "乐观": {
                "growth_rate": 0.20,
                "discount_rate": 0.10,
                "present_value": 110.0,
                "intrinsic_value": 120.0,
            },
            "中性": {
                "growth_rate": 0.10,
                "discount_rate": 0.12,
                "present_value": 100.0,
                "intrinsic_value": 105.0,
            },
        },
        "model_used": "DCF",
    }

    result = validator.full_validation(
        industry="manufacturing",
        model="DCF",
        current_price=95.0,
        output=normal_output,
    )

    print(f"\n测试 1 (正常估值): 有效={result.is_valid}")
    print(f"问题数: {len(result.issues)}")

    # 测试用例 2: 异常估值（幻觉检测）
    hallucination_output = {
        "scenarios": {
            "乐观": {
                "growth_rate": 5.0,  # 异常高增长率
                "discount_rate": 0.10,
                "present_value": 5000.0,  # 异常高估值
                "intrinsic_value": 6000.0,
            },
        },
        "model_used": "DCF",
    }

    result2 = validator.full_validation(
        industry="manufacturing",
        model="DCF",
        current_price=95.0,
        output=hallucination_output,
    )

    print(f"\n测试 2 (幻觉检测): 有效={result2.is_valid}")
    print(f"问题数: {len(result2.issues)}")
    for issue in result2.issues:
        print(f"  - [{issue.severity.value}] {issue.message}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_sandbox_validator()
