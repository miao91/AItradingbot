"""
AI TradeBot - 股票代码提取工具

从文本中提取A股股票代码
"""
import re
from typing import List


# =============================================================================
# A股股票代码模式
# =============================================================================

# 6位数字（沪市: 600xxx, 601xxx, 603xxx, 688xxx 科创板）
# 6位数字（深市: 000xxx, 001xxx, 002xxx, 003xxx, 300xxx 创业板）
PATTERNS = [
    # 直接匹配6位数字
    r'\b(600\d{3}|601\d{3}|603\d{3}|688\d{3}|000\d{3}|001\d{3}|002\d{3}|003\d{3}|300\d{3})\b',
    # 匹配带后缀的格式 (如: 600519.SH)
    r'\b(\d{6})\.(SH|SZ|sh|sz)\b',
    # 匹配括号中的代码 (如: 贵州茅台(600519))
    r'\((\d{6})\)',
    # 匹配冒号后的代码 (如: 贵州茅台:600519)
    r':(\d{6})\b',
]


# =============================================================================
# 常见股票名称关键词（辅助验证）
# =============================================================================

STOCK_KEYWORDS = [
    "股份", "有限公司", "集团", "科技", "实业", "发展", "控股",
    "银行", "保险", "证券", "信托", "租赁", "投资"
]


# =============================================================================
# 提取函数
# =============================================================================

def extract_tickers(text: str, normalize: bool = True) -> List[str]:
    """
    从文本中提取股票代码

    Args:
        text: 输入文本
        normalize: 是否标准化格式（添加 .SH/.SZ 后缀）

    Returns:
        股票代码列表（去重后）

    Examples:
        >>> extract_tickers("贵州茅台(600519)发布公告")
        ['600519.SH']

        >>> extract_tickers("600519和000001双双上涨", normalize=False)
        ['600519', '000001']
    """
    if not text:
        return []

    codes = set()

    # 尝试所有模式
    for pattern in PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            # match 可能是元组（有捕获组）或字符串
            if isinstance(match, tuple):
                code = match[0]  # 取第一个捕获组（数字部分）
            else:
                code = match

            if code and len(code) == 6 and code.isdigit():
                codes.add(code)

    # 去重并排序
    result = sorted(list(codes))

    # 标准化格式
    if normalize:
        result = [normalize_ticker(code) for code in result]

    return result


def normalize_ticker(code: str) -> str:
    """
    标准化股票代码格式

    Args:
        code: 6位数字代码

    Returns:
        带 .SH 或 .SZ 后缀的代码

    Examples:
        >>> normalize_ticker("600519")
        '600519.SH'

        >>> normalize_ticker("000001")
        '000001.SZ'
    """
    if not code or len(code) != 6:
        return code

    first_three = code[:3]

    # 上海证券交易所
    if first_three in ['600', '601', '603', '688', '689']:
        return f"{code}.SH"

    # 深圳证券交易所
    elif first_three in ['000', '001', '002', '003', '300', '301']:
        return f"{code}.SZ"

    # 北京证券交易所
    elif first_three in ['430', '831', '832', '833', '834', '835', '836', '837', '838', '839', '870', '871', '872', '873', '898']:
        return f"{code}.BJ"

    # 未知，默认 SH
    else:
        return f"{code}.SH"


def extract_ticker_with_context(text: str, max_context_length: int = 50) -> List[dict]:
    """
    提取股票代码及其上下文

    Args:
        text: 输入文本
        max_context_length: 上下文最大长度

    Returns:
        [{"code": "600519.SH", "context": "...", "position": 123}, ...]
    """
    results = []

    # 匹配所有6位数字
    pattern = r'\b(600\d{3}|601\d{3}|603\d{3}|688\d{3}|000\d{3}|001\d{3}|002\d{3}|003\d{3}|300\d{3})\b'

    for match in re.finditer(pattern, text):
        code = match.group()
        start, end = match.span()

        # 提取上下文
        context_start = max(0, start - max_context_length)
        context_end = min(len(text), end + max_context_length)
        context = text[context_start:context_end].strip()

        results.append({
            "code": normalize_ticker(code),
            "context": context,
            "position": start
        })

    return results


def is_valid_ticker(ticker: str) -> bool:
    """
    验证股票代码格式是否有效

    Args:
        ticker: 股票代码（可带或不带后缀）

    Returns:
        是否有效
    """
    # 移除后缀
    code = ticker.split('.')[0] if '.' in ticker else ticker

    if not code or len(code) != 6 or not code.isdigit():
        return False

    first_three = code[:3]

    # 检查是否为有效的交易所代码
    valid_prefixes = [
        '600', '601', '603', '605', '688', '689',  # 上交所
        '000', '001', '002', '003', '300', '301',  # 深交所
        '430', '831', '832', '833', '834', '835', '836', '837', '838', '839', '870', '871', '872', '873', '898',  # 北交所
    ]

    return first_three in valid_prefixes


# =============================================================================
# 批量处理
# =============================================================================

def batch_extract_tickers(texts: List[str]) -> List[List[str]]:
    """批量提取股票代码"""
    return [extract_tickers(text) for text in texts]


# =============================================================================
# 测试/演示
# =============================================================================

if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "贵州茅台(600519)发布2024年半年报，净利润增长20%",
        "600519和000001今日双双上涨，300750涨停",
        "招商银行(600036.SH)获增持，中国平安(601318)拟回购",
        "无代码的文本",
        "代码123456不是有效代码",
    ]

    for text in test_cases:
        codes = extract_tickers(text)
        print(f"文本: {text[:50]}")
        print(f"提取: {codes}")
        print()
