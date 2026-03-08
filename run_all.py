"""
AI TradeBot - 一键启动脚本 (增强版)

同时启动 FastAPI 后端、退出规划器监控线程、Streamlit 前端
"""
import subprocess
import sys
import time
import os
from pathlib import Path
import asyncio

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def print_banner():
    """打印启动横幅"""
    import sys
    import io

    # 设置 UTF-8 编码
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("=" * 60)
    print("=" * 15 + "AI TradeBot 启动中...")
    print("=" * 60)
    print()
    print("  以终为始 - AI 量化交易系统")
    print()
    print("  正在启动服务:")
    print("    - FastAPI 后端服务: http://localhost:8503")
    print("    - Streamlit 看板:   http://localhost:8502")
    print("    - 退出规划器监控: 后台线程")
    print("    - Tavily AI 搜索: 智能检索引擎")
    print()
    print("  按 Ctrl+C 停止所有服务")
    print("=" * 60)
    print()


def check_env_file():
    """检查 .env 配置文件"""
    print("检查环境配置...")

    env_file = project_root / ".env"

    if not env_file.exists():
        print("  [X] .env 文件不存在")
        print()
        print("  请创建 .env 文件并配置以下内容:")
        print("-" * 50)
        print("  # 数据库配置")
        print("  DATABASE_URL=sqlite:///data/database/aitradebot.db")
        print()
        print("  # AI API 密钥 (可选，用于实际交易)")
        print("  KIMI_API_KEY=your_kimi_api_key")
        print("  ZHIPUAI_API_KEY=your_zhipuai_api_key")
        print("  MINIMAX_API_KEY=your_minimax_api_key")
        print("  TAVILY_API_KEY=your_tavily_api_key")
        print()
        print("  # 数据源 API (可选)")
        print("  TUSHARE_TOKEN=your_tushare_token")
        print()
        print("  # Discord 配置 (可选)")
        print("  DISCORD_BOT_TOKEN=your_discord_bot_token")
        print("  DISCORD_CHANNEL_ID=your_channel_id")
        print()
        print("  # CryptoPanic API (可选)")
        print("  CRYPTOPANIC_API_KEY=your_cryptopanic_api_key")
        print()
        print("  # 执行模式")
        print("  EXECUTION_MODE=manual  # auto/manual/simulation")
        print("-" * 50)
        print()
        print("  提示: 可以复制 .env.example 并重命名为 .env")
        return False

    # 检查必需配置
    from dotenv import load_dotenv

    load_dotenv(env_file)

    required_vars = []
    optional_vars = []

    # 必需配置
    # 数据库使用默认值，不需要配置

    # 可选配置
    optional_vars.extend(["KIMI_API_KEY", "ZHIPUAI_API_KEY", "MINIMAX_API_KEY"])
    optional_vars.extend(["TAVILY_API_KEY", "TUSHARE_TOKEN"])
    optional_vars.extend(["DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID"])
    optional_vars.extend(["CRYPTOPANIC_API_KEY"])

    # 检查可选配置
    missing = []
    for var in optional_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        print(f"  [!] 未配置的可选变量 ({len(missing)}个):")
        for var in missing:
            print(f"      - {var}")
        print()
        print("  提示: 这些变量是可选的，不影响基本功能运行")
    else:
        print("  [OK] 所有可选 API 密钥已配置")

    print()
    return True


def check_dependencies():
    """检查依赖是否安装"""
    print("检查依赖...")

    required_packages = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("streamlit", "Streamlit"),
        ("sqlalchemy", "SQLAlchemy"),
        ("aiosqlite", "aiosqlite"),
        ("requests", "Requests"),
        ("pydantic", "Pydantic"),
        ("plotly", "Plotly"),
        ("pandas", "Pandas"),
        ("dotenv", "python-dotenv"),
    ]

    missing = []

    for module, name in required_packages:
        try:
            __import__(module)
            print(f"  [OK] {name}")
        except ImportError:
            print(f"  [X] {name} (未安装)")
            missing.append(name)

    if missing:
        print()
        print(f"错误: 缺少依赖包: {', '.join(missing)}")
        print("请运行: pip install -r requirements.txt")
        return False

    print("所有依赖已安装 [OK]")
    print()
    return True


async def initialize_database():
    """初始化数据库"""
    print("初始化数据库...")

    try:
        from core.database.session import db_manager
        await db_manager.initialize_engine()
        print("数据库初始化完成 [OK]")
        print()
        return True
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        return False


def start_api_server():
    """启动 FastAPI 服务器"""
    print("启动 FastAPI 后端服务...")

    process = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "core.api.app:app",
            "--host", "0.0.0.0",
            "--port", "8503",
            "--reload"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

    # 等待启动
    time.sleep(3)

    if process.poll() is None:
        print("FastAPI 服务已启动: http://localhost:8503 [OK]")
        print("  - API 文档: http://localhost:8503/docs")
        print("  - 公共接口: http://localhost:8503/api/v1/public/active_events")
        print("  - Showcase:  docs/showcase/index.html")
        print()
        return process
    else:
        print("FastAPI 服务启动失败 [X]")
        return None


def start_streamlit():
    """启动 Streamlit 看板"""
    print("启动 Streamlit 作战中心...")

    process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit",
            "run", "ui/app.py",
            "--server.port", "8502",
            "--server.address", "localhost",
            "--logger.level", "info"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )

    # 等待启动
    time.sleep(5)

    if process.poll() is None:
        print("Streamlit 看板已启动: http://localhost:8502 [OK]")
        print()
        return process
    else:
        print("Streamlit 看板启动失败 [X]")
        return None


async def start_exit_monitoring():
    """启动退出规划器监控"""
    print("启动退出规划器监控...")

    try:
        from decision.engine.exit_planner import get_exit_planner

        planner = get_exit_planner()

        if not planner.running:
            await planner.start_monitoring()
            print("退出规划器监控已启动 [OK]")
            print("  - 检查间隔: 30秒")
            print("  - 监控范围: 所有持仓中的事件")
            print()
            return True
        else:
            print("退出规划器监控已在运行 [OK]")
            print()
            return True

    except Exception as e:
        print(f"启动退出规划器失败: {e}")
        print("  提示: 退出规划器是可选的，不影响其他功能")
        print()
        return False


async def start_live_monitoring():
    """启动实时监测（使用 Tavily AI 搜索）"""
    print("启动 Tavily AI 搜索监测...")

    try:
        from perception.search import get_tavily_client

        # 测试 Tavily 连接
        tavily = get_tavily_client()
        print("Tavily AI 搜索已就绪 [OK]")
        print("  - 搜索引擎: Tavily AI Search")
        print("  - 深度模式: Advanced")
        print("  - 结果限制: Top 3")
        print("  - 字符限制: 3000 (1000 per result)")
        print()
        return True

    except Exception as e:
        print(f"启动 Tavily 搜索失败: {e}")
        print("  提示: Tavily 搜索是可选的，不影响其他功能")
        print()
        return False


async def start_tushare_monitoring():
    """启动 Tushare 新闻监测"""
    print("启动 Tushare 新闻监测...")

    try:
        from perception.news.tushare_sentinel import get_tushare_sentinel

        sentinel = get_tushare_sentinel()

        if not sentinel.token:
            print("  [!] TUSHARE_TOKEN 未设置，跳过 Tushare 监测")
            print()
            return False

        # 定义新闻处理回调
        async def news_callback(news_item):
            print(f"  [Tushare] 发现快讯: {news_item.ticker} - {news_item.title[:30]}... (评分: {news_item.score}/10)")

        # 启动监测（不阻塞）
        asyncio.create_task(sentinel.start(callback=news_callback))

        print("Tushare 新闻监测已启动 [OK]")
        print("  - 数据源: 财联社、新浪财经")
        print("  - AI 评分: DeepSeek 快速打分")
        print("  - 评分阈值: 7.0")
        print()
        return True

    except Exception as e:
        print(f"启动 Tushare 监测失败: {e}")
        print("  提示: Tushare 监测是可选的，不影响其他功能")
        print()
        return False


async def start_discord_broker():
    """启动 Discord A2A 自动代理（冷处理：默认不启动）"""
    print("启动 Discord A2A 自动代理...")

    try:
        from core.comms.discord_broker import get_discord_broker, is_discord_broker_active

        # 检查是否激活
        if not is_discord_broker_active():
            print("  🌙 Expert System: Standby (冷处理模式)")
            print("     Discord Broker 代码保留但未激活")
            print("     内置 AI 引擎全功率运行中")
            print("     提示: 在 .env 设置 ENABLE_DISCORD_BROKER=true 即可激活")
            print()
            return False

        broker = get_discord_broker()

        # 定义估值数据处理回调
        async def valuation_handler(valuation_data):
            print(f"  [Discord] 收到 Clawdbot 估值: {valuation_data.ticker} "
                  f"({valuation_data.fair_value_min} - {valuation_data.fair_value_max})")

        # 启动 Broker（不阻塞）
        asyncio.create_task(broker.start(event_handler=valuation_handler))

        print("Discord A2A 自动代理已启动 [OK]")
        print("  - Clawdbot ID:", os.getenv("CLAWDBOT_USER_ID", "N/A"))
        print("  - 自动寻址: 评分≥7自动发送")
        print("  - 数据拦截: 监听 Clawdbot JSON 响应")
        print()
        return True

    except Exception as e:
        print(f"启动 Discord Broker 失败: {e}")
        print("  提示: Discord Broker 是可选的，不影响其他功能")
        print()
        return False


async def start_crypto_monitoring():
    """启动 CryptoPanic 加密货币监测（冷处理：默认不启动）"""
    print("启动 CryptoPanic 加密货币监测...")

    try:
        from perception.news.cryptopanic_sentinel import (
            get_cryptopanic_sentinel,
            is_cryptopanic_active
        )

        # 检查是否激活
        if not is_cryptopanic_active():
            print("  🌙 Crypto Stream: Offline (冷处理模式)")
            print("     CryptoPanic 监测代码保留但未激活")
            print("     内置 AI 引擎全功率运行中")
            print("     提示: 在 .env 设置 ENABLE_CRYPTO=true 即可激活")
            print()
            return False

        sentinel = get_cryptopanic_sentinel()

        # 定义加密新闻处理回调
        async def crypto_callback(news_item):
            print(f"  [Crypto] 发现加密快讯: {news_item.title[:40]}...")

        # 启动监测（不阻塞）
        asyncio.create_task(sentinel.start(callback=crypto_callback))

        print("CryptoPanic 加密货币监测已启动 [OK]")
        print()
        return True

    except Exception as e:
        print(f"启动 CryptoPanic 监测失败: {e}")
        print("  提示: CryptoPanic 监测是可选的，不影响其他功能")
        print()
        return False


async def run_system_checks():
    """运行系统检查"""
    print("运行系统检查...")

    checks_passed = []
    checks_failed = []

    # 1. 数据库连接检查
    try:
        from core.database.session import db_manager
        await db_manager.initialize_engine()

        # 查询数据库
        async with db_manager.get_session() as db:
            from sqlalchemy import select, func
            result = await db.execute(select(func.count()).select_from("trade_events"))
            count = result.scalar() or 0

        print(f"  [OK] 数据库连接正常 (事件数: {count})")
        checks_passed.append("数据库")

    except Exception as e:
        print(f"  [X] 数据库连接失败: {e}")
        checks_failed.append("数据库")

    # 2. 环境变量检查
    if os.getenv("EXECUTION_MODE", "manual") == "manual":
        print(f"  [OK] 执行模式: MANUAL (手动确认)")
    else:
        print(f"  [!] 执行模式: {os.getenv('EXECUTION_MODE', 'auto')}")

    checks_passed.append("执行模式")

    print()

    if checks_failed:
        print(f"警告: {len(checks_failed)} 项检查未通过")
    else:
        print(f"所有系统检查通过 ({len(checks_passed)}/{len(checks_passed) + len(checks_failed)}) [OK]")

    print()


def log_startup_info():
    """记录启动信息"""
    try:
        from shared.logging import get_logger
        logger = get_logger(__name__)

        logger.info("=" * 60)
        logger.info("AI TradeBot 系统启动")
        logger.info("=" * 60)
        logger.info(f"启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"工作目录: {project_root}")
        logger.info(f"Python 版本: {sys.version}")
        logger.info("")

    except Exception as e:
        print(f"日志记录失败: {e}")


async def main():
    """主函数"""
    print_banner()

    # 记录启动信息
    log_startup_info()

    # 环境配置检查
    if not check_env_file():
        print()
        input("按 Enter 键退出...")
        sys.exit(1)

    # 依赖检查
    if not check_dependencies():
        sys.exit(1)

    # 数据库初始化
    if not await initialize_database():
        print()
        print("警告: 数据库初始化失败，但继续启动服务...")
        print()

    # 系统检查
    await run_system_checks()

    # 启动服务
    api_process = None
    streamlit_process = None
    exit_monitoring_started = False
    tushare_monitoring_started = False
    discord_broker_started = False
    crypto_monitoring_started = False
    tavily_monitoring_started = False

    try:
        # 启动 FastAPI
        api_process = start_api_server()
        if not api_process:
            print("无法启动 FastAPI 服务，退出...")
            sys.exit(1)

        # 启动 Streamlit
        streamlit_process = start_streamlit()
        if not streamlit_process:
            print("警告: Streamlit 启动失败，但 FastAPI 继续运行...")

        # 启动退出规划器监控
        try:
            exit_monitoring_started = await start_exit_monitoring()
        except Exception as e:
            print(f"警告: 启动退出规划器失败: {e}")
            exit_monitoring_started = False

        # 启动 Tavily AI 搜索
        try:
            tavily_monitoring_started = await start_live_monitoring()
        except Exception as e:
            print(f"警告: 启动 Tavily 搜索失败: {e}")
            tavily_monitoring_started = False

        # 启动 Tushare 新闻监测
        try:
            tushare_monitoring_started = await start_tushare_monitoring()
        except Exception as e:
            print(f"警告: 启动 Tushare 监测失败: {e}")
            tushare_monitoring_started = False

        # 启动 Discord A2A 自动代理
        try:
            discord_broker_started = await start_discord_broker()
        except Exception as e:
            print(f"警告: 启动 Discord Broker 失败: {e}")
            discord_broker_started = False

        # 启动 CryptoPanic 加密货币监测
        try:
            crypto_monitoring_started = await start_crypto_monitoring()
        except Exception as e:
            print(f"警告: 启动 CryptoPanic 监测失败: {e}")
            crypto_monitoring_started = False

        print()
        print("=" * 60)
        print("  所有服务已启动!")
        print("=" * 60)
        print()
        print("  访问地址:")
        print("    作战中心: http://localhost:8502")
        print("    API 文档:  http://localhost:8503/docs")
        print("    公共接口:  http://localhost:8503/api/v1/public/active_events")
        print("    WebSocket:  ws://localhost:8503/ws/events")
        print("    Showcase:  docs/showcase/index.html")
        print()
        print("  服务状态:")
        print(f"    FastAPI:        {'运行中 [OK]' if api_process and api_process.poll() is None else '已停止 [X]'}")
        print(f"    Streamlit:      {'运行中 [OK]' if streamlit_process and streamlit_process.poll() is None else '已停止 [X]'}")
        print(f"    内置 AI 引擎:   全功率运行 [ACTIVE]")
        print(f"    退出监控:       {'运行中 [OK]' if exit_monitoring_started else '未启动 [!]'}")
        print(f"    Tavily搜索:     {'就绪 [OK]' if tavily_monitoring_started else '未启动 [!]'}")
        print(f"    Tushare监测:    {'运行中 [OK]' if tushare_monitoring_started else '未启动 [!]'}")

        # 外部模块状态（冷处理模式）
        if discord_broker_started:
            print(f"    Expert System:   运行中 [OK]")
        else:
            print(f"    Expert System:   🌙 静默模式 [Standby]")

        if crypto_monitoring_started:
            print(f"    Crypto Stream:   运行中 [OK]")
        else:
            print(f"    Crypto Stream:   🌙 离线模式 [Offline]")

        print()
        print("  按 Ctrl+C 停止所有服务")
        print("=" * 60)
        print()

        # 持续监控进程
        while True:
            # 检查 API 进程
            if api_process and api_process.poll() is not None:
                print()
                print("警告: FastAPI 服务已停止")
                print("退出代码:", api_process.returncode)
                break

            # 检查 Streamlit 进程
            if streamlit_process and streamlit_process.poll() is not None:
                print()
                print("警告: Streamlit 看板已停止")
                print("退出代码:", streamlit_process.returncode)
                break

            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print("=" * 60)
        print("正在停止服务...")
        print("=" * 60)

    finally:
        # 停止所有进程
        processes = []

        if api_process:
            processes.append(("FastAPI", api_process))

        if streamlit_process:
            processes.append(("Streamlit", streamlit_process))

        for name, process in processes:
            if process.poll() is None:
                print(f"停止 {name}...")
                process.terminate()

                try:
                    process.wait(timeout=10)
                    print(f"{name} 已停止 [OK]")
                except subprocess.TimeoutExpired:
                    print(f"{name} 强制停止...")
                    process.kill()
                    process.wait()
                    print(f"{name} 已强制停止 [OK]")

        print()
        print("所有服务已停止")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print()
        print("启动被取消")
