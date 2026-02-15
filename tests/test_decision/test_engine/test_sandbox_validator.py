"""
AI TradeBot - 沙盒验证器单元测试

测试实际实现的公共接口
"""
import pytest
from unittest.mock import MagicMock

from decision.engine.sandbox_validator import (
    SandboxValidator,
    ValidationResult,
    ValidationSeverity,
    ValidationIssue,
    get_sandbox_validator,
)
from decision.engine.valuation_tool import IndustryType


class TestValidationSeverity:
    """验证严重性枚举测试"""

    def test_severity_values(self):
        """测试严重性值"""
        assert ValidationSeverity.INFO.value == "info"
        assert ValidationSeverity.WARNING.value == "warning"
        assert ValidationSeverity.ERROR.value == "error"
        assert ValidationSeverity.CRITICAL.value == "critical"


class TestValidationIssue:
    """验证问题数据类测试"""

    def test_issue_creation(self):
        """测试问题创建"""
        issue = ValidationIssue(
            severity=ValidationSeverity.WARNING,
            category="price_deviation",
            message="价格偏离过大",
            detail="当前价格与估值偏离 50%",
            suggestion="检查估值参数",
        )

        assert issue.severity == ValidationSeverity.WARNING
        assert issue.category == "price_deviation"
        assert issue.message == "价格偏离过大"


class TestValidationResult:
    """验证结果数据类测试"""

    def test_result_creation(self):
        """测试结果创建"""
        result = ValidationResult(is_valid=True)

        assert result.is_valid is True
        assert result.issues is not None

    def test_result_with_issues(self):
        """测试带问题的结果"""
        result = ValidationResult(is_valid=False)
        result.issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category="format",
            message="格式无效",
        ))

        assert result.is_valid is False
        assert len(result.issues) > 0

    def test_result_has_errors(self):
        """测试错误检查"""
        result = ValidationResult(is_valid=True)
        # has_errors 是属性不是方法
        assert result.has_errors is False

        result.issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category="test",
            message="测试错误",
        ))
        assert result.has_errors is True

    def test_result_has_warnings(self):
        """测试警告检查"""
        result = ValidationResult(is_valid=True)
        assert result.has_warnings is False

        result.issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            category="test",
            message="测试警告",
        ))
        assert result.has_warnings is True


class TestSandboxValidator:
    """沙盒验证器测试"""

    @pytest.fixture
    def validator(self):
        """创建验证器实例"""
        return SandboxValidator()

    def test_validator_initialization(self, validator):
        """测试验证器初始化"""
        assert validator is not None

    def test_validate_output(self, validator):
        """测试输出验证"""
        output = {
            "scenarios": {
                "中性": {
                    "present_value": 100.0,
                    "growth_rate": 0.10,
                    "discount_rate": 0.12,
                }
            },
            "model_used": "DCF",
        }

        result = validator.full_validation(
            industry="manufacturing",  # 使用字符串而不是枚举
            model="DCF",
            current_price=95.0,
            output=output,
        )

        assert result is not None
        assert isinstance(result, ValidationResult)

    def test_validate_empty_output(self, validator):
        """测试空输出验证"""
        result = validator.full_validation(
            industry="manufacturing",  # 使用字符串而不是枚举
            model="DCF",
            current_price=100.0,
            output={},
        )

        assert result is not None


class TestGlobalInstance:
    """全局实例测试"""

    def test_get_sandbox_validator(self):
        """测试获取全局验证器实例"""
        validator1 = get_sandbox_validator()
        validator2 = get_sandbox_validator()

        assert validator1 is not None
        assert validator2 is not None
        # 应该是同一个实例（单例）
        assert validator1 is validator2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
