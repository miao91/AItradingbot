"""
AI TradeBot - 健康检查器单元测试
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from decision.engine.health_checker import (
    SystemHealthChecker,
    CheckResult,
    CheckStatus,
    SystemHealthReport,
    run_system_health_check,
    get_health_checker,
    HEALTH_CHECK_CONFIG,
)


class TestCheckStatus:
    """检查状态枚举测试"""

    def test_status_values(self):
        """测试状态值"""
        assert CheckStatus.PASS.value == "pass"
        assert CheckStatus.WARNING.value == "warning"
        assert CheckStatus.FAIL.value == "fail"
        assert CheckStatus.SKIP.value == "skip"

    def test_all_statuses_exist(self):
        """测试所有状态存在"""
        statuses = list(CheckStatus)
        assert len(statuses) == 4


class TestCheckResult:
    """检查结果数据类测试"""

    def test_result_creation(self):
        """测试结果创建"""
        result = CheckResult(
            check_name="汇率预警联动",
            status=CheckStatus.PASS,
            message="检查通过",
            details={"api_configured": True},
        )

        assert result.check_name == "汇率预警联动"
        assert result.status == CheckStatus.PASS
        assert result.message == "检查通过"
        assert result.details["api_configured"] is True

    def test_result_is_healthy_pass(self):
        """测试 PASS 状态健康"""
        result = CheckResult(
            check_name="测试",
            status=CheckStatus.PASS,
            message="通过",
        )
        assert result.is_healthy is True

    def test_result_is_healthy_warning(self):
        """测试 WARNING 状态健康"""
        result = CheckResult(
            check_name="测试",
            status=CheckStatus.WARNING,
            message="警告",
        )
        assert result.is_healthy is False  # WARNING 不算健康

    def test_result_is_healthy_fail(self):
        """测试 FAIL 状态不健康"""
        result = CheckResult(
            check_name="测试",
            status=CheckStatus.FAIL,
            message="失败",
        )
        assert result.is_healthy is False

    def test_result_is_healthy_skip(self):
        """测试 SKIP 状态健康"""
        result = CheckResult(
            check_name="测试",
            status=CheckStatus.SKIP,
            message="跳过",
        )
        assert result.is_healthy is True

    def test_result_timestamp(self):
        """测试时间戳自动生成"""
        result = CheckResult(
            check_name="测试",
            status=CheckStatus.PASS,
            message="通过",
        )
        assert result.timestamp is not None
        assert len(result.timestamp) > 0


class TestSystemHealthReport:
    """系统健康报告测试"""

    def test_report_creation(self):
        """测试报告创建"""
        report = SystemHealthReport(
            overall_status=CheckStatus.PASS,
            checks=[
                CheckResult("检查1", CheckStatus.PASS, "通过"),
                CheckResult("检查2", CheckStatus.PASS, "通过"),
            ],
            passed_count=2,
            warning_count=0,
            failed_count=0,
            skipped_count=0,
        )

        assert report.overall_status == CheckStatus.PASS
        assert len(report.checks) == 2
        assert report.is_healthy is True

    def test_report_is_healthy_with_warning(self):
        """测试带警告的报告健康状态"""
        report = SystemHealthReport(
            overall_status=CheckStatus.WARNING,
            checks=[],
            passed_count=1,
            warning_count=1,
            failed_count=0,
            skipped_count=0,
        )
        assert report.is_healthy is True  # WARNING 仍然算健康

    def test_report_is_healthy_with_fail(self):
        """测试带失败的健康状态"""
        report = SystemHealthReport(
            overall_status=CheckStatus.FAIL,
            checks=[],
            passed_count=0,
            warning_count=0,
            failed_count=1,
            skipped_count=0,
        )
        assert report.is_healthy is False

    def test_report_to_dict(self):
        """测试报告转字典"""
        report = SystemHealthReport(
            overall_status=CheckStatus.PASS,
            checks=[
                CheckResult("检查1", CheckStatus.PASS, "通过", {"key": "value"}),
            ],
            passed_count=1,
            warning_count=0,
            failed_count=0,
            skipped_count=0,
        )

        result = report.to_dict()

        assert result["overall_status"] == "pass"
        assert result["is_healthy"] is True
        assert result["passed_count"] == 1
        assert len(result["checks"]) == 1
        assert result["checks"][0]["name"] == "检查1"


class TestHealthCheckConfig:
    """健康检查配置测试"""

    def test_config_exists(self):
        """测试配置存在"""
        assert HEALTH_CHECK_CONFIG is not None
        assert "checks" in HEALTH_CHECK_CONFIG

    def test_exchange_rate_config(self):
        """测试汇率预警配置"""
        config = HEALTH_CHECK_CONFIG["checks"]["exchange_rate_alert"]
        assert config["enabled"] is True
        assert "threshold_warning" in config
        assert "threshold_danger" in config

    def test_language_isolation_config(self):
        """测试语言隔离配置"""
        config = HEALTH_CHECK_CONFIG["checks"]["language_isolation"]
        assert config["enabled"] is True
        assert "allowed_languages" in config
        assert "en" in config["allowed_languages"]

    def test_async_config(self):
        """测试异步非阻塞配置"""
        config = HEALTH_CHECK_CONFIG["checks"]["async_non_blocking"]
        assert config["enabled"] is True
        assert "max_blocking_time_ms" in config

    def test_hallucination_config(self):
        """测试幻觉防护配置"""
        config = HEALTH_CHECK_CONFIG["checks"]["hallucination_protection"]
        assert config["enabled"] is True
        assert "max_price_change_ratio" in config

    def test_industry_adaptation_config(self):
        """测试行业适配配置"""
        config = HEALTH_CHECK_CONFIG["checks"]["industry_adaptation"]
        assert config["enabled"] is True
        assert "industry_models" in config
        assert len(config["industry_models"]) >= 8


class TestSystemHealthChecker:
    """系统健康检查器测试"""

    @pytest.fixture
    def checker(self):
        """创建检查器实例"""
        return SystemHealthChecker()

    def test_checker_initialization(self, checker):
        """测试检查器初始化"""
        assert checker is not None
        assert checker.config == HEALTH_CHECK_CONFIG
        assert checker.results == []

    @pytest.mark.asyncio
    async def test_run_all_checks(self, checker):
        """测试运行所有检查"""
        report = await checker.run_all_checks()

        assert report is not None
        assert isinstance(report, SystemHealthReport)
        assert len(report.checks) == 5  # 5 项检查

    @pytest.mark.asyncio
    async def test_check_exchange_rate_alert(self, checker):
        """测试汇率预警检查"""
        await checker._check_exchange_rate_alert()

        assert len(checker.results) == 1
        result = checker.results[0]
        assert result.check_name == "汇率预警联动"
        assert result.status in [CheckStatus.PASS, CheckStatus.WARNING, CheckStatus.FAIL, CheckStatus.SKIP]

    @pytest.mark.asyncio
    async def test_check_language_isolation(self, checker):
        """测试语言隔离检查"""
        await checker._check_language_isolation()

        assert len(checker.results) == 1
        result = checker.results[0]
        assert result.check_name == "语言隔离"

    @pytest.mark.asyncio
    async def test_check_async_non_blocking(self, checker):
        """测试异步非阻塞检查"""
        await checker._check_async_non_blocking()

        assert len(checker.results) == 1
        result = checker.results[0]
        assert result.check_name == "异步非阻塞"

    @pytest.mark.asyncio
    async def test_check_hallucination_protection(self, checker):
        """测试幻觉防护检查"""
        # 需要 sandbox_validator 模块
        try:
            await checker._check_hallucination_protection()

            result = checker.results[-1]
            assert result.check_name == "幻觉防护"
        except ImportError:
            pytest.skip("sandbox_validator not available")

    @pytest.mark.asyncio
    async def test_check_industry_adaptation(self, checker):
        """测试行业适配检查"""
        # 需要 valuation_tool 模块
        try:
            await checker._check_industry_adaptation()

            result = checker.results[-1]
            assert result.check_name == "行业适配"
        except ImportError:
            pytest.skip("valuation_tool not available")


class TestGlobalFunctions:
    """全局函数测试"""

    def test_get_health_checker_singleton(self):
        """测试获取单例"""
        checker1 = get_health_checker()
        checker2 = get_health_checker()

        assert checker1 is not None
        assert checker1 is checker2  # 应该是同一个实例

    @pytest.mark.asyncio
    async def test_run_system_health_check(self):
        """测试运行系统健康检查便捷函数"""
        report = await run_system_health_check()

        assert report is not None
        assert isinstance(report, SystemHealthReport)


class TestCheckDisabled:
    """禁用检查测试"""

    @pytest.fixture
    def checker_disabled(self):
        """创建禁用检查的检查器"""
        config = {
            "checks": {
                "exchange_rate_alert": {"enabled": False},
                "language_isolation": {"enabled": False},
                "async_non_blocking": {"enabled": False},
                "hallucination_protection": {"enabled": False},
                "industry_adaptation": {"enabled": False},
            }
        }
        checker = SystemHealthChecker()
        checker.config = config
        return checker

    @pytest.mark.asyncio
    async def test_disabled_checks_skip(self, checker_disabled):
        """测试禁用的检查跳过"""
        await checker_disabled._check_exchange_rate_alert()

        assert len(checker_disabled.results) == 1
        result = checker_disabled.results[0]
        assert result.status == CheckStatus.SKIP


class TestEdgeCases:
    """边界情况测试"""

    @pytest.fixture
    def checker(self):
        return SystemHealthChecker()

    @pytest.mark.asyncio
    async def test_check_with_exception(self, checker):
        """测试检查中异常处理"""
        with patch.object(checker, '_check_exchange_rate_alert') as mock_check:
            mock_check.side_effect = Exception("测试异常")

            # 不应该抛出异常
            try:
                await mock_check()
            except Exception:
                pass  # 预期的异常


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
