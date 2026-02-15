"""
AI TradeBot - Streamlit 作战中心

本地可视化管理看板
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database.session import db_manager, get_db_context
from storage.models.trade_event import TradeEvent, EventStatus
from execution.order.manual_handler import ManualTradeHandler, confirm_manual_trade
from shared.logging import setup_logging, get_logger


# =============================================================================
# 配置
# =============================================================================

st.set_page_config(
    page_title="AI TradeBot 作战中心",
    page_icon="target",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API 基础 URL
API_BASE_URL = "http://localhost:8000"

# =============================================================================
# 初始化
# =============================================================================

setup_logging()
logger = get_logger(__name__)

# =============================================================================
# 工具函数
# =============================================================================

@st.cache_data(ttl=10)  # 缓存10秒
def fetch_active_events() -> Dict[str, Any]:
    """从 API 获取活跃事件"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/public/active_events", timeout=5)
        if response.status_code == 200:
            return response.json()
        return {"total": 0, "events": [], "stats": None}
    except Exception as e:
        st.error(f"获取数据失败: {e}")
        return {"total": 0, "events": [], "stats": None}


@st.cache_data(ttl=30)
def fetch_event_reasoning(event_id: str) -> Optional[Dict[str, Any]]:
    """获取事件推理详情"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/public/reasoning/{event_id}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"获取推理详情失败: {e}")
        return None


@st.cache_data(ttl=5)
def fetch_dashboard_stats() -> Optional[Dict[str, Any]]:
    """获取仪表板统计"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/public/dashboard", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"获取统计数据失败: {e}")
        return None


async def confirm_manual_execution(event_id: str, price: float, quantity: int, notes: str = "") -> bool:
    """确认手动执行"""
    try:
        result = await confirm_manual_trade(
            event_id=event_id,
            actual_price=price,
            actual_quantity=quantity,
            notes=notes
        )
        return result.success
    except Exception as e:
        st.error(f"确认失败: {e}")
        return False


def format_status(status: str) -> str:
    """格式化状态显示"""
    status_map = {
        "observing": "🔍 观察中",
        "pending_confirm": "⏳ 待确认",
        "position_open": "💼 持仓中",
        "take_profit": "✅ 已止盈",
        "stopped_out": "🛑 已止损",
        "logic_expired": "⏰ 已失效",
        "manual_close": "👤 手动平仓",
        "rejected": "❌ 已拒绝"
    }
    return status_map.get(status, status)


def format_direction(direction: str) -> str:
    """格式化方向显示"""
    return "📈 做多" if direction == "long" else "📉 做空"


def get_status_color(status: str) -> str:
    """获取状态颜色"""
    color_map = {
        "observing": "🟢",
        "pending_confirm": "🟡",
        "position_open": "🔵",
        "take_profit": "🟢",
        "stopped_out": "🔴",
        "logic_expired": "⚫",
        "manual_close": "⚪",
        "rejected": "❌"
    }
    return color_map.get(status, "⚪")


# =============================================================================
# 主界面
# =============================================================================

def main():
    """主函数"""

    # =============================================================================
    # 侧边栏
    # =============================================================================
    with st.sidebar:
        st.title("🎯 AI TradeBot")
        st.caption("以终为始 - 量化交易系统")

        st.divider()

        # 系统状态
        st.subheader("系统状态")

        # API 连接状态
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                st.success("✅ API 服务正常")
            else:
                st.error("❌ API 服务异常")
        except:
            st.error("❌ 无法连接 API")

        st.divider()

        # 快捷操作
        st.subheader("快捷操作")

        if st.button("🔄 刷新数据", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        if st.button("📊 查看完整日志", use_container_width=True):
            st.switch_page("logs")  # 假设有日志页面

        st.divider()

        # 关于
        st.subheader("关于")
        st.info("""
        **AI TradeBot v1.0**

        基于多 AI 协同的量化交易系统

        特点：
        - 以终为始的交易哲学
        - 完整的退出规划
        - 硬风控保护
        - 全流程可追溯
        """)

    # =============================================================================
    # 主内容区
    # =============================================================================

    st.title("📊 作战中心")

    # 选项卡
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⏳ 待确认信号",
        "💼 持仓监控",
        "🧠 决策链",
        "🤖 AI实时分析",
        "📈 系统概览"
    ])

    # -------------------------------------------------------------------------
    # Tab 1: 待确认信号
    # -------------------------------------------------------------------------
    with tab1:
        st.subheader("待确认信号", help="AI 已发出信号，等待人工确认下单")

        data = fetch_active_events()

        # 过滤待确认事件
        pending_events = [e for e in data.get("events", []) if e["current_status"] == "pending_confirm"]

        if not pending_events:
            st.info("🎉 当前没有待确认的信号")
        else:
            for event in pending_events:
                with st.container():
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.markdown(f"### {event['ticker']} {event.get('ticker_name', '')}")

                        # 基本信息
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            st.metric("方向", format_direction(event['direction']))
                        with c2:
                            st.metric("置信度", f"{event.get('confidence', 0)*100:.1f}%")
                        with c3:
                            st.metric("状态", format_status(event['current_status']))

                        # AI 观点
                        if event.get('logic_summary'):
                            st.info(f"💡 **AI 观点**: {event['logic_summary']}")

                        # 事件描述
                        if event.get('event_description'):
                            st.caption(f"📝 {event['event_description']}")

                        # 入场计划
                        if event.get('entry_plan'):
                            ep = event['entry_plan']
                            st.write(f"📍 **入场计划**: 触发价 ¥{ep.get('trigger_price', 'N/A')}, 建议数量 {ep.get('suggested_quantity', 'N/A')}股")

                    with col2:
                        st.write(f"**事件 ID**: `{event['id']}`")
                        st.write(f"**创建时间**: {event['created_at'][:19]}")

                        # 一键复制股票代码
                        if st.button("📋 复制代码", key=f"copy_{event['id']}", help="复制股票代码到剪贴板"):
                            import pyperclip
                            try:
                                pyperclip.copy(event['ticker'])
                                st.success(f"已复制: {event['ticker']}")
                            except ImportError:
                                st.warning("需要安装 pyperclip: pip install pyperclip")
                            except Exception as e:
                                st.error(f"复制失败: {e}")

                    st.divider()

                    # 确认表单
                    with st.expander("✅ 确认成交", expanded=True):
                        c1, c2, c3 = st.columns(3)

                        with c1:
                            actual_price = st.number_input(
                                "实际成交价",
                                min_value=0.0,
                                step=0.01,
                                key=f"price_{event['id']}",
                                value=event.get('entry_plan', {}).get('trigger_price')
                            )

                        with c2:
                            actual_quantity = st.number_input(
                                "实际成交量",
                                min_value=1,
                                step=100,
                                key=f"qty_{event['id']}",
                                value=event.get('entry_plan', {}).get('suggested_quantity', 100)
                            )

                        with c3:
                            notes = st.text_input(
                                "备注",
                                key=f"notes_{event['id']}",
                                placeholder="可选填写"
                            )

                        col_left, col_right = st.columns([1, 4])

                        with col_left:
                            if st.button("确认成交", key=f"confirm_{event['id']}", type="primary"):
                                with st.spinner("处理中..."):
                                    # 在新线程中执行异步操作
                                    import threading

                                    def run_confirmation():
                                        loop = asyncio.new_event_loop()
                                        asyncio.set_event_loop(loop)
                                        try:
                                            result = loop.run_until_complete(
                                                confirm_manual_execution(
                                                    event['id'],
                                                    actual_price,
                                                    actual_quantity,
                                                    notes
                                                )
                                            )
                                            if result:
                                                st.success(f"✅ 确认成功！事件已进入持仓状态")
                                                st.cache_data.clear()
                                                st.rerun()
                                            else:
                                                st.error("❌ 确认失败")
                                        finally:
                                            loop.close()

                                    thread = threading.Thread(target=run_confirmation)
                                    thread.start()
                                    thread.join(timeout=5)

                        with col_right:
                            st.caption("确认后事件将进入持仓状态，退出规划器自动开始监控")

                    st.divider()

    # -------------------------------------------------------------------------
    # Tab 2: 持仓监控
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("持仓监控", help="实时监控持仓标的与目标价位")

        data = fetch_active_events()
        position_events = [e for e in data.get("events", []) if e["current_status"] == "position_open"]

        if not position_events:
            st.info("当前没有持仓")
        else:
            for event in position_events:
                with st.container():
                    # 标题行
                    col1, col2, col3 = st.columns([3, 2, 1])

                    with col1:
                        st.markdown(f"### {event['ticker']} {event.get('ticker_name', '')}")

                    with col2:
                        if event.get('actual_entry_price'):
                            st.metric("成本价", f"¥{event['actual_entry_price']:.2f}")
                        if event.get('current_pnl_ratio') is not None:
                            delta = f"{event['current_pnl_ratio']:+.2f}%"
                            st.metric("盈亏", delta, delta_color="normal")

                    with col3:
                        st.write(f"`{event['id']}`")

                    # 进度条：距离目标价
                    if event.get('distance_to_target_pct') is not None:
                        distance = event['distance_to_target_pct']
                        if distance > 0:
                            # 还在目标之下
                            progress_val = max(0, min(100, 100 - distance))
                            st.progress(progress_val / 100)
                            st.caption(f"🎯 距离止盈目标还有 {distance:.2f}%")
                        else:
                            st.success("🎉 已达止盈目标！")

                    # 退出计划详情
                    if event.get('exit_plan'):
                        ep = event['exit_plan']

                        c1, c2, c3 = st.columns(3)

                        with c1:
                            if ep.get('take_profit_price'):
                                st.metric(
                                    "🎯 止盈目标",
                                    f"¥{ep['take_profit_price']:.2f}",
                                    delta=f"+{ep.get('target_return_ratio', 0):.2f}%"
                                )

                        with c2:
                            if ep.get('stop_loss_price'):
                                st.metric("🛑 止损位", f"¥{ep['stop_loss_price']:.2f}")

                        with c3:
                            if ep.get('days_remaining') is not None:
                                st.metric("⏰ 剩余天数", f"{ep['days_remaining']}天")

                    # AI 观点
                    if event.get('logic_summary'):
                        with st.expander("💡 查看 AI 观点"):
                            st.write(event['logic_summary'])

                    st.divider()

    # -------------------------------------------------------------------------
    # Tab 3: 决策链
    # -------------------------------------------------------------------------
    with tab3:
        st.subheader("AI 决策链", help="查看完整的 AI 推理过程")

        # 获取所有事件
        data = fetch_active_events()
        all_events = data.get("events", [])

        if not all_events:
            st.info("暂无事件数据")
        else:
            # 事件选择器
            event_options = {f"{e['ticker']} - {format_status(e['current_status'])}": e for e in all_events}
            selected = st.selectbox("选择事件查看详情", list(event_options.keys()))

            if selected:
                event = event_options[selected]

                # 显示事件摘要
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(f"### {event['ticker']} {event.get('ticker_name', '')}")
                    st.write(f"**事件 ID**: `{event['id']}`")
                    st.write(f"**方向**: {format_direction(event['direction'])}")
                    st.write(f"**状态**: {format_status(event['current_status'])}")

                with col2:
                    if event.get('actual_entry_price'):
                        st.metric("入场价", f"¥{event['actual_entry_price']:.2f}")
                    if event.get('confidence'):
                        st.metric("置信度", f"{event['confidence']*100:.1f}%")

                st.divider()

                # 获取推理详情
                reasoning_data = fetch_event_reasoning(event['id'])

                if reasoning_data:
                    # AI 观点摘要
                    if reasoning_data.get('logic_summary'):
                        st.subheader("💡 AI 观点摘要")
                        st.info(reasoning_data['logic_summary'])

                    # 推理链
                    if reasoning_data.get('reasoning_log'):
                        st.subheader("🔗 推理链路")

                        for i, step in enumerate(reasoning_data['reasoning_log'], 1):
                            with st.expander(f"步骤 {i}: {step.get('step', 'Unknown')}", expanded=False):
                                st.write(f"**时间**: {step.get('timestamp', 'N/A')}")
                                if step.get('description'):
                                    st.write(f"**描述**: {step['description']}")

                                # 显示附加数据
                                if step.get('data'):
                                    st.json(step['data'])

                    # 完整计划
                    col1, col2 = st.columns(2)

                    with col1:
                        if reasoning_data.get('entry_plan_full'):
                            st.subheader("📍 入场计划")
                            st.json(reasoning_data['entry_plan_full'])

                    with col2:
                        if reasoning_data.get('exit_plan_full'):
                            st.subheader("🎯 退出计划")
                            st.json(reasoning_data['exit_plan_full'])

                    # 风控检查
                    if reasoning_data.get('risk_check_details'):
                        st.subheader("🛡️ 风控检查")
                        passed = reasoning_data.get('risk_check_passed', False)
                        if passed:
                            st.success("✅ 风控检查通过")
                        else:
                            st.error("❌ 风控检查未通过")
                        st.json(reasoning_data['risk_check_details'])
                else:
                    st.warning("无法获取推理详情")

    # -------------------------------------------------------------------------
    # Tab 5: AI 实时分析测试
    # -------------------------------------------------------------------------
    with tab5:
        st.subheader("AI 实时推演测试", help="粘贴新闻文本，AI 将实时生成交易逻辑预览")

        st.info("""
        **使用说明**:
        1. 在下方文本框中粘贴新闻或公告文本
        2. 点击"开始分析"按钮
        3. AI 将使用 Kimi + 智谱 GLM-4 协同分析
        4. 查看生成的逻辑预览（不会保存到数据库）
        """)

        # 输入区域
        text_input = st.text_area(
            "输入新闻/公告文本",
            height=200,
            placeholder="请粘贴要分析的新闻或公告文本...",
            help="支持粘贴长文本，AI 将自动提取关键信息"
        )

        # 分析选项
        col1, col2, col3 = st.columns(3)

        with col1:
            ticker_input = st.text_input(
                "股票代码（可选）",
                placeholder="如: 600519.SH",
                help="如果不填，AI 将尝试从文本中识别"
            )

        with col2:
            direction = st.selectbox(
                "交易方向",
                ["long", "short"],
                format_func=lambda x: "做多" if x == "long" else "做空"
            )

        with col3:
            quantity = st.number_input(
                "分析数量（股）",
                min_value=100,
                value=1000,
                step=100
            )

        # 分析按钮
        if st.button("🚀 开始分析", type="primary", use_container_width=True):
            if not text_input.strip():
                st.error("请输入要分析的文本")
            else:
                with st.spinner("AI 正在分析中，请稍候..."):
                    try:
                        # 这里应该调用实际的 AI 分析流程
                        # 暂时模拟返回结果
                        st.success("分析完成！")

                        # 模拟结果显示
                        st.subheader("🧠 AI 推演结果预览")

                        # 模拟 Kimi 摘要
                        with st.expander("📝 Kimi 事实提炼", expanded=True):
                            st.write("""
                            **关键信息提取**:
                            - 公司名称: [从文本中提取]
                            - 事件类型: [财报/公告/政策等]
                            - 关键数据: [营收/利润/增长率等]
                            - 市场影响: [正面/负面/中性]
                            """)

                        # 模拟智谱推演
                        with st.expander("🎯 智谱 GLM-4 博弈推演", expanded=True):
                            col_a, col_b = st.columns(2)

                            with col_a:
                                st.write("**做多理由**:")
                                st.write("- " + text_input[:100] + "...")
                                st.write("- 估值修复空间")
                                st.write("- 技术面支撑")

                            with col_b:
                                st.write("**风险因素**:")
                                st.write("- 宏观经济风险")
                                st.write("- 行业政策变化")
                                st.write("- 市场情绪波动")

                        # 模拟退出计划
                        with st.expander("🎯 退出规划", expanded=True):
                            c1, c2, c3 = st.columns(3)

                            with c1:
                                st.metric("止盈目标", "¥1850.00", "+10.09%")

                            with c2:
                                st.metric("止损位", "¥1600.00", "-4.76%")

                            with c3:
                                st.metric("逻辑时效", "90天")

                        # 操作按钮
                        st.divider()

                        col1, col2, col3 = st.columns(3)

                        with col1:
                            if st.button("💾 保存为草稿", use_container_width=True):
                                st.info("草稿保存功能开发中...")

                        with col2:
                            if st.button("🔄 重新分析", use_container_width=True):
                                st.rerun()

                        with col3:
                            st.write(".")

                        # 温馨提示
                        st.caption("⚠️ 注意: 这只是预览分析，未保存到数据库。要创建正式事件，请使用完整的工作流。")

                    except Exception as e:
                        st.error(f"分析失败: {e}")
                        logger.error(f"AI 分析测试失败: {e}")

        # 历史分析记录（可选）
        st.divider()
        st.subheader("📋 最近分析记录")

        st.info("""
        历史分析记录将显示在这里...

        *功能开发中*
        """)

    # -------------------------------------------------------------------------
    # Tab 4: 系统概览
    # -------------------------------------------------------------------------
    with tab4:
        st.subheader("系统概览", help="全局统计与系统信息")

        stats = fetch_dashboard_stats()

        if stats:
            # 核心指标
            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.metric("总事件数", stats['total_events'])

            with c2:
                st.metric("观察中", stats['observing_count'], delta_color="off")

            with c3:
                st.metric("持仓中", stats['position_open_count'], delta_color="normal")

            with c4:
                st.metric("已完成", stats['closed_count'], delta_color="off")

            st.divider()

            # 盈亏统计
            c1, c2 = st.columns(2)

            with c1:
                if stats.get('total_pnl_ratio') is not None:
                    st.metric("平均收益率", f"{stats['total_pnl_ratio']:.2f}%")

            with c2:
                if stats.get('win_rate') is not None:
                    st.metric("胜率", f"{stats['win_rate']:.1f}%")

            st.divider()

            # 状态分布饼图
            status_data = {
                "观察中": stats['observing_count'],
                "待确认": stats['pending_confirm_count'],
                "持仓中": stats['position_open_count'],
                "已完成": stats['closed_count']
            }

            # 过滤零值
            status_data = {k: v for k, v in status_data.items() if v > 0}

            if status_data:
                fig = px.pie(
                    values=list(status_data.values()),
                    names=list(status_data.keys()),
                    title="事件状态分布",
                    color_discrete_sequence=px.colors.sequential.Teal
                )
                st.plotly_chart(fig, use_container_width=True)

        else:
            st.warning("无法获取统计数据")

    # -------------------------------------------------------------------------
    # 底部：实时日志
    # -------------------------------------------------------------------------
    st.divider()
    st.subheader("📜 实时日志")

    # 日志级别过滤
    log_level = st.selectbox("日志级别", ["全部", "INFO", "WARNING", "ERROR"], key="log_level_filter")

    # 这里可以接入实际的日志流
    # 暂时显示示例
    st.info("""
    **实时日志组件**

    此区域将显示系统最新日志：
    - 感知层抓取信息
    - 决策层分析结果
    - 执行层操作记录
    - 风控检查日志

    *注：完整日志功能需要集成日志收集服务*
    """)


# =============================================================================
# 启动
# =============================================================================

if __name__ == "__main__":
    main()
