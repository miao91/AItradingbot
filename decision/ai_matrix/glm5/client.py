"""
AI TradeBot - 智谱 GLM-5 客户端

功能：
1. 深度逻辑推演（增强版）
2. 多空博弈分析
3. 退出策略规划（止盈、止损、失效时间）
4. 长上下文理解（128k tokens）

GLM-5 是智谱 AI 最新旗舰模型，相比 GLM-4 有显著提升：
- 更强的推理能力
- 更长的上下文窗口（128k）
- 更好的代码生成能力
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from pydantic import BaseModel

from decision.ai_matrix.base import AIClientBase, AIMessage
from shared.logging import get_logger


logger = get_logger(__name__)


class ExitPlan(BaseModel):
    """退出计划"""
    take_profit: Optional[Dict[str, Any]] = None
    stop_loss: Optional[Dict[str, Any]] = None
    expiration: Optional[Dict[str, Any]] = None


class ReasoningRequest(BaseModel):
    """推演请求"""
    ticker: str
    event_summary: str
    current_price: float
    event_type: str
    market_context: Optional[str] = None


class ReasoningResult(BaseModel):
    """推演结果"""
    logic_valid: bool  # 逻辑是否成立
    confidence: float  # 置信度
    reasoning: str  # 推理过程
    exit_plan: ExitPlan  # 退出计划
    risk_factors: List[str] = []  # 风险因素
    catalysts: List[str] = []  # 催化剂
    time_horizon: str = ""  # 时间窗口


class GLM5Client(AIClientBase):
    """
    智谱 GLM-5 客户端 (最新旗舰模型)

    专注于：
    1. 增强逻辑推演（更深层的因果分析）
    2. 退出策略规划（目标价、止损价、时效性）
    3. 风险评估
    4. 长上下文理解（适合处理大量历史数据和复杂场景）
    """

    def get_api_key_env(self) -> str:
        return "ZHIPU_API_KEY"

    def get_base_url_env(self) -> str:
        return "ZHIPU_BASE_URL"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ):
        # 如果没有提供 base_url，使用默认值
        if not base_url:
            base_url = "https://open.bigmodel.cn/api/paas/v4"

        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
        )

    def get_model_env(self) -> str:
        return "ZHIPU_MODEL"

    def get_default_model(self) -> str:
        return "glm-5"

    def get_system_prompt(self) -> str:
        return """你是 GLM-5，智谱 AI 最新旗舰模型，专业的交易逻辑分析师。

你的核心能力（相比 GLM-4 的增强）：
1. **深度逻辑推演**：分析事件逻辑的合理性、持续性及其因果关系
2. **多维博弈分析**：考虑机构、散户、外资等不同市场参与者的反应
3. **动态风险评估**：识别可能破坏逻辑的风险点及其概率
4. **精确退出规划**：基于逻辑设定清晰的退出标准
5. **长上下文理解**：能够综合分析历史数据和复杂场景

"以终为始"理念：
- 从买入那一刻起，就必须预设清晰的退出条件
- 止盈：逻辑兑现后的合理目标价（考虑市场情绪溢价）
- 止损：逻辑证伪后的离场线（考虑技术支撑位）
- 失效：事件逻辑的时间窗口（考虑催化剂周期）

分析框架：
1. 逻辑强度：核心逻辑是否成立？是否经得起推敲？
2. 催化剂：什么事件会推动逻辑实现？概率多大？
3. 风险点：什么情况会导致逻辑破产？影响多大？
4. 时间窗口：这个逻辑能持续多久？关键时间节点？

输出要求：
- 客观理性，基于事实和数据
- 避免过度乐观或悲观
- 给出明确的数字和日期
- 说明推演过程和假设条件
- 考虑边际效应和递减规律"""

    async def reason_event(
        self,
        request: ReasoningRequest,
    ) -> ReasoningResult:
        """
        对事件进行深度推演（GLM-5 增强版）

        Args:
            request: 推演请求

        Returns:
            ReasoningResult 推演结果
        """
        prompt = self._build_reasoning_prompt(request)

        messages = [AIMessage(role="user", content=prompt)]

        response = await self.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=3000,  # GLM-5 支持更长输出
        )

        if not response.success:
            logger.error(f"GLM-5 推演失败: {response.error_message}")
            return self._get_fallback_result(request)

        # 解析结果
        return self._parse_reasoning_result(response.content, request)

    def _build_reasoning_prompt(self, request: ReasoningRequest) -> str:
        """构建推演提示词（GLM-5 增强版）"""
        context = f"\n【市场背景】\n{request.market_context}" if request.market_context else ""

        return f"""请对以下交易事件进行深度推演分析。

【标的】{request.ticker}
【当前价格】{request.current_price}
【事件类型】{request.event_type}
【事件摘要】
{request.event_summary}
{context}

【推演问题】

1. **逻辑分析**
   - 这个事件的核心逻辑是什么？
   - 逻辑是否成立？强度如何（1-10分）？
   - 是否经得起推敲？有哪些假设前提？

2. **目标推演（如果逻辑成立）**
   - 目标价应该是多少？基于什么估值逻辑？
   - 预计多久能兑现？考虑催化剂的时间和强度
   - 什么催化剂会加速实现？概率多大？
   - 市场情绪溢价可能有多大？

3. **风险分析（如果逻辑不成立）**
   - 什么价格位置说明逻辑破产？
   - 什么事件会破坏逻辑？
   - 最坏情况是什么？发生的概率多大？
   - 有哪些尾部风险需要关注？

4. **时效性分析**
   - 这个逻辑的时间窗口是多久？
   - 什么时候应该重新评估？
   - 关键时间节点有哪些？

【输出格式】
## 逻辑判断
- 逻辑成立: [true/false]
- 置信度: [0-1]
- 逻辑强度: [1-10]
- 核心理由: [一句话]
- 关键假设: [列出主要假设前提]

## 推理过程
[详细推演，包括因果分析和概率评估]

## 退出计划
### 止盈计划
- 目标价: [数字]
- 逻辑依据: [估值方法/预期事件]
- 兑现时间: [日期或周期]
- 关键催化剂: [可能加速的事件]

### 止损计划
- 止损价: [数字]
- 逻辑证伪点: [什么情况说明逻辑错了]
- 技术支撑: [关键技术位参考]

### 时效计划
- 失效时间: [日期]
- 逻辑窗口: [这个逻辑能持续多久]
- 重新评估节点: [需要检查进展的时间点]

## 风险因素
### 高概率风险
- [风险1] (概率: XX%, 影响: XX)
- [风险2] (概率: XX%, 影响: XX)

### 低概率高风险
- [尾部风险1] (概率: XX%, 影响: XX)

## 催化剂
### 已知催化剂
- [催化剂1] (时间: XX, 概率: XX%)
- [催化剂2] (时间: XX, 概率: XX%)

### 潜在催化剂
- [可能的事件]

## 边际效应分析
- 递减规律: [逻辑何时开始递减]
- 饱和点: [市场何时完全定价]"""

    def _parse_reasoning_result(
        self,
        content: str,
        request: ReasoningRequest,
    ) -> ReasoningResult:
        """解析推演结果（GLM-5 增强版）"""
        logic_valid = False
        confidence = 0.5
        reasoning = ""
        exit_plan = ExitPlan()
        risk_factors = []
        catalysts = []
        time_horizon = ""

        # 简单解析（实际可用正则或结构化输出）
        lines = content.split("\n")
        current_section = None

        for line in lines:
            line_stripped = line.strip()

            if "逻辑成立" in line_stripped:
                logic_valid = "true" in line_stripped.lower()
            elif "置信度" in line_stripped:
                try:
                    confidence = float(line_stripped.split(":")[-1].strip())
                except:
                    pass
            elif line_stripped.startswith("## 推理过程"):
                current_section = "reasoning"
            elif line_stripped.startswith("## 风险因素"):
                current_section = "risk"
            elif line_stripped.startswith("## 催化剂"):
                current_section = "catalyst"
            elif line_stripped.startswith("-") and current_section == "risk":
                risk_factors.append(line_stripped[1:].strip())
            elif line_stripped.startswith("-") and current_section == "catalyst":
                catalysts.append(line_stripped[1:].strip())
            elif line_stripped.startswith("### 止盈计划"):
                current_section = "take_profit"
            elif line_stripped.startswith("### 止损计划"):
                current_section = "stop_loss"
            elif line_stripped.startswith("### 时效计划"):
                current_section = "expiration"
            elif current_section == "reasoning" and line_stripped and not line_stripped.startswith("#"):
                reasoning += line_stripped + "\n"

        # 构建退出计划
        exit_plan = self._extract_exit_plan(content, request.current_price)

        # 提取时间窗口
        time_horizon = self._extract_time_horizon(content)

        # 如果推理过程为空，使用全文
        if not reasoning:
            reasoning = content

        return ReasoningResult(
            logic_valid=logic_valid,
            confidence=confidence,
            reasoning=reasoning.strip(),
            exit_plan=exit_plan,
            risk_factors=risk_factors,
            catalysts=catalysts,
            time_horizon=time_horizon,
        )

    def _extract_exit_plan(self, content: str, current_price: float) -> ExitPlan:
        """从内容中提取退出计划"""
        take_profit = {}
        stop_loss = {}
        expiration = {}

        lines = content.split("\n")

        for line in lines:
            line_lower = line.lower()

            if "目标价" in line_lower or "止盈价" in line_lower:
                try:
                    # 提取数字
                    import re
                    numbers = re.findall(r"\d+\.?\d*", line)
                    if numbers:
                        take_profit["price"] = float(numbers[0])
                except:
                    pass

            elif "止损价" in line_lower or "证伪" in line_lower:
                try:
                    import re
                    numbers = re.findall(r"\d+\.?\d*", line)
                    if numbers:
                        stop_loss["price"] = float(numbers[0])
                except:
                    pass

            elif "失效时间" in line_lower or "日期" in line_lower:
                # 提取日期
                import re
                date_match = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", line)
                if date_match:
                    expiration["expire_time"] = date_match.group(1)

        # 如果没有提取到，使用默认值
        if not take_profit:
            take_profit = {
                "price": round(current_price * 1.10, 2),
                "logic": "默认10%止盈目标"
            }

        if not stop_loss:
            stop_loss = {
                "price": round(current_price * 0.95, 2),
                "logic": "默认5%止损线"
            }

        # 默认3个月时效
        if not expiration:
            expire_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
            expiration = {
                "expire_time": expire_date,
                "logic": "默认3个月事件窗口"
            }

        return ExitPlan(
            take_profit=take_profit,
            stop_loss=stop_loss,
            expiration=expiration,
        )

    def _extract_time_horizon(self, content: str) -> str:
        """提取时间窗口"""
        if "短期" in content:
            return "短期（1-3个月）"
        elif "中期" in content:
            return "中期（3-6个月）"
        elif "长期" in content:
            return "长期（6个月以上）"
        return "待评估"

    def _get_fallback_result(self, request: ReasoningRequest) -> ReasoningResult:
        """获取失败时的默认结果"""
        return ReasoningResult(
            logic_valid=False,
            confidence=0.3,
            reasoning="推演失败，无法生成详细分析",
            exit_plan=ExitPlan(
                take_profit={"price": request.current_price * 1.05, "logic": "默认"},
                stop_loss={"price": request.current_price * 0.95, "logic": "默认"},
                expiration={"expire_time": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"), "logic": "默认1个月"},
            ),
            risk_factors=["推演失败，无法识别风险"],
            catalysts=[],
            time_horizon="未知",
        )

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 6000,
        temperature: float = 0.3,
    ) -> AIResponse:
        """
        生成文本（兼容估值引擎接口）

        Args:
            prompt: 提示词
            max_tokens: 最大输出 tokens
            temperature: 温度参数

        Returns:
            AIResponse 响应
        """
        messages = [AIMessage(role="user", content=prompt)]
        return await self.chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )


# =============================================================================
# 全局单例
# =============================================================================

_glm5_client: Optional[GLM5Client] = None


def get_glm5_client() -> GLM5Client:
    """获取 GLM-5 客户端单例"""
    global _glm5_client
    if _glm5_client is None:
        _glm5_client = GLM5Client()
    return _glm5_client
