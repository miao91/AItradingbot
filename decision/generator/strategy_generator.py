"""
AI TradeBot - 策略生成器

功能：
- 接收 MarketContext
- 调用LLM生成策略代码
- 支持多种策略模板
- 策略代码可执行且安全

核心公式: S_{t+1} = AI_agent(News_t, Flow_t, Factor_t)
"""

import re
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

from shared.logging import get_logger
from shared.llm.clients import get_glm5_client, get_deepseek_client


logger = get_logger(__name__)


# =============================================================================
# 数据模型
# =============================================================================

class StrategyType(Enum):
    """策略类型"""
    TREND_FOLLOWING = "trend_following"       # 趋势跟踪
    MEAN_REVERSION = "mean_reversion"         # 均值回归
    BREAKOUT = "breakout"                     # 突破策略
    REVERSAL = "reversal"                     # 反转策略
    MOMENTUM = "momentum"                     # 动量策略
    HYBRID = "hybrid"                         # 混合策略


@dataclass
class GeneratedStrategy:
    """生成的策略对象"""
    strategy_id: str
    strategy_type: StrategyType
    code: str                                  # 策略代码
    logic_description: str                      # 策略逻辑说明
    parameters: Dict[str, Any] = field(default_factory=dict)  # 策略参数
    generated_at: str = ""                      # 生成时间
    market_context: Optional[Dict] = None        # 生成时的市场上下文
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_type": self.strategy_type.value,
            "code": self.code,
            "logic_description": self.logic_description,
            "parameters": self.parameters,
            "generated_at": self.generated_at,
        }


# =============================================================================
# Prompt模板
# =============================================================================

class StrategyPromptTemplate:
    """策略生成Prompt模板"""
    
    SYSTEM_PROMPT = """你是一个专业的量化交易策略工程师。你的任务是根据当前市场状态，
生成一个具体的、可执行的Python交易策略。

【重要约束】
1. 生成的策略必须是一个完整的Python函数，签名如下：
```python
def strategy(context) -> dict:
    '''
    输入: MarketContext 对象
    返回: {
        "action": "BUY" | "SELL" | "HOLD",
        "size": float,  # 0-1 仓位比例
        "stop_loss": float,  # 止损比例 (如0.02表示2%)
        "take_profit": float,  # 止盈比例
        "confidence": float,  # 0-1 信心指数
        "reason": "策略逻辑说明"
    }
```

2. 必须包含以下要素：
   - 入场条件判断（必须同时满足多个条件）
   - 仓位管理逻辑（根据信心度动态调整）
   - 止损/止盈设置（必须包含）
   - 清晰的投资逻辑说明

3. 策略类型可以是（选择最适合当前市场的）：
   - 趋势跟踪策略：适用于有明显趋势的行情
   - 均值回归策略：适用于震荡行情
   - 突破策略：适用于盘整后突破
   - 反转策略：适用于超卖/超买后的反转
   - 动量策略：适用于强者恒强的行情

4. 【关键】你必须基于实际的市场数据来判断，不要假设数据。"""

    @classmethod
    def build_prompt(cls, market_context_prompt: str, strategy_type: str = "auto") -> str:
        """构建完整Prompt"""
        return f"""{cls.SYSTEM_PROMPT}

【当前市场状态】
{market_context_prompt}

【任务】
请生成一个针对当前市场状态的交易策略。

{'如果你判断当前适合趋势跟踪，请生成趋势跟踪策略。' if strategy_type == 'trend' else ''}
{'如果你判断当前适合均值回归，请生成均值回归策略。' if strategy_type == 'mean_reversion' else ''}
{'如果你判断当前适合反转策略，请生成反转策略。' if strategy_type == 'reversal' else ''}
{'请根据市场状态自动判断最合适的策略类型。' if strategy_type == 'auto' else ''}

请直接输出策略代码，不要包含其他说明文字。代码必须完整可运行。"""
    
    @classmethod
    def extract_code(cls, response: str) -> str:
        """从LLM响应中提取代码"""
        # 尝试提取 ```python ... ``` 块
        code_blocks = re.findall(r'```python\s*(.*?)\s*```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0]
        
        # 尝试提取 ``` ... ``` 块
        code_blocks = re.findall(r'```\s*(.*?)\s*```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0]
        
        # 如果没有代码块，返回整个响应
        return response.strip()


# =============================================================================
# 策略生成器
# =============================================================================

class StrategyGenerator:
    """
    AI策略生成器
    
    将市场上下文转化为可执行的交易策略代码
    """
    
    def __init__(self, model: str = "glm-5"):
        """
        初始化策略生成器
        
        Args:
            model: 使用的LLM模型 (glm-5, deepseek, kimi)
        """
        self.model = model
        self.prompt_template = StrategyPromptTemplate()
        self._llm_client = None
        
        logger.info(f"[StrategyGenerator] 初始化完成: model={model}")
    
    async def generate(
        self,
        market_context_prompt: str,
        strategy_type: str = "auto",
        custom_instructions: Optional[str] = None
    ) -> GeneratedStrategy:
        """
        生成策略代码
        
        Args:
            market_context_prompt: 市场上下文Prompt
            strategy_type: 策略类型 (auto/trend/mean_reversion/reversal)
            custom_instructions: 自定义指令
            
        Returns:
            GeneratedStrategy: 生成的策略对象
        """
        import uuid
        from datetime import datetime
        
        logger.info(f"[StrategyGenerator] 开始生成策略")
        
        # 构建Prompt
        prompt = self.prompt_template.build_prompt(
            market_context_prompt,
            strategy_type
        )
        
        if custom_instructions:
            prompt += f"\n\n【额外要求】\n{custom_instructions}"
        
        # 调用LLM生成代码
        try:
            response = await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"[StrategyGenerator] LLM调用失败: {e}")
            # 返回默认策略
            return self._get_fallback_strategy()
        
        # 提取代码
        code = self.prompt_template.extract_code(response)
        
        # 解析策略类型
        detected_type = self._detect_strategy_type(response)
        
        # 生成策略对象
        strategy = GeneratedStrategy(
            strategy_id=f"strat_{uuid.uuid4().hex[:8]}",
            strategy_type=detected_type,
            code=code,
            logic_description=self._extract_logic_description(response),
            parameters=self._extract_parameters(code),
            generated_at=datetime.now().isoformat(),
        )
        
        logger.info(f"[StrategyGenerator] 策略生成完成: {strategy.strategy_id}, type={strategy.strategy_type.value}")
        
        return strategy
    
    async def _call_llm(self, prompt: str) -> str:
        """调用LLM获取响应"""
        
        # 根据模型选择LLM客户端
        if self.model == "glm-5":
            client = get_glm5_client()
        elif self.model == "deepseek":
            client = get_deepseek_client()
        else:
            # 默认使用GLM5
            client = get_glm5_client()
        
        # 调用LLM
        response = await client.chat(
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        return response
    
    def _detect_strategy_type(self, response: str) -> StrategyType:
        """从响应中检测策略类型"""
        response_lower = response.lower()
        
        if "趋势" in response or "trend" in response_lower:
            return StrategyType.TREND_FOLLOWING
        elif "均值回归" in response or "mean reversion" in response_lower:
            return StrategyType.MEAN_REVERSION
        elif "突破" in response or "breakout" in response_lower:
            return StrategyType.BREAKOUT
        elif "反转" in response or "reversal" in response_lower:
            return StrategyType.REVERSAL
        elif "动量" in response or "momentum" in response_lower:
            return StrategyType.MOMENTUM
        else:
            return StrategyType.HYBRID
    
    def _extract_logic_description(self, response: str) -> str:
        """提取策略逻辑描述"""
        # 尝试从代码注释中提取
        match = re.search(r'"""(.*?)"""', response, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # 尝试从代码中提取docstring
        lines = response.split('\n')
        description_lines = []
        in_docstring = False
        
        for line in lines:
            if '"""' in line or "'''" in line:
                if not in_docstring:
                    in_docstring = True
                    # 开始收集docstring内容
                    desc_part = line.split('"""')[1] if '"""' in line else line.split("'''")[1]
                    if desc_part.strip():
                        description_lines.append(desc_part.strip())
                else:
                    in_docstring = False
            elif in_docstring:
                description_lines.append(line.strip())
        
        if description_lines:
            return ' '.join(description_lines[:3])  # 取前3行
        
        return "AI生成的交易策略"
    
    def _extract_parameters(self, code: str) -> Dict[str, Any]:
        """从代码中提取参数"""
        params = {}
        
        # 提取常见参数模式
        patterns = {
            'stop_loss': r'stop_?loss\s*=\s*([0-9.]+)',
            'take_profit': r'take_?profit\s*=\s*([0-9.]+)',
            'position_size': r'position_?size\s*=\s*([0-9.]+)',
            'rsi_threshold': r'rsi[<>]=?\s*([0-9.]+)',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                try:
                    params[key] = float(match.group(1))
                except:
                    pass
        
        return params
    
    def _get_fallback_strategy(self) -> GeneratedStrategy:
        """获取备用策略"""
        from datetime import datetime
        import uuid
        
        fallback_code = '''def strategy(context) -> dict:
    """
    默认策略：根据市场状态进行简单决策
    """
    # 获取市场数据
    sentiment = context.get("sentiment", 0)
    flow = context.get("flow", 0)
    rsi = context.get("rsi", 50)
    
    # 简单决策逻辑
    if sentiment > 0.3 and flow > 0 and rsi < 70:
        return {
            "action": "BUY",
            "size": 0.1,
            "stop_loss": 0.02,
            "take_profit": 0.05,
            "confidence": 0.6,
            "reason": "市场情绪乐观，资金流入，符合买入条件"
        }
    elif sentiment < -0.3 or rsi > 80:
        return {
            "action": "SELL",
            "size": 0.1,
            "stop_loss": 0.02,
            "take_profit": 0.03,
            "confidence": 0.6,
            "reason": "市场情绪悲观或超买，考虑卖出"
        }
    
    return {
        "action": "HOLD",
        "size": 0,
        "stop_loss": 0,
        "take_profit": 0,
        "confidence": 0.5,
        "reason": "市场状态不明确，保持观望"
    }
'''
        
        return GeneratedStrategy(
            strategy_id=f"fallback_{uuid.uuid4().hex[:6]}",
            strategy_type=StrategyType.HYBRID,
            code=fallback_code,
            logic_description="默认混合策略",
            parameters={"type": "fallback"},
            generated_at=datetime.now().isoformat(),
        )


# =============================================================================
# 便捷函数
# =============================================================================

async def generate_strategy(
    market_context_prompt: str,
    model: str = "glm-5"
) -> GeneratedStrategy:
    """
    快速生成策略
    
    Usage:
        strategy = await generate_strategy(context_prompt)
        print(strategy.code)
    """
    generator = StrategyGenerator(model=model)
    return await generator.generate(market_context_prompt)


# =============================================================================
# 测试入口
# =============================================================================

if __name__ == "__main__":
    async def test():
        # 测试Prompt
        sample_context = """
- 新闻情绪: 0.3 (偏多)
- 热点主题: 科技、新能源
- 资金流向: 净流入1500万
- RSI(14): 65.5
- 趋势: 上涨趋势
"""
        
        generator = StrategyGenerator()
        strategy = await generator.generate(sample_context)
        
        print("=" * 60)
        print(f"策略ID: {strategy.strategy_id}")
        print(f"策略类型: {strategy.strategy_type.value}")
        print(f"逻辑描述: {strategy.logic_description}")
        print("=" * 60)
        print("策略代码:")
        print(strategy.code)
    
    # asyncio.run(test())
    print("StrategyGenerator 模块已加载")
