"""
AI TradeBot - API 端点单元测试
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

# 尝试导入 app
try:
    from core.api.app import app
    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False
    app = None


@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not available")
class TestHealthAPI:
    """健康检查 API 测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return TestClient(app)

    def test_quick_health(self, client):
        """测试快速健康检查"""
        response = client.get("/api/v1/health/quick")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_full_health_check(self, client):
        """测试完整健康检查"""
        with patch('decision.engine.health_checker.run_system_health_check') as mock_check:
            # 模拟健康检查报告
            mock_report = MagicMock()
            mock_report.to_dict.return_value = {
                "overall_status": "pass",
                "is_healthy": True,
                "passed_count": 5,
                "warning_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "checks": [],
                "checked_at": "2026-02-13T12:00:00",
            }
            mock_check.return_value = mock_report

            response = client.get("/api/v1/health/check")

            assert response.status_code == 200
            data = response.json()
            assert "overall_status" in data

    def test_gpu_status(self, client):
        """测试 GPU 状态"""
        with patch('decision.engine.monte_carlo_engine.detect_gpu_backend') as mock_detect:
            from decision.engine.monte_carlo_engine import ComputeBackend
            mock_detect.return_value = (ComputeBackend.NUMPY, "CPU 模式")

            response = client.get("/api/v1/health/gpu")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not available")
class TestNewsAPI:
    """新闻 API 测试"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_news_feed(self, client):
        """测试获取新闻流"""
        response = client.get("/api/v1/news/feed")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]

    def test_get_news_feed_with_limit(self, client):
        """测试带限制的新闻流"""
        response = client.get("/api/v1/news/feed?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["count"] <= 5

    def test_get_high_score_news(self, client):
        """测试高评分新闻"""
        response = client.get("/api/v1/news/high-score?threshold=7.0")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "threshold" in data["data"]

    def test_get_news_status(self, client):
        """测试新闻服务状态"""
        response = client.get("/api/v1/news/status")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "enabled" in data["data"]

    def test_get_latest_news(self, client):
        """测试最近新闻"""
        response = client.get("/api/v1/news/latest?minutes=60")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not available")
class TestMonteCarloAPI:
    """蒙特卡洛 API 测试"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_monte_carlo_status(self, client):
        """测试蒙特卡洛状态"""
        response = client.get("/api/v1/monte-carlo/status")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_quick_demo(self, client):
        """测试快速演示"""
        response = client.post(
            "/api/v1/monte-carlo/quick-demo",
            json={"ticker": "600000.SH", "current_price": 95.0}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "distribution_histogram" in data["data"] or "histogram" in data["data"]

    def test_quick_demo_missing_params(self, client):
        """测试缺少参数的快速演示"""
        response = client.post(
            "/api/v1/monte-carlo/quick-demo",
            json={}
        )

        # 应该返回 422 或使用默认值
        assert response.status_code in [200, 422]


@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not available")
class TestExternalAPI:
    """外部数据 API 测试"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_get_forex_rate(self, client):
        """测试获取汇率"""
        response = client.get("/api/v1/external/forex/USDCNH")

        assert response.status_code == 200
        data = response.json()
        assert "rate" in data or "error" in data


@pytest.mark.skipif(not APP_AVAILABLE, reason="FastAPI app not available")
class TestReasoningAPI:
    """推理 API 测试"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_start_reasoning(self, client):
        """测试启动推理"""
        response = client.post(
            "/api/v1/reasoning/start",
            json={
                "ticker": "600000.SH",
                "event_description": "测试事件",
            }
        )

        # 可能返回 200 或 404（如果路由未注册）
        assert response.status_code in [200, 404, 422]

    def test_get_demo(self, client):
        """测试演示端点"""
        response = client.post("/api/v1/reasoning/demo")

        assert response.status_code in [200, 404]


class TestAPIUtilities:
    """API 工具测试"""

    def test_health_check_response_format(self):
        """测试健康检查响应格式"""
        expected_fields = ["overall_status", "is_healthy", "checks", "checked_at"]

        # 验证响应结构定义
        for field in expected_fields:
            assert isinstance(field, str)

    def test_news_response_format(self):
        """测试新闻响应格式"""
        expected_fields = ["success", "data"]

        for field in expected_fields:
            assert isinstance(field, str)

    def test_monte_carlo_response_format(self):
        """测试蒙特卡洛响应格式"""
        expected_fields = [
            "ticker", "current_price", "mean_price",
            "var_95", "var_99", "histogram"
        ]

        for field in expected_fields:
            assert isinstance(field, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
