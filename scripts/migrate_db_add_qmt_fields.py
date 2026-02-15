#!/usr/bin/env python3
"""
AI TradeBot - 数据库 Schema 更新脚本

为 TradeEvent 表添加 QMT 对账相关字段
"""
import sys
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 新增字段列表
new_columns = [
    ("qmt_actual_position", "TEXT", "QMT 实际持仓（JSON 格式）"),
    ("qmt_sync_time", "TIMESTAMP", "QMT 同步时间"),
    ("qmt_deviation", "REAL", "QMT 偏差金额"),
    ("qmt_missing_shares", "BOOLEAN", "QMT 漏单（True=有漏单）"),
    ("postmortem_report", "TEXT", "AI 复盘报告（JSON 格式）"),
]

def print_step(step_num: int, step_name: str):
    """打印步骤横幅"""
    print("\n" + "=" * 70)
    print(f"  步骤 {step_num}: {step_name}")
    print("=" * 70)
    print()

def run_migration():
    """执行数据库迁移"""
    print_step(1, "检查数据库文件")

    db_path = project_root / "data" / "database" / "aitradebot.db"

    if not db_path.exists():
        logger.error(f"数据库文件不存在: {db_path}")
        print(f"请先运行: python scripts/init_db.py")
        return False

    print_step(2, "添加新字段到 TradeEvent 表")

    # 导入 SQLAlchemy
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(f"sqlite:///{db_path}")

        with engine.connect() as conn:
            # 开启外键约束
            conn.execute("PRAGMA foreign_keys=OFF")

            # 添加新字段
            for column_name, column_type in new_columns:
                column_sql = f"ALTER TABLE trade_events ADD COLUMN {column_name} {column_type}"

                print(f"  执行: {column_sql}")
                try:
                    conn.execute(column_sql)
                    print(f"  ✓ 成功添加字段: {column_name}")
                except Exception as e:
                    print(f"  ✗ 失败: {str(e)}")
                    logger.error(f"添加字段失败: {column_name}: {e}")

            conn.commit()
            print_step(3, "验证字段添加结果")

            # 检查字段是否成功添加
            result = conn.execute("PRAGMA table_info(trade_events)")
            columns_info = result[0]

            if columns_info:
                existing_columns = [row[1] for row in columns_info]
                print(f"\n现有字段:")
                for row in existing_columns:
                    print(f"  - {row[1]} ({row[2]})")

                # 检查新字段是否在列表中
                new_fields = [col[1] for col in new_columns if col[1] not in existing_columns]

                if new_fields:
                    print(f"\n✓ 新字段已添加:")
                    for field in new_fields:
                        print(f"  ✓ {field}")
                else:
                    print(f"\n所有字段已存在，无需添加")

            print_step(4, "创建索引（可选）")

            # 为复盘数据创建独立表（如果需要）
            create_postmortem_table_sql = """
CREATE TABLE IF NOT EXISTS postmortem_reports (
                id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                report_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ai_thesis TEXT,
                market_fact TEXT,
                accuracy_score REAL,
                strategy_optimization TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """

            try:
                conn.execute(create_postmortem_table_sql)
                print(f"  ✓ 成功创建 postmortem_reports 表")
                logger.info("复盘表创建成功")
            except Exception as e:
                print(f"  ✗ 创建失败: {str(e)}")
                    logger.error(f"创建复盘表错误: {e}")

            conn.commit()
            conn.close()

    print_step(5, "数据库 Schema 更新完成")
    print("\n" + "=" * 70)
    print(f"  系统: 可以开始使用新的 QMT 对账字段了！")
    print("=" * 70)
    print()
    print("📋 后续步骤:")
    print("  1. 创建 execution/monitor/ledger_sync.py")
    print("  2. 创建 decision/engine/postmortem.py")
    print("  3. 更新 API 路由支持复盘")
    print("  4. 创建 ui/pages/history.py（历史复盘页面）")
    print("  5. 测试 QMT 同步功能（可选）")
    print("  6. 集成测试 run_all.py")
    print()
    print("\n" + "=" * 70)
    print("💡 提示: 如果您的 QMT 已经在运行，可以:")
    print("    - 使用 python scripts/test_qmt_sync.py 测试读取实际持仓")
    print("    - 查看 Streamlit 界面的「持仓对比」标签")
    print("    - 系统会自动检测偏差并记录")
    print()

if __name__ == "__main__":
    run_migration()
