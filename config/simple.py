"""
AI TradeBot - 简化配置

只暴露20个核心配置项，其他配置使用默认值

使用方式：
```python
from config.simple import Config

api_key = Config.ZHIPU_API_KEY
model = Config.DEFAULT_MODEL
```
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ConfigClass:
    """
    核心配置（20项）

    分类：
    - AI 配置（5项）
    - 数据源配置（5项）
    - 系统配置（5项）
    - 风控配置（5项）
    """

    # ==========================================================================
    # AI 配置（5项）
    # ==========================================================================

    # 智谱 AI（GLM-5 核心）
    ZHIPU_API_KEY: str = ""
    ZHIPU_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"
    ZHIPU_MODEL: str = "glm-5"  # 核心模型

    # Kimi（长文专家，可选）
    KIMI_API_KEY: str = ""

    # 默认 AI 模型
    DEFAULT_MODEL: str = "glm-5"

    # ==========================================================================
    # 数据源配置（5项）
    # ==========================================================================

    # Tushare（金融数据）
    TUSHARE_TOKEN: str = ""

    # FunHub（汇率）
    FUNHUB_API_KEY: str = ""

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/aitradebot.db"

    # Redis（可选，用于缓存）
    REDIS_URL: str = ""

    # 报纸订阅目录
    NEWSPAPERS_DIR: str = r"D:\报刊订阅"

    # ==========================================================================
    # 系统配置（5项）
    # ==========================================================================

    # 日志级别
    LOG_LEVEL: str = "INFO"

    # API 端口
    API_PORT: int = 8001

    # 执行模式（manual/paper/live）
    EXECUTION_MODE: str = "manual"

    # 调试模式
    DEBUG: bool = False

    # GPU 加速
    ENABLE_GPU: bool = True

    # ==========================================================================
    # 风控配置（5项）- 硬编码安全参数
    # ==========================================================================

    # 最大持仓比例
    MAX_POSITION_RATIO: float = 0.3  # 单只股票最大30%

    # 止损阈值
    DEFAULT_STOP_LOSS: float = 0.05  # 默认5%止损

    # 止盈阈值
    DEFAULT_TAKE_PROFIT: float = 0.10  # 默认10%止盈

    # 风控熔断阈值（USD/CNH 波动率）
    FOREX_CIRCUIT_BREAKER: float = 0.01  # 1%波动触发熔断

    # 最大单日交易次数
    MAX_DAILY_TRADES: int = 5


# 从环境变量加载配置
def _load_from_env() -> ConfigClass:
    """从环境变量加载配置"""
    return ConfigClass(
        # AI 配置
        ZHIPU_API_KEY=os.getenv("ZHIPU_API_KEY", ""),
        ZHIPU_BASE_URL=os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        ZHIPU_MODEL=os.getenv("ZHIPU_MODEL", "glm-5"),
        KIMI_API_KEY=os.getenv("KIMI_API_KEY", ""),
        DEFAULT_MODEL=os.getenv("DEFAULT_MODEL", "glm-5"),
        # 数据源配置
        TUSHARE_TOKEN=os.getenv("TUSHARE_TOKEN", ""),
        FUNHUB_API_KEY=os.getenv("FUNHUB_API_KEY", ""),
        DATABASE_URL=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/aitradebot.db"),
        REDIS_URL=os.getenv("REDIS_URL", ""),
        NEWSPAPERS_DIR=os.getenv("NEWSPAPERS_DIR", r"D:\报刊订阅"),
        # 系统配置
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
        API_PORT=int(os.getenv("API_PORT", "8001")),
        EXECUTION_MODE=os.getenv("EXECUTION_MODE", "manual"),
        DEBUG=os.getenv("DEBUG", "").lower() in ("true", "1", "yes"),
        ENABLE_GPU=os.getenv("ENABLE_GPU", "true").lower() in ("true", "1", "yes"),
        # 风控配置
        MAX_POSITION_RATIO=float(os.getenv("MAX_POSITION_RATIO", "0.3")),
        DEFAULT_STOP_LOSS=float(os.getenv("DEFAULT_STOP_LOSS", "0.05")),
        DEFAULT_TAKE_PROFIT=float(os.getenv("DEFAULT_TAKE_PROFIT", "0.10")),
        FOREX_CIRCUIT_BREAKER=float(os.getenv("FOREX_CIRCUIT_BREAKER", "0.01")),
        MAX_DAILY_TRADES=int(os.getenv("MAX_DAILY_TRADES", "5")),
    )


# 全局配置实例
Config = _load_from_env()


def get_config() -> ConfigClass:
    """获取配置实例"""
    return Config


def reload_config() -> ConfigClass:
    """重新加载配置"""
    global Config
    Config = _load_from_env()
    return Config


# =============================================================================
# 配置验证
# =============================================================================


def validate_config() -> bool:
    """验证必要配置"""
    errors = []

    # GLM-5 是核心，必须配置
    if not Config.ZHIPU_API_KEY:
        errors.append("ZHIPU_API_KEY 未配置")

    # 数据库路径
    if not Config.DATABASE_URL:
        errors.append("DATABASE_URL 未配置")

    if errors:
        for error in errors:
            print(f"[配置错误] {error}")
        return False

    return True


__all__ = [
    "Config",
    "ConfigClass",
    "get_config",
    "reload_config",
    "validate_config",
]
