"""
AI TradeBot - 策略代码审查器

功能：
- 语法检查
- 安全检查（禁止危险函数）
- 必要元素检查（止损、仓位）
- 逻辑漏洞检测
"""

import ast
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from enum import Enum

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 数据模型
# =============================================================================

class IssueSeverity(Enum):
    """问题严重程度"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class CodeIssue:
    """代码问题"""
    severity: IssueSeverity
    message: str
    line: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ReviewResult:
    """审查结果"""
    passed: bool
    issues: List[CodeIssue] = field(default_factory=list)
    score: float = 0.0  # 0-100 质量评分
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [
                {
                    "severity": i.severity.value,
                    "message": i.message,
                    "line": i.line,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "score": self.score,
        }


# =============================================================================
# 审查器
# =============================================================================

class CodeReviewer:
    """
    策略代码审查器
    
    确保AI生成的策略代码安全、有效、可执行
    """
    
    # 危险函数/模块黑名单
    DANGEROUS_IMPORTS: Set[str] = {
        'os', 'sys', 'subprocess', 'socket', 'requests',
        'urllib', 'http', 'ftplib', 'telnetlib',
        'eval', 'exec', 'compile', 'open',
        'pickle', 'marshal', 'yaml',
        'shutil', 'pathlib', 'glob',
        'threading', 'multiprocessing', 'asyncio',
    }
    
    # 危险函数调用
    DANGEROUS_FUNCTIONS: Set[str] = {
        'os.system', 'os.popen', 'os.remove', 'os.rmdir',
        'subprocess.call', 'subprocess.run', 'subprocess.Popen',
        'eval', 'exec', 'compile',
        '__import__', 'open', 'file',
    }
    
    # 必要元素
    REQUIRED_ELEMENTS: Dict[str, str] = {
        'stop_loss': '止损设置',
        'position': '仓位管理',
        'size': '仓位大小',
        'action': '交易动作',
    }
    
    # 策略相关关键字
    STRATEGY_KEYWORDS: Set[str] = {
        'context', 'sentiment', 'flow', 'rsi', 'macd',
        'buy', 'sell', 'hold', 'signal',
        'entry', 'exit', 'position', 'stop',
    }
    
    def __init__(self):
        """初始化审查器"""
        self._issues: List[CodeIssue] = []
        
        logger.info("[CodeReviewer] 初始化完成")
    
    def review(self, code: str) -> ReviewResult:
        """
        审查策略代码
        
        Args:
            code: Python代码字符串
            
        Returns:
            ReviewResult: 审查结果
        """
        self._issues = []
        
        # 1. 语法检查
        syntax_issues = self._check_syntax(code)
        self._issues.extend(syntax_issues)
        
        # 2. 安全检查
        security_issues = self._check_security(code)
        self._issues.extend(security_issues)
        
        # 3. 必要元素检查
        required_issues = self._check_required_elements(code)
        self._issues.extend(required_issues)
        
        # 4. 策略逻辑检查
        logic_issues = self._check_strategy_logic(code)
        self._issues.extend(logic_issues)
        
        # 5. 计算评分
        score = self._calculate_score(code)
        
        # 判断是否通过
        has_errors = any(i.severity == IssueSeverity.ERROR for i in self._issues)
        passed = not has_errors and score >= 50
        
        return ReviewResult(
            passed=passed,
            issues=self._issues,
            score=score,
        )
    
    def _check_syntax(self, code: str) -> List[CodeIssue]:
        """检查语法"""
        issues = []
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(CodeIssue(
                severity=IssueSeverity.ERROR,
                message=f"语法错误: {e.msg}",
                line=e.lineno,
                suggestion="请检查代码语法是否正确"
            ))
        except Exception as e:
            issues.append(CodeIssue(
                severity=IssueSeverity.ERROR,
                message=f"解析错误: {str(e)}",
                suggestion="请检查代码格式"
            ))
        
        return issues
    
    def _check_security(self, code: str) -> List[CodeIssue]:
        """检查安全性"""
        issues = []
        
        # 检查危险导入
        import_pattern = r'(?:^|\n)\s*(?:import\s+(\w+)|from\s+(\w+)\s+import)'
        for match in re.finditer(import_pattern, code):
            module = match.group(1) or match.group(2)
            if module in self.DANGEROUS_IMPORTS:
                issues.append(CodeIssue(
                    severity=IssueSeverity.ERROR,
                    message=f"禁止导入危险模块: {module}",
                    line=code[:match.start()].count('\n') + 1,
                    suggestion=f"请移除 'import {module}' 或 'from {module} import ...'"
                ))
        
        # 检查危险函数调用
        for dangerous_func in self.DANGEROUS_FUNCTIONS:
            if dangerous_func in code:
                issues.append(CodeIssue(
                    severity=IssueSeverity.ERROR,
                    message=f"禁止使用危险函数: {dangerous_func}",
                    suggestion="请移除此函数调用"
                ))
        
        # 检查 __import__
        if '__import__' in code:
            issues.append(CodeIssue(
                severity=IssueSeverity.ERROR,
                message="禁止使用 __import__",
                suggestion="请使用静态导入"
            ))
        
        return issues
    
    def _check_required_elements(self, code: str) -> List[CodeIssue]:
        """检查必要元素"""
        issues = []
        code_lower = code.lower()
        
        for element, description in self.REQUIRED_ELEMENTS.items():
            if element not in code_lower:
                issues.append(CodeIssue(
                    severity=IssueSeverity.WARNING,
                    message=f"缺少必要元素: {description}",
                    suggestion=f"请添加 {element} 相关逻辑"
                ))
        
        # 检查是否有返回值
        if 'return' not in code_lower:
            issues.append(CodeIssue(
                severity=IssueSeverity.ERROR,
                message="策略必须返回交易信号",
                suggestion="请添加 return 语句返回交易决策"
            ))
        
        # 检查是否定义了strategy函数
        if 'def strategy' not in code:
            issues.append(CodeIssue(
                severity=IssueSeverity.ERROR,
                message="必须定义 strategy 函数",
                suggestion="请定义 def strategy(context) 函数"
            ))
        
        return issues
    
    def _check_strategy_logic(self, code: str) -> List[CodeIssue]:
        """检查策略逻辑"""
        issues = []
        code_lower = code.lower()
        
        # 检查是否有条件判断
        if 'if' not in code_lower:
            issues.append(CodeIssue(
                severity=IssueSeverity.WARNING,
                message="策略缺少条件判断逻辑",
                suggestion="建议添加入场/出场条件判断"
            ))
        
        # 检查是否有仓位控制
        if 'size' not in code_lower and 'position' not in code_lower:
            issues.append(CodeIssue(
                severity=IssueSeverity.WARNING,
                message="策略缺少仓位控制",
                suggestion="建议添加仓位管理逻辑"
            ))
        
        # 检查是否有置信度
        if 'confidence' not in code_lower:
            issues.append(CodeIssue(
                severity=IssueSeverity.INFO,
                message="建议添加置信度指标",
                suggestion="可以添加 confidence 字段表示策略信心"
            ))
        
        # 检查返回值格式
        if 'action' not in code_lower:
            issues.append(CodeIssue(
                severity=IssueSeverity.ERROR,
                message="返回值必须包含 action 字段",
                suggestion="请在返回字典中包含 'action' 字段"
            ))
        
        # 检查action是否只有 BUY/SELL/HOLD
        valid_actions = ['buy', 'sell', 'hold']
        action_pattern = r'["\']action["\']\s*:\s*["\'](\w+)["\']'
        for match in re.finditer(action_pattern, code, re.IGNORECASE):
            action = match.group(1).lower()
            if action not in valid_actions:
                issues.append(CodeIssue(
                    severity=IssueSeverity.WARNING,
                    message=f"action 值 '{action}' 不是标准值",
                    suggestion="建议使用 BUY/SELL/HOLD 之一"
                ))
        
        return issues
    
    def _calculate_score(self, code: str) -> float:
        """计算代码质量评分"""
        score = 100.0
        
        # 语法错误扣分
        syntax_errors = sum(1 for i in self._issues 
                          if i.severity == IssueSeverity.ERROR and '语法' in i.message)
        score -= syntax_errors * 30
        
        # 安全问题扣分
        security_issues = sum(1 for i in self._issues 
                            if i.severity == IssueSeverity.ERROR and '危险' in i.message)
        score -= security_issues * 25
        
        # 缺少必要元素扣分
        required_issues = sum(1 for i in self._issues 
                            if i.severity == IssueSeverity.ERROR and '必须' in i.message)
        score -= required_issues * 20
        
        # 警告扣分
        warnings = sum(1 for i in self._issues 
                      if i.severity == IssueSeverity.WARNING)
        score -= warnings * 5
        
        # 信息扣分
        infos = sum(1 for i in self._issues 
                   if i.severity == IssueSeverity.INFO)
        score -= infos * 2
        
        # 奖励分：包含良好实践
        bonus = 0
        
        # 有详细注释
        if '"""' in code or "'''" in code:
            bonus += 5
        
        # 有风险管理
        if 'stop_loss' in code.lower() and 'take_profit' in code.lower():
            bonus += 10
        
        # 有置信度
        if 'confidence' in code.lower():
            bonus += 5
        
        # 有多条件判断
        if code.lower().count('if') >= 2:
            bonus += 5
        
        score += bonus
        
        return max(0, min(100, score))
    
    def validate_return_format(self, code: str) -> bool:
        """验证返回值格式"""
        # 检查返回是否是字典
        return_pattern = r'return\s*\{'
        return bool(re.search(return_pattern, code))


# =============================================================================
# 便捷函数
# =============================================================================

def review_strategy(code: str) -> ReviewResult:
    """
    快速审查策略代码
    
    Usage:
        result = review_strategy(strategy_code)
        if result.passed:
            print("策略审查通过")
    """
    reviewer = CodeReviewer()
    return reviewer.review(code)


# =============================================================================
# 测试入口
# =============================================================================

if __name__ == "__main__":
    # 测试代码
    test_code = '''
def strategy(context) -> dict:
    """
    测试策略
    """
    # 获取市场数据
    sentiment = context.get("sentiment", 0)
    rsi = context.get("rsi", 50)
    
    # 入场条件
    if sentiment > 0.3 and rsi < 70:
        return {
            "action": "BUY",
            "size": 0.1,
            "stop_loss": 0.02,
            "take_profit": 0.05,
            "confidence": 0.8,
            "reason": "市场情绪乐观且未超买"
        }
    
    return {
        "action": "HOLD",
        "size": 0,
        "confidence": 0.5,
        "reason": "不符合入场条件"
    }
'''
    
    reviewer = CodeReviewer()
    result = reviewer.review(test_code)
    
    print("=" * 60)
    print(f"审查结果: {'通过' if result.passed else '未通过'}")
    print(f"评分: {result.score}/100")
    print("=" * 60)
    
    for issue in result.issues:
        print(f"[{issue.severity.value}] {issue.message}")
        if issue.line:
            print(f"  行号: {issue.line}")
        if issue.suggestion:
            print(f"  建议: {issue.suggestion}")
