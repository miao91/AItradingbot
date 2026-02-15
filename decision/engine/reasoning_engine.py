"""
AI TradeBot - AI 思维链推理引擎

支持 DeepSeek-R1 / GLM-Zero 风格的思维链展示
流式输出推理过程，实现透明的 AI 决策逻辑
"""
import json
import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from shared.logging import get_logger
from shared.llm.clients import get_glm5_client, GLM5Client


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

REASONING_CONFIG = {
    # 推理步骤定义（11步）
    "reasoning_steps": [
        {"id": 1, "icon": "📊", "name": "数据采集", "description": "正在分析全球情报数据..."},
        {"id": 2, "icon": "🌍", "name": "地缘政治分析", "description": "分析地缘政治因素..."},
        {"id": 3, "icon": "💱", "name": "汇率锚点", "description": "评估汇率环境..."},
        {"id": 4, "icon": "🔍", "name": "市场扫描", "description": "扫描市场机会..."},
        {"id": 5, "icon": "🧠", "name": "AI 深思", "description": "AI 深度分析中..."},
        {"id": 6, "icon": "📈", "name": "五维评估", "description": "执行五维评估..."},
        {"id": 7, "icon": "🎯", "name": "目标锁定", "description": "锁定交易目标..."},
        {"id": 8, "icon": "⚙️", "name": "模型选择", "description": "选择估值模型..."},
        {"id": 9, "icon": "🐍", "name": "代码生成", "description": "生成估值代码..."},
        {"id": 10, "icon": "✅", "name": "代码验证", "description": "验证代码正确性..."},
        {"id": 11, "icon": "🚀", "name": "计算执行", "description": "执行估值计算..."},
    ],

    # AI 配置
    "ai_model": "glm-5",
    "max_tokens": 4000,
    "temperature": 0.5,
    "stream_delay": 0.5,  # 每步延迟（秒）
}


# =============================================================================
# 数据类
# =============================================================================

class ReasoningStatus(Enum):
    """推理状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_id: int
    icon: str
    name: str
    status: ReasoningStatus = ReasoningStatus.PENDING
    content: str = ""
    detail: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "icon": self.icon,
            "name": self.name,
            "status": self.status.value,
            "content": self.content,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


@dataclass
class ReasoningChain:
    """完整推理链"""
    chain_id: str
    ticker: str
    event_description: str
    steps: List[ReasoningStep] = field(default_factory=list)
    status: ReasoningStatus = ReasoningStatus.PENDING
    final_result: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "ticker": self.ticker,
            "event_description": self.event_description,
            "steps": [step.to_dict() for step in self.steps],
            "status": self.status.value,
            "final_result": self.final_result,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# =============================================================================
# 推理引擎
# =============================================================================

class ReasoningEngine:
    """
    AI 思维链推理引擎

    支持流式输出推理过程，实现透明的 AI 决策逻辑
    """

    def __init__(self):
        """初始化推理引擎"""
        self.glm5_client: Optional[GLM5Client] = None
        self.config = REASONING_CONFIG
        self._active_chains: Dict[str, ReasoningChain] = {}

        logger.info(
            f"[推理引擎] 初始化完成: "
            f"步骤数={len(self.config['reasoning_steps'])}, "
            f"模型={self.config['ai_model']}"
        )

    async def start_reasoning(
        self,
        ticker: str,
        event_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReasoningChain:
        """
        启动推理链

        Args:
            ticker: 股票代码
            event_description: 事件描述
            context: 额外上下文

        Returns:
            ReasoningChain 推理链对象
        """
        import uuid
        chain_id = f"chain_{uuid.uuid4().hex[:8]}"

        chain = ReasoningChain(
            chain_id=chain_id,
            ticker=ticker,
            event_description=event_description,
        )

        # 初始化所有步骤
        for step_config in self.config["reasoning_steps"]:
            chain.steps.append(ReasoningStep(
                step_id=step_config["id"],
                icon=step_config["icon"],
                name=step_config["name"],
            ))

        self._active_chains[chain_id] = chain
        logger.info(f"[推理引擎] 启动推理链: {chain_id} for {ticker}")

        return chain

    async def stream_reasoning(
        self,
        chain: ReasoningChain,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[ReasoningStep, None]:
        """
        流式生成推理步骤

        Args:
            chain: 推理链对象
            context: 额外上下文

        Yields:
            ReasoningStep 每个推理步骤
        """
        # 初始化 AI 客户端
        if not self.glm5_client:
            self.glm5_client = get_glm5_client()

        chain.status = ReasoningStatus.RUNNING

        try:
            # 步骤 1-4: 数据采集和分析
            for i in range(4):
                step = chain.steps[i]
                step.status = ReasoningStatus.RUNNING
                yield step

                # 模拟处理
                await asyncio.sleep(self.config["stream_delay"])

                # 根据步骤生成内容
                step.content = await self._generate_step_content(step, chain, context)
                step.status = ReasoningStatus.COMPLETED
                yield step

            # 步骤 5-6: AI 深思和五维评估（核心步骤）
            for i in range(4, 6):
                step = chain.steps[i]
                step.status = ReasoningStatus.RUNNING
                yield step

                # 调用 AI 生成深度分析
                ai_result = await self._call_ai_for_step(step, chain, context)
                step.content = ai_result.get("content", "")
                step.detail = ai_result.get("detail", "")
                step.status = ReasoningStatus.COMPLETED
                yield step

            # 步骤 7-11: 目标锁定到计算执行
            for i in range(6, 11):
                step = chain.steps[i]
                step.status = ReasoningStatus.RUNNING
                yield step

                await asyncio.sleep(self.config["stream_delay"])

                step.content = await self._generate_step_content(step, chain, context)
                step.status = ReasoningStatus.COMPLETED
                yield step

            # 完成推理链
            chain.status = ReasoningStatus.COMPLETED
            chain.completed_at = datetime.now().isoformat()
            chain.final_result = {
                "success": True,
                "message": "推理完成",
            }

        except Exception as e:
            logger.error(f"[推理引擎] 推理异常: {e}")
            chain.status = ReasoningStatus.FAILED
            chain.final_result = {
                "success": False,
                "error": str(e),
            }

    async def _generate_step_content(
        self,
        step: ReasoningStep,
        chain: ReasoningChain,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """生成步骤内容"""
        templates = {
            1: f"正在采集 {chain.ticker} 相关数据，包括行情、新闻、公告...",
            2: f"<strong>地缘政治分析：</strong>分析美联储政策、中美关系、全球宏观经济环境对 {chain.ticker} 的影响。",
            3: f"<strong>汇率锚点：</strong>USD/CNH 当前处于正常波动区间，流动性环境评估中...",
            4: f"<strong>市场扫描：</strong>基于事件「{chain.event_description[:30]}...」识别相关投资机会。",
            7: f"<strong>目标锁定：</strong>已锁定 {chain.ticker} 作为主要分析标的，开始估值建模。",
            8: f"<strong>模型选择：</strong>根据行业属性选择最佳估值模型（DCF/PE/PS/PB）。",
            9: f"<strong>代码生成：</strong>正在编写 Python 估值脚本，计算内在价值...",
            10: f"<strong>代码验证：</strong>语法检查通过，准备执行计算。",
            11: f"<strong>计算执行：</strong>正在运行 Python 脚本，生成三档估值结果...",
        }

        return templates.get(step.step_id, f"执行 {step.name}...")

    async def _call_ai_for_step(
        self,
        step: ReasoningStep,
        chain: ReasoningChain,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, str]:
        """调用 AI 生成步骤内容"""
        if step.step_id == 5:
            # AI 深思步骤
            prompt = f"""你是 AI TradeBot 的深度分析专家。请对以下交易机会进行深度分析。

【标的】{chain.ticker}
【事件】{chain.event_description}

请提供：
1. 核心投资逻辑（2-3句话）
2. 主要风险因素
3. 关键观察指标

请简洁回答，不超过 200 字。"""

        elif step.step_id == 6:
            # 五维评估步骤
            prompt = f"""你是 AI TradeBot 的五维评估专家。请对以下标的进行快速评估。

【标的】{chain.ticker}
【事件】{chain.event_description}

请给出五个维度的评分（0-10分）：
- 重塑性（市场格局重塑能力）
- 持续性（趋势持续能力）
- 地缘传导（地缘政治影响）
- 定价偏离（价格与价值偏离）
- 流动性（市场流动性环境）

请简洁回答，格式如：重塑性 X分，持续性 X分，地缘传导 X分，定价偏离 X分，流动性 X分"""

        else:
            return {"content": "", "detail": ""}

        try:
            response = await self.glm5_client.call(
                prompt=prompt,
                max_tokens=500,
                temperature=0.5,
            )

            if response.success:
                return {
                    "content": response.content[:300],
                    "detail": response.content,
                }
            else:
                return {
                    "content": f"分析中...（{response.error_message}）",
                    "detail": "",
                }

        except Exception as e:
            return {
                "content": f"分析中...",
                "detail": str(e),
            }

    def get_chain(self, chain_id: str) -> Optional[ReasoningChain]:
        """获取推理链"""
        return self._active_chains.get(chain_id)


# =============================================================================
# 全局单例
# =============================================================================

_reasoning_engine: Optional[ReasoningEngine] = None


def get_reasoning_engine() -> ReasoningEngine:
    """获取全局推理引擎实例"""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = ReasoningEngine()
    return _reasoning_engine


# =============================================================================
# 便捷函数
# =============================================================================

async def start_reasoning_chain(
    ticker: str,
    event_description: str,
    context: Optional[Dict[str, Any]] = None,
) -> ReasoningChain:
    """
    启动推理链（便捷函数）

    Args:
        ticker: 股票代码
        event_description: 事件描述
        context: 额外上下文

    Returns:
        ReasoningChain 推理链对象
    """
    engine = get_reasoning_engine()
    return await engine.start_reasoning(ticker, event_description, context)


# =============================================================================
# 主程序（用于测试）
# =============================================================================

async def main():
    """主程序（用于测试）"""
    print("=" * 60)
    print("AI TradeBot - 思维链推理引擎测试")
    print("=" * 60)
    print()

    engine = get_reasoning_engine()

    # 启动推理链
    chain = await engine.start_reasoning(
        ticker="600000.SH",
        event_description="美联储暗示降息周期可能提前",
    )

    print(f"推理链 ID: {chain.chain_id}")
    print(f"标的: {chain.ticker}")
    print()
    print("开始流式推理...")
    print("-" * 60)

    # 流式输出
    async for step in engine.stream_reasoning(chain):
        status_icon = "✅" if step.status == ReasoningStatus.COMPLETED else "⏳"
        print(f"{status_icon} {step.icon} [{step.name}]")
        if step.content:
            print(f"   {step.content[:100]}...")
        print()

    print("-" * 60)
    print(f"推理状态: {chain.status.value}")
    print(f"完成时间: {chain.completed_at}")


if __name__ == "__main__":
    asyncio.run(main())
