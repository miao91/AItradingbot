"""
AI TradeBot - MiniMax 客户端

功能：
1. 结构化指令生成
2. JSON 格式输出
3. 决策打包
"""
import json
from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel

from decision.ai_matrix.base import AIClientBase, AIMessage
from decision.ai_matrix.glm4.client import ExitPlan, ReasoningResult
from shared.logging import get_logger


logger = get_logger(__name__)


class DecisionBundle(BaseModel):
    """决策包 - 最终的交易指令"""
    event_id: str
    ticker: str
    action: str  # BUY / SELL / HOLD
    quantity: int
    entry_plan: Dict[str, Any]
    exit_plan: Dict[str, Any]
    confidence: float
    reasoning: str
    generated_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "TEV_20250211_001",
                "ticker": "600000.SH",
                "action": "BUY",
                "quantity": 1000,
                "entry_plan": {"trigger_price": 10.50},
                "exit_plan": {
                    "take_profit": {"price": 12.00},
                    "stop_loss": {"price": 9.80},
                    "expiration": {"expire_time": "2025-05-11"}
                },
                "confidence": 0.75,
                "reasoning": "年报预增，预期股价上涨",
                "generated_at": "2025-02-11T10:00:00"
            }
        }


class MiniMaxClient(AIClientBase):
    """
    MiniMax 客户端

    专注于：
    1. 结构化输出
    2. 决策打包
    3. 格式验证
    """

    def get_api_key_env(self) -> str:
        return "MINIMAX_API_KEY"

    def get_base_url_env(self) -> str:
        return "MINIMAX_BASE_URL"

    def get_model_env(self) -> str:
        return "MINIMAX_MODEL"

    def get_default_model(self) -> str:
        return "abab6.5s-chat"

    def get_system_prompt(self) -> str:
        return """你是 MiniMax，专门负责将分析结果转化为结构化的交易指令。

你的职责：
1. 接收 GLM-4 的推演结果
2. 提取关键数据并格式化
3. 生成符合规范的 JSON 决策包

输出要求：
- 必须是有效的 JSON 格式
- 所有数字必须是数值类型
- 日期必须是 ISO 格式
- 不添加任何额外说明，只输出 JSON

决策包格式：
```json
{{
  "action": "BUY|SELL|HOLD",
  "quantity": 1000,
  "entry_plan": {{
    "trigger_price": 10.50,
    "limit_price": 10.55,
    "entry_condition": "回踩至5日均线"
  }},
  "exit_plan": {{
    "take_profit": {{
      "price": 12.50,
      "logic": "估值修复至15倍PE"
    }},
    "stop_loss": {{
      "price": 9.80,
      "logic": "跌破则逻辑证伪"
    }},
    "expiration": {{
      "expire_time": "2025-05-11",
      "logic": "3个月事件窗口"
    }}
  }},
  "confidence": 0.75
}}
```

规则：
- action 只能是 BUY、SELL 或 HOLD
- quantity 必须是整数
- 所有价格必须是两位小数
- confidence 必须在 0-1 之间"""

    async def generate_decision_bundle(
        self,
        event_id: str,
        ticker: str,
        reasoning_result: ReasoningResult,
        current_price: float,
        default_quantity: int = 1000,
    ) -> Optional[DecisionBundle]:
        """
        生成决策包

        Args:
            event_id: 事件ID
            ticker: 股票代码
            reasoning_result: GLM-4 推演结果
            current_price: 当前价格
            default_quantity: 默认数量

        Returns:
            DecisionBundle 决策包
        """
        # 判断动作
        if reasoning_result.logic_valid and reasoning_result.confidence >= 0.6:
            action = "BUY"
        elif not reasoning_result.logic_valid:
            action = "SELL"
        else:
            action = "HOLD"

        # 构建提示词
        prompt = self._build_decision_prompt(
            ticker=ticker,
            reasoning_result=reasoning_result,
            current_price=current_price,
            default_quantity=default_quantity,
            action=action,
        )

        messages = [AIMessage(role="user", content=prompt)]

        response = await self.chat(
            messages=messages,
            temperature=0.1,  # 低温度保证结构化输出
            max_tokens=1000,
        )

        if not response.success:
            logger.error(f"MiniMax 生成失败: {response.error_message}")
            return None

        # 解析 JSON
        try:
            # 清理可能的 markdown 代码块标记
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            decision_data = json.loads(content.strip())

            # 合并退出计划（如果 MiniMax 没有完整输出）
            if "exit_plan" not in decision_data or not decision_data["exit_plan"]:
                decision_data["exit_plan"] = reasoning_result.exit_plan.model_dump()

            # 确保必需字段存在
            if "entry_plan" not in decision_data:
                decision_data["entry_plan"] = {
                    "trigger_price": current_price,
                    "entry_condition": "当前价格入场"
                }

            # 验证并创建决策包
            bundle = DecisionBundle(
                event_id=event_id,
                ticker=ticker,
                action=decision_data.get("action", action),
                quantity=decision_data.get("quantity", default_quantity),
                entry_plan=decision_data.get("entry_plan", {}),
                exit_plan=decision_data.get("exit_plan", {}),
                confidence=reasoning_result.confidence,
                reasoning=reasoning_result.reasoning,
                generated_at=datetime.now(),
            )

            logger.info(f"决策包生成成功: {bundle.action} {bundle.ticker}")
            return bundle

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, 原始内容: {response.content[:200]}")
            # 返回手动构建的默认决策包
            return self._create_fallback_bundle(
                event_id, ticker, reasoning_result, current_price, default_quantity, action
            )

        except Exception as e:
            logger.error(f"决策包生成失败: {e}")
            return self._create_fallback_bundle(
                event_id, ticker, reasoning_result, current_price, default_quantity, action
            )

    def _build_decision_prompt(
        self,
        ticker: str,
        reasoning_result: ReasoningResult,
        current_price: float,
        default_quantity: int,
        action: str,
    ) -> str:
        """构建决策生成提示词"""
        return f"""请根据以下推演结果，生成结构化的交易决策包。

【标的】{ticker}
【当前价格】{current_price}
【建议动作】{action}
【默认数量】{default_quantity}

【GLM-4 推演结果】
逻辑成立: {reasoning_result.logic_valid}
置信度: {reasoning_result.confidence}

推理过程:
{reasoning_result.reasoning}

退出计划:
{json.dumps(reasoning_result.exit_plan.model_dump(), ensure_ascii=False, indent=2)}

风险因素:
{chr(10).join(f'- {r}' for r in reasoning_result.risk_factors)}

催化剂:
{chr(10).join(f'- {c}' for c in reasoning_result.catalysts)}

【输出要求】
请直接输出 JSON 格式的决策包，不要添加任何其他内容。"""

    def _create_fallback_bundle(
        self,
        event_id: str,
        ticker: str,
        reasoning_result: ReasoningResult,
        current_price: float,
        default_quantity: int,
        action: str,
    ) -> DecisionBundle:
        """创建备用决策包（当生成失败时）"""
        return DecisionBundle(
            event_id=event_id,
            ticker=ticker,
            action=action,
            quantity=default_quantity,
            entry_plan={
                "trigger_price": current_price,
                "entry_condition": "当前价格入场",
            },
            exit_plan=reasoning_result.exit_plan.model_dump(),
            confidence=reasoning_result.confidence,
            reasoning=reasoning_result.reasoning,
            generated_at=datetime.now(),
        )

    def validate_decision_bundle(self, bundle: DecisionBundle) -> bool:
        """
        验证决策包的有效性

        Args:
            bundle: 决策包

        Returns:
            是否有效
        """
        # 检查动作
        if bundle.action not in ["BUY", "SELL", "HOLD"]:
            logger.error(f"无效的动作: {bundle.action}")
            return False

        # 检查数量
        if bundle.quantity <= 0:
            logger.error(f"无效的数量: {bundle.quantity}")
            return False

        # 检查置信度
        if not 0 <= bundle.confidence <= 1:
            logger.error(f"无效的置信度: {bundle.confidence}")
            return False

        # 检查退出计划
        exit_plan = bundle.exit_plan
        if not exit_plan:
            logger.error("缺少退出计划")
            return False

        # 检查价格
        for plan_type in ["take_profit", "stop_loss"]:
            if plan_type in exit_plan and exit_plan[plan_type]:
                price = exit_plan[plan_type].get("price")
                if price and price <= 0:
                    logger.error(f"无效的{plan_type}价格: {price}")
                    return False

        return True
