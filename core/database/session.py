"""
AI TradeBot - 数据库会话管理
使用 SQLAlchemy 异步模式
"""
import os
from pathlib import Path
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool
import aiosqlite

from shared.logging import get_logger
from shared.constants import DEFAULT_DB_PATH


logger = get_logger(__name__)


class DatabaseManager:
    """
    数据库管理器 - 单例模式
    负责：引擎初始化、会话管理、表结构创建
    """

    _instance: Optional["DatabaseManager"] = None
    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 避免重复初始化
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._db_url: Optional[str] = None

    def get_db_url(self) -> str:
        """
        获取数据库连接 URL

        Returns:
            数据库连接字符串
        """
        if self._db_url:
            return self._db_url

        # 从环境变量读取，否则使用默认值
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            # 确保数据库目录存在
            db_path = Path(DEFAULT_DB_PATH)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # 构建 SQLite 异步 URL
            abs_path = db_path.absolute()
            db_url = f"sqlite+aiosqlite:///{abs_path}"

        self._db_url = db_url
        logger.info(f"Database URL: {self._db_url}")
        return self._db_url

    async def initialize_engine(
        self,
        db_url: Optional[str] = None,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
    ) -> AsyncEngine:
        """
        初始化数据库引擎

        Args:
            db_url: 数据库连接 URL，默认从环境变量获取
            echo: 是否输出 SQL 语句（调试用）
            pool_size: 连接池大小
            max_overflow: 最大溢出连接数

        Returns:
            异步引擎实例
        """
        if self._engine is not None:
            logger.warning("Database engine already initialized")
            return self._engine

        url = db_url or self.get_db_url()

        # SQLite 使用 NullPool（连接池管理由文件系统处理）
        # 其他数据库可配置连接池参数
        engine_kwargs = {"echo": echo}
        if not url.startswith("sqlite"):
            engine_kwargs.update({
                "pool_size": pool_size,
                "max_overflow": max_overflow,
            })
        else:
            engine_kwargs["poolclass"] = NullPool

        self._engine = create_async_engine(url, **engine_kwargs)

        # 创建会话工厂
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        logger.info("Database engine initialized successfully")
        return self._engine

    async def create_tables(self, drop_existing: bool = False) -> None:
        """
        创建数据库表结构

        Args:
            drop_existing: 是否先删除已存在的表
        """
        if self._engine is None:
            await self.initialize_engine()

        # 导入所有模型（确保表被注册到 Base.metadata）
        from storage.models.trade_event import Base
        from storage.models import (
            decision,  # type: ignore
            position,  # type: ignore
            trade_log,  # type: ignore
            ai_reasoning,  # type: ignore
        )

        if drop_existing:
            logger.warning("Dropping existing tables...")
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("Existing tables dropped")

        logger.info("Creating database tables...")
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

    def get_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """
        获取会话工厂

        Returns:
            会话工厂实例

        Raises:
            RuntimeError: 如果引擎未初始化
        """
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize_engine() first.")
        return self._session_factory

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._engine is not None:
            await self._engine.dispose()
            logger.info("Database connection closed")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize_engine()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


# 全局数据库管理器实例
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖注入函数（FastAPI 使用）

    Yields:
        数据库会话

    Example:
        @app.get("/events/")
        async def list_events(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(TradeEvent))
            return result.scalars().all()
    """
    session_factory = db_manager.get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的上下文管理器（脚本使用）

    Yields:
        数据库会话

    Example:
        async with get_db_context() as db:
            event = TradeEvent(ticker="600000.SH", ...)
            db.add(event)
            await db.commit()
    """
    session_factory = db_manager.get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_database(
    db_url: Optional[str] = None,
    echo: bool = False,
    drop_tables: bool = False,
) -> None:
    """
    初始化数据库（便捷函数）

    Args:
        db_url: 数据库 URL
        echo: 是否输出 SQL
        drop_tables: 是否删除已存在的表
    """
    await db_manager.initialize_engine(db_url=db_url, echo=echo)
    await db_manager.create_tables(drop_existing=drop_tables)


async def check_database_connection() -> bool:
    """
    检查数据库连接是否正常

    Returns:
        连接是否成功
    """
    from sqlalchemy import text
    try:
        async with get_db_context() as db:
            await db.execute(text("SELECT 1"))
        logger.info("Database connection check passed")
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
