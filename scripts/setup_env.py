"""
AI TradeBot - 环境变量自动配置脚本

功能：
1. 读取 api文档.txt 文件
2. 提取 API Key 和配置项
3. 自动填充到 .env 文件
4. 验证配置完整性
"""
import os
import re
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# API Key 映射表
API_KEY_PATTERNS = {
    # Tushare
    "TUSHARE_TOKEN": [
        r"Tushare\s*Token?\s*[:：]\s*([a-zA-Z0-9]+)",
        r"Tushare\s*[:：]\s*([a-zA-Z0-9]+)",
        r"TUSHARE_TOKEN\s*[:：]\s*([a-zA-Z0-9]+)",
    ],

    # Tavily
    "TAVILY_API_KEY": [
        r"Tavily\s*API?\s*Key?\s*[:：]\s*([a-zA-Z0-9_-]+)",
        r"Tavily\s*[:：]\s*([a-zA-Z0-9_-]+)",
        r"TAVILY_API_KEY\s*[:：]\s*([a-zA-Z0-9_-]+)",
        r"tvly-([a-zA-Z0-9_-]+)",
    ],

    # 智谱 GLM-4
    "ZHIPU_API_KEY": [
        r"智谱\s*API?\s*Key?\s*[:：]\s*([a-zA-Z0-9._-]+)",
        r"GLM-?\d*\s*API?\s*Key?\s*[:：]\s*([a-zA-Z0-9._-]+)",
        r"ZhipuAI?\s*[:：]\s*([a-zA-Z0-9._-]+)",
        r"ZHIPU_API_KEY\s*[:：]\s*([a-zA-Z0-9._-]+)",
    ],

    # MiniMax
    "MINIMAX_API_KEY": [
        r"MiniMax\s*API?\s*Key?\s*[:：]\s*([a-zA-Z0-9_-]+)",
        r"MINIMAX_API_KEY\s*[:：]\s*([a-zA-Z0-9_-]+)",
    ],

    "MINIMAX_GROUP_ID": [
        r"MiniMax\s*Group?\s*ID?\s*[:：]\s*([a-zA-Z0-9_-]+)",
        r"MINIMAX_GROUP_ID\s*[:：]\s*([a-zA-Z0-9_-]+)",
    ],

    # Kimi (Moonshot)
    "KIMI_API_KEY": [
        r"Kimi\s*API?\s*Key?\s*[:：]\s*([a-zA-Z0-9_-]+)",
        r"Moonshot\s*API?\s*Key?\s*[:：]\s*([a-zA-Z0-9_-]+)",
        r"KIMI_API_KEY\s*[:：]\s*([a-zA-Z0-9_-]+)",
        r"sk-([a-zA-Z0-9_-]+)",
    ],

    # 其他可能的配置
    "DATABASE_URL": [
        r"DATABASE_URL\s*[:：]\s*(.+)",
    ],

    "QMT_PATH": [
        r"QMT\s*Path?\s*[:：]\s*(.+)",
        r"QMT_PATH\s*[:：]\s*(.+)",
    ],
}


def extract_api_keys(doc_content: str) -> dict:
    """
    从文档内容中提取 API Keys

    Args:
        doc_content: 文档内容

    Returns:
        提取到的配置字典
    """
    extracted = {}

    for env_key, patterns in API_KEY_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, doc_content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # 跳过占位符
                if value and value.lower() not in ["your_api_key", "your_token", "none", "n/a", "xxxx"]:
                    extracted[env_key] = value
                    break

    return extracted


def load_env_template(env_example_path: Path) -> str:
    """加载 .env.example 模板"""
    if env_example_path.exists():
        return env_example_path.read_text(encoding="utf-8")
    else:
        print(f"警告: .env.example 文件不存在: {env_example_path}")
        return ""


def update_env_file(env_path: Path, api_keys: dict, template: str) -> None:
    """
    更新 .env 文件

    Args:
        env_path: .env 文件路径
        api_keys: 提取的 API Keys
        template: .env.example 模板内容
    """
    # 如果 .env 不存在，使用模板创建
    if not env_path.exists():
        if template:
            content = template
        else:
            content = "# AI TradeBot Environment Variables\n\n"
        print(f"创建新的 .env 文件: {env_path}")
    else:
        # 读取现有 .env
        content = env_path.read_text(encoding="utf-8")
        print(f"更新现有 .env 文件: {env_path}")

    # 更新配置项
    updated_lines = []
    updated_count = 0

    for line in content.split("\n"):
        updated = False
        for env_key, api_value in api_keys.items():
            # 检查是否是该配置项
            if line.strip().startswith(f"{env_key}="):
                # 跳过注释
                if line.strip().startswith("#"):
                    updated_lines.append(line)
                    updated = True
                    break

                # 更新值
                new_line = f'{env_key}="{api_value}"'
                if line != new_line:
                    print(f"  更新: {env_key}=***")
                    updated_lines.append(new_line)
                    updated_count += 1
                    updated = True
                    break

        if not updated:
            updated_lines.append(line)

    # 添加缺失的配置项
    existing_keys = set()
    for line in updated_lines:
        match = re.match(r"^([A-Z_]+)=", line.strip())
        if match and not line.strip().startswith("#"):
            existing_keys.add(match.group(1))

    added_count = 0
    for env_key, api_value in api_keys.items():
        if env_key not in existing_keys:
            print(f"  新增: {env_key}=***")
            updated_lines.append(f'{env_key}="{api_value}"')
            added_count += 1

    # 写入文件
    content = "\n".join(updated_lines)
    env_path.write_text(content, encoding="utf-8")

    print(f"\n[OK] 完成! 更新 {updated_count} 项，新增 {added_count} 项")


def validate_env_config(env_path: Path) -> list:
    """
    验证 .env 配置完整性

    Args:
        env_path: .env 文件路径

    Returns:
        缺失的配置项列表
    """
    required_keys = [
        "TUSHARE_TOKEN",
        "TAVILY_API_KEY",
        "ZHIPU_API_KEY",
        "MINIMAX_API_KEY",
        "MINIMAX_GROUP_ID",
        "KIMI_API_KEY",
    ]

    if not env_path.exists():
        return required_keys

    content = env_path.read_text(encoding="utf-8")
    missing = []

    for key in required_keys:
        # 检查是否存在且非空
        pattern = rf"^{key}\s*=\s*(.+)$"
        match = re.search(pattern, content, re.MULTILINE)
        if not match:
            missing.append(key)
        else:
            value = match.group(1).strip('"\' ')
            # 检查是否为占位符
            if value.lower() in ["your_api_key", "your_token", "none", "n/a", "xxxx"]:
                missing.append(key)

    return missing


def print_extracted_keys(api_keys: dict) -> None:
    """打印提取到的配置项名称（不显示值）"""
    print("\n" + "=" * 60)
    print("从文档中提取到的配置项:")
    print("=" * 60)
    for key in sorted(api_keys.keys()):
        masked_value = "***" if len(api_keys[key]) > 0 else "(空)"
        print(f"  {key} = {masked_value}")
    print("=" * 60)


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("AI TradeBot - 环境变量自动配置")
    print("=" * 60 + "\n")

    # 路径配置
    api_doc_path = project_root / "api文档.txt"
    env_path = project_root / ".env"
    env_example_path = project_root / ".env.example"

    # 检查 API 文档是否存在
    if not api_doc_path.exists():
        print(f"[!] API 文档不存在: {api_doc_path}")
        print(f"请将 api文档.txt 放在项目根目录下")
        print(f"\n当前目录: {project_root}")
        return 1

    # 读取 API 文档
    print(f"[INFO] 读取 API 文档: {api_doc_path}")
    doc_content = api_doc_path.read_text(encoding="utf-8")

    # 提取 API Keys
    print("\n[INFO] 提取 API Keys...")
    api_keys = extract_api_keys(doc_content)

    if not api_keys:
        print("[!] 未从文档中提取到任何 API Key")
        print("请检查 api文档.txt 格式是否正确")
        return 1

    # 打印提取结果（仅显示键名）
    print_extracted_keys(api_keys)

    # 确认是否继续
    print("\n是否继续更新 .env 文件? (y/n): ", end="")
    try:
        confirm = input().strip().lower()
        if confirm != "y":
            print("已取消")
            return 0
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        return 0

    # 加载模板
    template = load_env_template(env_example_path)

    # 更新 .env 文件
    print("\n[INFO] 更新 .env 文件...")
    update_env_file(env_path, api_keys, template)

    # 验证配置
    print("\n[INFO] 验证配置完整性...")
    missing = validate_env_config(env_path)

    if missing:
        print("\n[!] 以下配置项缺失或为占位符:")
        for key in missing:
            print(f"  - {key}")
        print("\n请在 .env 文件中手动补充这些配置项")
    else:
        print("\n[OK] 所有必需配置项已填写!")

    # 安全提醒
    print("\n" + "=" * 60)
    print("安全提醒:")
    print("=" * 60)
    print("1. 请确保 .gitignore 已包含 .env 和 api文档.txt")
    print("2. 不要将包含真实 API Key 的文件上传到公共仓库")
    print("3. 定期更新 API Key 以确保安全")

    # 检查 .gitignore
    gitignore_path = project_root / ".gitignore"
    if gitignore_path.exists():
        gitignore_content = gitignore_path.read_text(encoding="utf-8")
        checks = [
            (".env" in gitignore_content, ".env"),
            ("api文档.txt" in gitignore_content or "api*.txt" in gitignore_content, "api文档.txt"),
        ]

        all_safe = all(safe for safe, _ in checks)

        print("\n.gitignore 检查:")
        for safe, name in checks:
            status = "[OK]" if safe else "[!]"
            print(f"  {status} {name}")

        if not all_safe:
            print("\n[!] 建议更新 .gitignore 以防止敏感信息泄露")
    else:
        print("\n[!] .gitignore 不存在，建议创建")

    print("\n" + "=" * 60)
    print("配置完成!")
    print("=" * 60 + "\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
