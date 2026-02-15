"""
AI TradeBot - API Configuration Check Script

Check all API key configuration status
"""
import os
import sys
from pathlib import Path
from typing import Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv


# API configurations to check
API_CONFIGS = {
    "Kimi (Moonshot AI)": {
        "env": "KIMI_API_KEY",
        "required": True,
        "placeholder": "sk-abcdefghijklmnopqrstuvwxyz"
    },
    "Zhipu GLM-4": {
        "env": "ZHIPU_API_KEY",
        "required": True,
        "placeholder": "your_zhipu_api_key_here"
    },
    "MiniMax": {
        "env": "MINIMAX_API_KEY",
        "required": True,
        "placeholder": "MNX-"
    },
    "MiniMax Group ID": {
        "env": "MINIMAX_GROUP_ID",
        "required": True,
        "placeholder": "1234567890"
    },
    "Tavily": {
        "env": "TAVILY_API_KEY",
        "required": True,
        "placeholder": "tvly-"
    },
    "Tushare": {
        "env": "TUSHARE_TOKEN",
        "required": True,
        "placeholder": "37d77"
    },
}


def check_api_status() -> List[Dict]:
    """Check all API configuration status"""
    # Load environment variables
    env_path = project_root / ".env"
    if not env_path.exists():
        print("[!] .env file not found, using .env.example")
        env_path = project_root / ".env.example"

    load_dotenv(env_path)

    results = []

    for name, config in API_CONFIGS.items():
        env_key = config["env"]
        placeholder = config["placeholder"]
        value = os.getenv(env_key, "")

        # Check status
        if not value:
            status = "missing"
            status_text = "[X] Not configured"
        elif value == placeholder or len(value) < 10:
            status = "placeholder"
            status_text = "[!] Placeholder"
        else:
            status = "configured"
            status_text = "[OK] Configured"

        results.append({
            "name": name,
            "env_key": env_key,
            "status": status,
            "status_text": status_text,
            "value_preview": value[:8] + "..." if len(value) > 8 else value if value else "",
            "required": config["required"]
        })

    return results


def print_report(results: List[Dict]) -> None:
    """Print configuration report"""
    print("\n" + "=" * 60)
    print("API Configuration Status Report")
    print("=" * 60 + "\n")

    # Statistics
    total = len(results)
    required = [r for r in results if r["required"]]
    configured = [r for r in results if r["status"] == "configured"]
    missing = [r for r in results if r["status"] == "missing"]
    placeholder = [r for r in results if r["status"] == "placeholder"]

    print(f"Total: {total} APIs")
    print(f"Required: {len(required)}")
    print(f"Configured: {len(configured)}")
    print(f"Missing: {len(missing)}")
    print(f"Placeholder: {len(placeholder)}\n")

    # Detailed list
    print("-" * 60)
    print("Detailed Status\n")

    for i, result in enumerate(results, 1):
        required_mark = "(REQUIRED)" if result["required"] else "(OPTIONAL)"

        print(f"{i}. {result['name']} {required_mark}")
        print(f"   Status: {result['status_text']}")
        print(f"   Env var: {result['env_key']}")
        if result["value_preview"]:
            print(f"   Value: {result['value_preview']}")
        print()

    # Missing APIs
    need_config = missing + placeholder
    if need_config:
        print("-" * 60)
        print("APIs that need configuration:\n")

        for result in need_config:
            print(f"  * {result['name']}")
            print(f"    Environment variable: {result['env_key']}")
            print()

    # Next steps
    print("-" * 60)
    print("Next steps:\n")

    if need_config:
        print("  1. Read API_CONFIG_GUIDE.md to get API keys")
        print("  2. Edit .env file and fill in your API keys")
        print("  3. Run this script again to verify")
    else:
        print("  [OK] All APIs configured!")
        print("  Test the system with:")
        print("    python scripts/simulate_hot_news.py")


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("AI TradeBot - API Configuration Check")
    print("=" * 60)

    # Check configuration status
    results = check_api_status()

    # Print report
    print_report(results)

    # Final recommendation
    print("\n" + "=" * 60)

    required_configured = sum(1 for r in results if r["required"] and r["status"] == "configured")
    required_total = sum(1 for r in results if r["required"])

    if required_configured == required_total:
        print("[OK] All required APIs configured!")
        print("The system is ready to run.")
    else:
        missing_count = required_total - required_configured
        print(f"[!] {missing_count} required API(s) not configured")
        print("Please refer to API_CONFIG_GUIDE.md to get API keys")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
