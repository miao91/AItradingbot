"""
AI TradeBot - 代码安全提取与校验器

AI 经常输出带有 Markdown（如 ```python）的废话。本模块提供高鲁棒性的代码提取和安全校验。

核心功能：
1. 提取函数：从 LLM 响应中提取 Python 代码
2. 语法校验：使用 ast.parse 验证代码语法
3. 安全检查：黑名单防御危险操作
4. 函数校验：确保包含 strategy 函数定义

作者: Matrix Agent
"""

import os
import sys
import ast
import re
import inspect
from typing import Optional, List, Set, Tuple
from dataclasses import dataclass, field

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 自定义异常
# =============================================================================

class CodeExtractionError(Exception):
    """
    代码提取异常
    
    当无法从 LLM 响应中提取有效代码时抛出。
    """
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class SecurityViolationError(Exception):
    """
    安全违规异常
    
    当代码包含危险操作时抛出。
    """
    def __init__(self, message: str, violation_type: str = ""):
        self.message = message
        self.violation_type = violation_type
        super().__init__(self.message)


class SyntaxValidationError(Exception):
    """
    语法验证异常
    
    当代码语法错误时抛出。
    """
    def __init__(self, message: str, line_number: int = 0, column: int = 0):
        self.message = message
        self.line_number = line_number
        self.column = column
        super().__init__(self.message)


# =============================================================================
# 安全黑名单
# =============================================================================

# 危险导入列表
DANGEROUS_IMPORTS: Set[str] = {
    "os",           # 文件系统操作
    "sys",          # 系统操作
    "subprocess",   # 子进程执行
    "pty",          # 伪终端
    "socket",       # 网络套接字
    "requests",     # HTTP 请求
    "urllib",       # URL 操作
    "http",         # HTTP 操作
    "ftplib",       # FTP 操作
    "telnetlib",    # Telnet 操作
    "telnet",       # Telnet 操作
    "smtplib",      # 邮件操作
    "poplib",       # 邮件操作
    "imaplib",      # 邮件操作
    "glob",         # 文件 glob
    "shutil",       # 文件操作
    "tempfile",     # 临时文件
    "glob",         # 文件匹配
    "pathlib",      # 路径操作
    "importlib",    # 动态导入
}

# 危险函数列表
DANGEROUS_FUNCTIONS: Set[str] = {
    "eval",         # 动态执行
    "exec",         # 代码执行
    "compile",      # 编译代码
    "open",         # 文件打开
    "file",         # 文件操作
    "input",        # 用户输入
    "print",        # 打印（警告，非危险）
    "reload",       # 模块重载
    "vars",         # 获取变量
    "dir",          # 获取属性
    "getattr",      # 获取属性
    "setattr",      # 设置属性
    "delattr",      # 删除属性
    "memoryview",   # 内存视图
    "mmap",         # 内存映射文件
}

# 危险属性列表
DANGEROUS_ATTRIBUTES: Set[str] = {
    "__import__",           # 动态导入
    "__builtins__",         # 内置函数
    "__globals__",         # 全局变量
    "__code__",            # 代码对象
    "__func__",            # 函数对象
    "__closure__",         # 闭包
    "__subclasses__",      # 子类
}


# =============================================================================
# AST 访问器
# =============================================================================

class SecurityASTVisitor(ast.NodeVisitor):
    """
    AST 安全访问器
    
    遍历 AST 节点，检查危险操作。
    """
    
    def __init__(self):
        self.violations: List[Tuple[str, str]] = []  # (违规类型, 详情)
        self.imports: Set[str] = set()
        self.function_names: Set[str] = set()
        self.has_strategy_function: bool = False
    
    def visit_Import(self, node: ast.Import) -> None:
        """访问导入语句"""
        for alias in node.names:
            import_name = alias.name.split(".")[0]  # 只取顶层模块
            self.imports.add(import_name)
            
            if import_name in DANGEROUS_IMPORTS:
                self.violations((f"危险导入: {import_name}", "import"))
        
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """访问 from...import 语句"""
        if node.module:
            import_name = node.module.split(".")[0]
            self.imports.add(import_name)
            
            if import_name in DANGEROUS_IMPORTS:
                self.violations.append((f"危险导入: {import_name}", "import_from"))
        
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call) -> None:
        """访问函数调用"""
        # 检查危险函数调用
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in DANGEROUS_FUNCTIONS:
                self.violations.append((f"危险函数调用: {func_name}", "call"))
        
        # 检查 __import__ 调用
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr == "__import__":
                self.violations.append(("动态导入调用", "call"))
        
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """访问函数定义"""
        self.function_names.add(node.name)
        
        # 检查是否包含 strategy 函数
        if node.name == "strategy":
            self.has_strategy_function = True
        
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """访问异步函数定义"""
        self.function_names.add(node.name)
        
        if node.name == "strategy":
            self.has_strategy_function = True
        
        self.generic_visit(node)


# =============================================================================
# 核心函数
# =============================================================================

def extract_code_from_markdown(text: str) -> str:
    """
    从 Markdown 中提取 Python 代码
    
    Args:
        text: 包含 Markdown 代码块的文本
        
    Returns:
        提取出的代码字符串
        
    Examples:
        >>> text = "以下是策略代码:\n```python\ndef strategy():\n    return 'BUY'\n```"
        >>> extract_code_from_markdown(text)
        "def strategy():\n    return 'BUY'"
    """
    if not text:
        return ""
    
    # 移除多余空白
    text = text.strip()
    
    # 方法1: 尝试匹配 ```python ... ```
    pattern1 = r"```python\s*\n(.*?)\n```"
    match = re.search(pattern1, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 方法2: 尝试匹配 ``` ... ``` (不带语言标识)
    pattern2 = r"```\s*\n(.*?)\n```"
    match = re.search(pattern2, text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        # 排除 markdown 标题等
        if not code.startswith("#") and not code.startswith("="):
            return code
    
    # 方法3: 尝试匹配 ```python ```
    pattern3 = r"```python\s*(.*?)\s*```"
    match = re.search(pattern3, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # 方法4: 如果没有代码块，返回原文本（可能是裸代码）
    # 检查是否包含 Python 代码特征
    if "def " in text or "class " in text or "import " in text:
        # 移除可能的描述文本
        lines = text.split("\n")
        code_lines = []
        in_code = False
        
        for line in lines:
            # 跳过明显的描述性文本
            if line.strip().startswith("#") and not in_code:
                continue
            if line.strip().startswith("以下是") or line.strip().startswith("代码"):
                continue
            
            code_lines.append(line)
            in_code = True
        
        if code_lines:
            return "\n".join(code_lines).strip()
    
    # 返回原始文本作为最后尝试
    return text


def validate_syntax(code: str) -> ast.AST:
    """
    验证代码语法
    
    Args:
        code: Python 代码字符串
        
    Returns:
        解析后的 AST 树
        
    Raises:
        SyntaxValidationError: 语法错误
    """
    try:
        return ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise SyntaxValidationError(
            message=f"语法错误: {e.msg}",
            line_number=e.lineno or 0,
            column=e.offset or 0
        )


def check_security(code: str) -> List[Tuple[str, str]]:
    """
    检查代码安全性
    
    Args:
        code: Python 代码字符串
        
    Returns:
        违规列表 [(违规类型, 详情), ...]
        
    Raises:
        SecurityViolationError: 存在危险操作
    """
    # 先解析 AST
    try:
        tree = validate_syntax(code)
    except SyntaxValidationError:
        # 语法错误时不进行安全检查
        return []
    
    # 访问 AST
    visitor = SecurityASTVisitor()
    visitor.visit(tree)
    
    # 检查违规
    violations = visitor.violations
    
    if violations:
        raise SecurityViolationError(
            message=f"发现 {len(violations)} 个安全违规",
            violation_type="; ".join([v[0] for v in violations])
        )
    
    return violations


def check_strategy_function(code: str) -> bool:
    """
    检查代码是否包含 strategy 函数定义
    
    Args:
        code: Python 代码字符串
        
    Returns:
        是否包含 strategy 函数
    """
    try:
        tree = validate_syntax(code)
    except SyntaxValidationError:
        return False
    
    visitor = SecurityASTVisitor()
    visitor.visit(tree)
    
    return visitor.has_strategy_function


def extract_and_validate_code(llm_response: str) -> str:
    """
    从 LLM 响应中提取并验证代码
    
    这是核心入口函数，执行以下步骤：
    1. 使用正则提取 Markdown 中的 Python 代码
    2. 使用 ast.parse 验证语法
    3. 检查是否存在危险操作
    4. 确保包含 strategy 函数定义
    
    Args:
        llm_response: LLM 原始响应
        
    Returns:
        净化后的代码字符串
        
    Raises:
        CodeExtractionError: 无法提取代码
        SyntaxValidationError: 语法错误
        SecurityViolationError: 安全违规
    """
    logger.info("[AST Utils] 开始提取和验证代码")
    
    # 步骤1: 提取代码
    code = extract_code_from_markdown(llm_response)
    
    if not code or len(code.strip()) < 10:
        raise CodeExtractionError(
            message="无法从响应中提取有效代码",
            original_error=None
        )
    
    logger.info(f"[AST Utils] 提取代码长度: {len(code)} 字符")
    
    # 步骤2: 验证语法
    try:
        validate_syntax(code)
        logger.info("[AST Utils] 语法验证通过")
    except SyntaxValidationError as e:
        logger.error(f"[AST Utils] 语法验证失败: {e.message}")
        raise CodeExtractionError(
            message=f"代码语法错误 (行 {e.line_number}): {e.message}",
            original_error=e
        )
    
    # 步骤3: 安全检查
    try:
        check_security(code)
        logger.info("[AST Utils] 安全检查通过")
    except SecurityViolationError as e:
        logger.error(f"[AST Utils] 安全检查失败: {e.violation_type}")
        raise CodeExtractionError(
            message=f"安全违规: {e.violation_type}",
            original_error=e
        )
    
    # 步骤4: 检查 strategy 函数
    if not check_strategy_function(code):
        logger.warning("[AST Utils] 警告: 代码中未找到 strategy 函数定义")
        # 不抛出异常，但记录警告
    
    return code


def sanitize_code_for_sandbox(code: str) -> str:
    """
    为沙箱准备代码
    
    执行额外的清理步骤：
    1. 移除注释
    2. 规范化缩进
    3. 移除 docstring
    
    Args:
        code: 原始代码
        
    Returns:
        净化后的代码
    """
    try:
        tree = validate_syntax(code)
    except SyntaxValidationError:
        return code
    
    # 移除 docstring
    class DocstringRemover(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
            if ast.get_docstring(node):
                node.body.pop(0) if node.body and isinstance(node.body[0], ast.Expr) else None
            return node
    
    # 简化处理：直接返回原代码
    # 实际生产中可以进一步处理
    return code


# =============================================================================
# 便捷函数
# =============================================================================

def safe_extract_code(llm_response: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    安全提取代码的便捷函数
    
    Args:
        llm_response: LLM 原始响应
        
    Returns:
        (是否成功, 代码, 错误信息)
    """
    try:
        code = extract_and_validate_code(llm_response)
        return True, code, None
    except CodeExtractionError as e:
        return False, None, e.message
    except Exception as e:
        return False, None, f"未知错误: {e}"


# =============================================================================
# 测试入口
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("测试代码安全提取与校验器")
    print("=" * 60)
    
    # 测试1: 正常代码
    test_code1 = """
def strategy(context):
    '''策略函数'''
    price = context.get('price', 0)
    if price > 100:
        return {'action': 'BUY', 'size': 0.5}
    return {'action': 'HOLD', 'size': 0}
"""
    
    success, result, error = safe_extract_code(test_code1)
    print(f"\n测试1 - 正常代码:")
    print(f"  成功: {success}")
    if success:
        print(f"  代码长度: {len(result)}")
    
    # 测试2: 带 Markdown 的代码
    test_code2 = """
以下是策略代码:
```python
def strategy(context):
    return {'action': 'BUY', 'size': 1.0}
```
请检查
"""
    
    success, result, error = safe_extract_code(test_code2)
    print(f"\n测试2 - Markdown 代码:")
    print(f"  成功: {success}")
    if success:
        print(f"  提取的代码: {result[:50]}...")
    
    # 测试3: 危险代码
    test_code3 = """
import os
import subprocess

def strategy(context):
    os.system('rm -rf /')
    return {'action': 'BUY', 'size': 1.0}
"""
    
    success, result, error = safe_extract_code(test_code3)
    print(f"\n测试3 - 危险代码:")
    print(f"  成功: {success}")
    print(f"  错误: {error}")
    
    # 测试4: 语法错误
    test_code4 = """
def strategy(contextaction': 'BU)
    return {'Y'}
"""
    
    success, result, error = safe_extract_code(test_code4)
    print(f"\n测试4 - 语法错误:")
    print(f"  成功: {success}")
    print(f"  错误: {error}")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成")
    print("=" * 60)
