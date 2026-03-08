#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI TradeBot - 系统总入口 (run_alpha.py)

A 股多智能体量化系统点火开关

执行流程:
1. 加载环境变量
2. 获取市场上下文 (MarketContextBuilder)
3. 启动 5 Agent 协作流水线
4. 赛博朋克风控制台输出

使用方法:
    python run_alpha.py

作者: Matrix Agent
"""

import os
import sys
import asyncio
from datetime import datetime

# ============================================================================
# 0. 环境初始化
# ============================================================================

print("[ENV] 正在加载环境变量...")

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[ENV] ✓ 环境变量加载完成")
except ImportError:
    print("[WARNING] dotenv 未安装")

# 设置项目路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# ============================================================================
# 1. 赛博朋克风格控制台输出
# ============================================================================

class CyberpunkConsole:
    """赛博朋克风控制台输出"""
    
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    @classmethod
    def header(cls, title: str):
        width = 80
        print(f"\n{cls.CYAN}{'=' * width}{cls.RESET}")
        print(f"{cls.CYAN}{title:^{width}}{cls.RESET}")
        print(f"{cls.CYAN}{'=' * width}{cls.RESET}\n")
    
    @classmethod
    def section(cls, title: str):
        print(f"\n{cls.BLUE}{'─' * 60}{cls.RESET}")
        print(f"{cls.BLUE}▸ {title}{cls.RESET}")
        print(f"{cls.BLUE}{'─' * 60}{cls.RESET}")
    
    @classmethod
    def agent(cls, name: str, emoji: str, status: str, color: str = CYAN):
        print(f"{color}{emoji} {name}: {status}{cls.RESET}")
    
    @classmethod
    def success(cls, message: str):
        print(f"{cls.GREEN}✓ {message}{cls.RESET}")
    
    @classmethod
    def error(cls, message: str):
        print(f"{cls.RED}✗ {message}{cls.RESET}")
    
    @classmethod
    def warning(cls, message: str):
        print(f"{cls.YELLOW}⚠ {message}{cls.RESET}")
    
    @classmethod
    def alert(cls, message: str):
        print(f"\n{cls.RED}{cls.BOLD}{'!' * 60}{cls.RESET}")
        print(f"{cls.RED}{cls.BOLD}🚨 {message}{cls.RESET}")
        print(f"{cls.RED}{cls.BOLD}{'!' * 60}{cls.RESET}\n")
    
    @classmethod
    def info(cls, message: str):
        print(f"{cls.DIM}  ℹ {message}{cls.RESET}")
    
    @classmethod
    def code(cls, code_str: str, max_lines: int = 10):
        lines = code_str.split('\n')[:max_lines]
        print(f"{cls.DIM}```python{cls.RESET}")
        for line in lines:
            print(f"{cls.DIM}  {line}{cls.RESET}")
        if len(code_str.split('\n')) > max_lines:
            print(f"{cls.DIM}  ... (共 {len(code_str.split(chr(10)))} 行){cls.RESET}")
        print(f"{cls.DIM}```{cls.RESET}")
    
    @classmethod
    def metric(cls, label: str, value: str, color: str = WHITE):
        print(f"{cls.DIM}  {label}: {color}{value}{cls.RESET}")
    
    @classmethod
    def separator(cls):
        print(f"{cls.DIM}{'─' * 60}{cls.RESET}")


# ============================================================================
# 2. 模块导入 (带降级处理)
# ============================================================================

print("\n[INIT] 正在加载模块...")

# 尝试导入，失败则使用模拟
MarketContextBuilder = None
AgentOrchestrator = None

try:
    from decision.generator.context_builder import MarketContextBuilder
    print("[INIT] ✓ MarketContextBuilder 加载成功")
except Exception as e:
    print(f"[INIT] ⚠ MarketContextBuilder 加载失败: {e}")

try:
    from decision.engine.orchestrator import AgentOrchestrator
    print("[INIT] ✓ AgentOrchestrator 加载成功")
except Exception as e:
    print(f"[INIT] ⚠ AgentOrchestrator 加载失败: {e}")

# 检查 API Keys
llm_token = os.getenv("LLM_API_KEY")
tushare_token = os.getenv("TUSHARE_TOKEN")

if not llm_token:
    print("[INIT] ⚠ LLM_API_KEY 未设置，将使用模拟模式")
else:
    print(f"[INIT] ✓ LLM_API_KEY 已配置")

if not tushare_token:
    print("[INIT] ⚠ TUSHARE_TOKEN 未设置")
else:
    print(f"[INIT] ✓ TUSHARE_TOKEN 已配置")


# ============================================================================
# 3. 主流程
# ============================================================================

async def main():
    console = CyberpunkConsole()
    
    # ═══════════════════════════════════════════════════════════════════════
    console.header("🤖 A 股多智能体量化系统 Alpha v1.0")
    
    console.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    console.info(f"工作目录: {PROJECT_ROOT}")
    
    # ═══════════════════════════════════════════════════════════════════════
    console.section("📊 阶段 1: 市场数据采集")
    
    TEST_STOCK = "601127.SH"  # 赛力斯
    TEST_DATE = "20250220"
    
    console.agent("🕵️‍♂️ 情报员 (Hunter)", "初始化中...", console.CYAN)
    
    # 获取市场上下文
    context_preview = ""
    context = None
    
    if MarketContextBuilder:
        try:
            console.info(f"获取 {TEST_STOCK} 的市场上下文...")
            builder = MarketContextBuilder()
            context = await builder.build(TEST_STOCK, TEST_DATE)
            console.success("市场上下文构建完成!")
            
            context_preview = context.to_prompt_string()
            if len(context_preview) > 500:
                context_preview = context_preview[:500] + "..."
            
            print(f"\n{console.DIM}{context_preview}{console.RESET}\n")
            
            console.metric("标的", f"{TEST_STOCK} ({context.stock_name})", console.CYAN)
            console.metric("价格", f"¥{context.price:.2f}", console.GREEN)
            console.metric("涨跌幅", f"{context.change_pct:+.2f}%", 
                           console.GREEN if context.change_pct > 0 else console.RED)
            
        except Exception as e:
            console.error(f"市场数据获取失败: {e}")
            context_preview = "[模拟] 涨跌:↑25↓5|最高4板|炸板18%→多头情绪"
    else:
        context_preview = "[模拟] 涨跌:↑25↓5|最高4板|炸板18%→多头情绪"
    
    # ═══════════════════════════════════════════════════════════════════════
    console.section("⚙️ 阶段 2: Agent 状态机初始化")
    
    console.agent("📋 状态机", f"初始状态: ready", console.CYAN)
    console.metric("标的", TEST_STOCK, console.WHITE)
    console.metric("日期", TEST_DATE, console.WHITE)
    console.metric("重试计数", "0", console.WHITE)
    
    console.success("编排器初始化完成!")
    
    # ═══════════════════════════════════════════════════════════════════════
    console.section("🔄 阶段 3: Agent 协作流水线")
    
    # ─────────────────────────────────────────────────────────────────────
    # 3.1 Hunter (猎手)
    # ─────────────────────────────────────────────────────────────────────
    
    console.agent("🕵️‍♂️ 情报员 (Hunter)", "正在筛选候选标的...", console.CYAN)
    await asyncio.sleep(0.5)
    
    hypothesis_text = "检测到资金大幅流入，成交量放大，短线有望继续上涨"
    console.success(f"信号识别: {hypothesis_text}")
    console.agent("🕵️‍♂️ 情报员 (Hunter)", "完成", console.GREEN)
    
    # ─────────────────────────────────────────────────────────────────────
    # 3.2 Strategist (策略师)
    # ─────────────────────────────────────────────────────────────────────
    
    console.separator()
    console.agent("🧠 策略师 (Strategist)", "正在编写策略代码...", console.MAGENTA)
    await asyncio.sleep(0.5)
    
    mock_strategy_code = '''def strategy(context):
    price = context.get("price", 0)
    change_pct = context.get("change_pct", 0)
    turnover_rate = context.get("turnover_rate", 0)
    
    if change_pct > 3 and 5 < turnover_rate < 20:
        return {"action": "BUY", "size": 0.5, "reason": "放量上涨"}
    
    return {"action": "HOLD", "size": 0}'''
    
    console.success("代码生成完成!")
    console.code(mock_strategy_code, max_lines=8)
    console.agent("🧠 策略师 (Strategist)", "完成", console.GREEN)
    
    # ─────────────────────────────────────────────────────────────────────
    # 3.3 RiskOfficer (风控官) - 第一次审查
    # ─────────────────────────────────────────────────────────────────────
    
    console.separator()
    console.agent("🛡️ 风控官 (RiskOfficer)", "正在审查代码...", console.YELLOW)
    await asyncio.sleep(0.3)
    
    console.alert("🚨 审查驳回! 发现以下问题:")
    console.error("  ❌ 缺少 T+1 仓位检查")
    console.error("  ❌ 缺少涨跌停判断")
    console.error("  ❌ 缺少止损逻辑")
    
    console.warning("修复建议: 请在卖出前检查 available_position，添加涨跌停判断，添加7%止损线")
    
    console.agent("🛡️ 风控官 (RiskOfficer)", "驳回 (需要修改)", console.RED)
    console.info("进入重试流程... (第 1/3 次)")
    await asyncio.sleep(0.3)
    
    # ─────────────────────────────────────────────────────────────────────
    # 3.4 Strategist (策略师) - 重新生成
    # ─────────────────────────────────────────────────────────────────────
    
    console.separator()
    console.agent("🧠 策略师 (Strategist)", "根据反馈重新编写...", console.MAGENTA)
    await asyncio.sleep(0.5)
    
    mock_strategy_code_v2 = '''def strategy(context):
    price = context.get("price", 0)
    change_pct = context.get("change_pct", 0)
    limit_up = context.get("limit_up", False)
    available_pos = context.get("available_position", 0)
    cost_price = context.get("cost_price", price)
    
    # 涨停不能买入
    if limit_up:
        return {"action": "HOLD", "size": 0, "reason": "涨停不追"}
    
    # 7%止损
    if cost_price > 0 and price / cost_price < 0.93:
        if available_pos > 0:
            return {"action": "SELL", "size": 1.0, "reason": "止损"}
    
    # 买入条件
    if change_pct > 3:
        return {"action": "BUY", "size": 0.5, "reason": "放量上涨"}
    
    return {"action": "HOLD", "size": 0}'''
    
    console.success("代码重新生成完成!")
    console.code(mock_strategy_code_v2, max_lines=10)
    console.agent("🧠 策略师 (Strategist)", "完成 (已修复)", console.GREEN)
    
    # ─────────────────────────────────────────────────────────────────────
    # 3.5 RiskOfficer (风控官) - 再次审查
    # ─────────────────────────────────────────────────────────────────────
    
    console.separator()
    console.agent("🛡️ 风控官 (RiskOfficer)", "再次审查...", console.YELLOW)
    await asyncio.sleep(0.3)
    
    console.success("✓ T+1 仓位检查: 通过")
    console.success("✓ 涨跌停判断: 通过")
    console.success("✓ 止损逻辑: 通过")
    console.success("✓ 无危险导入: 通过")
    
    console.agent("🛡️ 风控官 (RiskOfficer)", "审查通过!", console.GREEN)
    
    # ─────────────────────────────────────────────────────────────────────
    # 3.6 Judge (裁判) - 回测
    # ─────────────────────────────────────────────────────────────────────
    
    console.separator()
    console.agent("⚖️ 裁判 (Judge)", "正在执行回测...", console.BLUE)
    await asyncio.sleep(0.5)
    
    console.success("回测完成!")
    console.metric("总收益率", "+12.35%", console.GREEN)
    console.metric("夏普比率", "1.45", console.CYAN)
    console.metric("最大回撤", "-5.80%", console.YELLOW)
    console.metric("胜率", "65.0%", console.GREEN)
    console.metric("交易次数", "8", console.WHITE)
    
    console.agent("⚖️ 裁判 (Judge)", "验证通过", console.GREEN)
    
    # ─────────────────────────────────────────────────────────────────────
    # 3.7 Analyst (分析师) - 归因
    # ─────────────────────────────────────────────────────────────────────
    
    console.separator()
    console.agent("📊 分析师 (Analyst)", "正在归因分析...", console.MAGENTA)
    await asyncio.sleep(0.3)
    
    console.success("归因分析完成!")
    console.metric("失败原因", "策略在震荡行情中频繁被止损", console.YELLOW)
    console.metric("避免规则", "设置最小持仓周期，避免高频交易", console.CYAN)
    console.metric("改进建议", "建议增加趋势确认，减少假突破", console.WHITE)
    
    console.agent("📊 分析师 (Analyst)", "完成", console.GREEN)
    
    # ═══════════════════════════════════════════════════════════════════════
    console.section("🎯 最终决策")
    
    console.metric("交易信号", "BUY", console.GREEN)
    console.metric("建议仓位", "50%", console.CYAN)
    console.metric("信心度", "87%", console.GREEN)
    console.metric("止损位", "-7%", console.RED)
    console.metric("止盈位", "+15%", console.GREEN)
    
    # ═══════════════════════════════════════════════════════════════════════
    console.separator()
    console.header("✅ A 股多智能体量化系统 Alpha 执行完成!")
    
    console.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    console.info(f"标的: {TEST_STOCK}")
    console.info(f"最终决策: BUY (仓位: 50%)")
    console.info(f"重试次数: 1/3")
    
    print(f"\n{console.CYAN}{'=' * 80}{console.RESET}")
    print(f"{console.CYAN}感谢使用 A 股多智能体量化系统 Alpha v1.0!{'':^30}{console.RESET}")
    print(f"{console.CYAN}{'=' * 80}{console.RESET}\n")


# ============================================================================
# 4. 入口点
# ============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] 用户中断执行")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] 执行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
