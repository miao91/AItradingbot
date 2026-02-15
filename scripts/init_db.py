"""
AI TradeBot - 数据库初始化脚本

功能：
1. 初始化数据库引擎
2. 创建所有表结构
3. 可选：清空已有数据
4. 验证数据库连接

使用方法：
    python scripts/init_db.py              # 创建数据库
    python scripts/init_db.py --drop       # 删除并重新创建
    python scripts/init_db.py --echo       # 显示 SQL 语句
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import click
from shared.logging import setup_logging, get_logger, track_operation
from core.database.session import db_manager, check_database_connection
from shared.constants import DEFAULT_DB_PATH


@click.group()
def cli():
    """数据库管理工具"""
    pass


@cli.command()
@click.option(
    "--drop",
    is_flag=True,
    help="删除已存在的表（危险操作！）",
)
@click.option(
    "--echo",
    is_flag=True,
    help="显示 SQL 语句",
)
@click.option(
    "--db-url",
    default=None,
    help="自定义数据库连接 URL",
)
def init(drop: bool, echo: bool, db_url: str):
    """
    初始化数据库

    示例:
        python scripts/init_db.py init
        python scripts/init_db.py init --drop
        python scripts/init_db.py init --echo
    """
    setup_logging()
    logger = get_logger(__name__)

    # 显示配置信息
    db_path = db_url or DEFAULT_DB_PATH
    logger.info("=" * 60)
    logger.info("AI TradeBot - 数据库初始化")
    logger.info("=" * 60)
    logger.info(f"数据库路径: {db_path}")
    logger.info(f"删除已有表: {'是 (危险!)' if drop else '否'}")
    logger.info(f"显示 SQL: {'是' if echo else '否'}")
    logger.info("=" * 60)

    if drop:
        click.confirm("⚠️  确认要删除所有已有数据吗？此操作不可恢复！", abort=True)

    # 异步初始化
    asyncio.run(_init_database(drop, echo, db_url))


async def _init_database(drop: bool, echo: bool, db_url: str):
    """异步初始化数据库"""
    logger = get_logger(__name__)

    with track_operation("数据库引擎初始化"):
        await db_manager.initialize_engine(db_url=db_url, echo=echo)

    with track_operation("表结构创建"):
        await db_manager.create_tables(drop_existing=drop)

    # 验证连接
    with track_operation("数据库连接验证"):
        if await check_database_connection():
            logger.info("✅ 数据库连接验证成功")
        else:
            logger.error("❌ 数据库连接验证失败")
            sys.exit(1)

    # 显示数据库文件信息
    if not db_url:  # 使用默认 SQLite
        db_file = Path(DEFAULT_DB_PATH)
        if db_file.exists():
            size_mb = db_file.stat().st_size / (1024 * 1024)
            logger.info(f"📄 数据库文件大小: {size_mb:.2f} MB")

    logger.info("=" * 60)
    logger.info("✅ 数据库初始化完成！")
    logger.info("=" * 60)

    # 关闭连接
    await db_manager.close()


@cli.command()
@click.option(
    "--db-url",
    default=None,
    help="数据库连接 URL",
)
def check(db_url: str):
    """
    检查数据库连接状态

    示例:
        python scripts/init_db.py check
    """
    setup_logging()
    logger = get_logger(__name__)

    async def _check():
        if db_url:
            await db_manager.initialize_engine(db_url=db_url)

        result = await check_database_connection()
        await db_manager.close()

        if result:
            logger.info("✅ 数据库连接正常")
            sys.exit(0)
        else:
            logger.error("❌ 数据库连接失败")
            sys.exit(1)

    asyncio.run(_check())


@cli.command()
@click.option(
    "--confirm",
    is_flag=True,
    help="确认删除操作",
)
def reset(confirm: bool):
    """
    重置数据库（删除所有数据）

    示例:
        python scripts/init_db.py reset --confirm
    """
    setup_logging()
    logger = get_logger(__name__)

    if not confirm:
        logger.error("❌ 请使用 --confirm 参数确认删除操作")
        logger.info("示例: python scripts/init_db.py reset --confirm")
        sys.exit(1)

    if not click.confirm("⚠️  此操作将永久删除所有数据，确认继续？"):
        sys.exit(0)

    async def _reset():
        with track_operation("数据库重置"):
            await db_manager.initialize_engine()
            await db_manager.create_tables(drop_existing=True)

            if await check_database_connection():
                logger.info("✅ 数据库重置完成")
            else:
                logger.error("❌ 数据库重置后验证失败")
                sys.exit(1)

        await db_manager.close()

    asyncio.run(_reset())


@cli.command()
def status():
    """
    显示数据库状态信息

    示例:
        python scripts/init_db.py status
    """
    setup_logging()
    logger = get_logger(__name__)

    async def _status():
        try:
            # 尝试连接数据库
            await db_manager.initialize_engine()

            # 检查文件是否存在
            db_file = Path(DEFAULT_DB_PATH)
            if db_file.exists():
                size_mb = db_file.stat().st_size / (1024 * 1024)
                logger.info("=" * 60)
                logger.info("数据库状态")
                logger.info("=" * 60)
                logger.info(f"文件路径: {db_file.absolute()}")
                logger.info(f"文件大小: {size_mb:.2f} MB")
                logger.info(f"创建时间: {db_file.stat().st_ctime}")
                logger.info(f"修改时间: {db_file.stat().st_mtime}")

                # 检查连接
                if await check_database_connection():
                    logger.info("连接状态: ✅ 正常")
                else:
                    logger.info("连接状态: ❌ 异常")

                logger.info("=" * 60)
            else:
                logger.warning("⚠️  数据库文件不存在，请先运行 init 命令")

            await db_manager.close()

        except Exception as e:
            logger.error(f"❌ 获取数据库状态失败: {e}")
            sys.exit(1)

    asyncio.run(_status())


@cli.command()
@click.option(
    "--output",
    default="-",
    help="输出文件路径，默认为标准输出",
)
def schema(output: str):
    """
    显示数据库 Schema

    示例:
        python scripts/init_db.py schema
        python scripts/init_db.py schema --output schema.sql
    """
    setup_logging()
    logger = get_logger(__name__)

    async def _schema():
        try:
            await db_manager.initialize_engine()

            from storage.models.trade_event import Base
            from sqlalchemy.ext.asyncio import create_async_engine
            from asyncio import run

            # 生成 SQL
            from sqlalchemy.schema import CreateSchema
            engine = db_manager._engine

            if engine:
                async with engine.begin() as conn:
                    sql_statements = []

                    def dump(sql, *multiparams, **params):
                        """收集 SQL 语句"""
                        statement = str(sql.compile(dialect=engine.dialect))
                        sql_statements.append(statement)

                    await conn.run_sync(
                        lambda: Base.metadata.create_all(engine, on=dump)
                    )

                schema_sql = "\n\n".join(sql_statements)

                if output == "-":
                    click.echo(schema_sql)
                else:
                    output_path = Path(output)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(schema_sql, encoding="utf-8")
                    logger.info(f"✅ Schema 已导出到: {output_path.absolute()}")

            await db_manager.close()

        except Exception as e:
            logger.error(f"❌ 导出 Schema 失败: {e}")
            sys.exit(1)

    asyncio.run(_schema())


if __name__ == "__main__":
    cli()
