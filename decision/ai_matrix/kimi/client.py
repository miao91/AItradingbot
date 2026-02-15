"""
AI TradeBot - Kimi (Moonshot AI) 客户端

功能：
1. 处理长文本（128K context）
2. 公告清洗与摘要生成
3. 事实提取与结构化
"""
import json
from typing import Optional, Dict, Any

from pydantic import BaseModel

from decision.ai_matrix.base import AIClientBase, AIMessage
from shared.logging import get_logger


logger = get_logger(__name__)


class KimiSummaryRequest(BaseModel):
    """Kimi 摘要请求"""
    content: str
    max_length: int = 500
    extract_facts: bool = True
    extract_numbers: bool = True


class KimiSummaryResult(BaseModel):
    """Kimi 摘要结果"""
    summary: str
    key_facts: list[str] = []
    extracted_numbers: Dict[str, Any] = {}
    original_length: int = 0
    compressed_ratio: float = 0.0


class KimiClient(AIClientBase):
    """
    Kimi (Moonshot AI) 客户端

    专注于：
    1. 长文本处理（公告、研报清洗）
    2. 核心事实摘要（500字以内）
    3. 数据提取（数字、日期、关键指标）
    """

    def get_api_key_env(self) -> str:
        return "KIMI_API_KEY"

    def get_base_url_env(self) -> str:
        return "KIMI_BASE_URL"

    def get_model_env(self) -> str:
        return "KIMI_MODEL"

    def get_default_model(self) -> str:
        return "moonshot-v1-128k"

    def get_system_prompt(self) -> str:
        return """你是 Kimi，专业的金融信息处理助手。

你的核心能力：
1. **长文本理解**：能够处理大量文本，提取关键信息
2. **事实提取**：准确提取公告、研报中的核心事实
3. **数据提取**：识别并提取数字、日期、财务指标等
4. **简洁摘要**：将长文压缩为 500 字以内的核心摘要

处理规则：
- 保留所有关键数字（金额、比例、日期）
- 保留公司名称、股票代码
- 保留因果关系和逻辑链条
- 去除冗余表述和客套话
- 客观中立，不添加主观判断

输出格式：
- 摘要：简洁的事实陈述
- 关键事实：按重要性排序的要点列表
- 提取数据：结构化的数字和指标"""

    async def summarize_announcement(
        self,
        markdown_content: str,
        max_length: int = 500,
    ) -> KimiSummaryResult:
        """
        摘要公告内容

        Args:
            markdown_content: Markdown 格式的公告内容
            max_length: 最大摘要长度

        Returns:
            KimiSummaryResult 摘要结果
        """
        original_length = len(markdown_content)

        # 构建提示词
        prompt = f"""请分析以下公告内容，生成结构化摘要。

【要求】
1. 摘要控制在 {max_length} 字以内
2. 提取 3-5 个关键事实
3. 提取所有重要数字和指标

【公告内容】
{markdown_content}

【输出格式】
## 摘要
[简洁的事实陈述]

## 关键事实
- 事实1
- 事实2
- 事实3

## 提取数据
{{"股票代码": "xxx", "公告日期": "xxx", "关键指标": ...}}"""

        messages = [
            AIMessage(role="user", content=prompt)
        ]

        response = await self.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
        )

        if not response.success:
            logger.error(f"Kimi 摘要失败: {response.error_message}")
            return KimiSummaryResult(
                summary="摘要生成失败",
                original_length=original_length,
            )

        # 解析结果
        content = response.content
        summary, key_facts, extracted_numbers = self._parse_summary_result(content)

        return KimiSummaryResult(
            summary=summary,
            key_facts=key_facts,
            extracted_numbers=extracted_numbers,
            original_length=original_length,
            compressed_ratio=round(len(summary) / original_length * 100, 2) if original_length > 0 else 0,
        )

    def _parse_summary_result(self, content: str) -> tuple:
        """
        解析 Kimi 返回的摘要结果

        Args:
            content: Kimi 返回的内容

        Returns:
            (summary, key_facts, extracted_numbers)
        """
        summary = ""
        key_facts = []
        extracted_numbers = {}

        # 简单解析（实际可用更复杂的解析逻辑）
        lines = content.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()

            if line.startswith("## 摘要"):
                current_section = "summary"
            elif line.startswith("## 关键事实"):
                current_section = "facts"
            elif line.startswith("## 提取数据"):
                current_section = "data"
            elif line.startswith("-") and current_section == "facts":
                key_facts.append(line[1:].strip())
            elif current_section == "summary" and line:
                summary += line + "\n"
            elif current_section == "data":
                # 尝试解析 JSON
                try:
                    if line.startswith("{"):
                        extracted_numbers = json.loads(line)
                except:
                    pass

        # 如果没有解析到结构，使用全文作为摘要
        if not summary:
            summary = content

        return summary.strip(), key_facts, extracted_numbers

    async def extract_event_logic(
        self,
        announcement: str,
        market_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        提取事件逻辑（用于后续推演）

        Args:
            announcement: 公告内容
            market_context: 市场背景（可选）

        Returns:
            事件逻辑字典
        """
        context_info = f"\n【市场背景】\n{market_context}" if market_context else ""

        prompt = f"""请分析以下公告，提取交易相关的核心逻辑。

【公告内容】
{announcement}
{context_info}

【输出格式】
{{"事件类型": "xxx", "核心逻辑": "xxx", "影响方向": "positive/negative", "关键指标": [...], "置信度": 0.7}}"""

        messages = [AIMessage(role="user", content=prompt)]

        response = await self.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=800,
        )

        if response.success:
            try:
                # 尝试解析 JSON
                result = json.loads(response.content)
                return result
            except:
                # 如果解析失败，返回基本信息
                return {
                    "事件类型": "未知",
                    "核心逻辑": response.content[:200],
                    "影响方向": "neutral",
                    "置信度": 0.5,
                }

        return {}
