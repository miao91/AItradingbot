"""
AI TradeBot - 事件分析工作流（集成 Tavily AI 搜索）

整合 AI Matrix 协同，实现从信息到交易指令的完整流程
使用 Tavily AI 搜索替代 OpenClaw，实施严格的 Token 防火墙
"""
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from pydantic import BaseModel

from core.database.session import get_db_context
from storage.models.trade_event import TradeEvent, EventStatus, Direction
from perception.market_data import get_market_manager
from perception.search import get_tavily_client, TavilyResponse
from decision.ai_matrix.kimi.client import KimiClient
from decision.ai_matrix.glm4.client import GLM4Client, ReasoningRequest
from decision.ai_matrix.minimax.client import MiniMaxClient, DecisionBundle
from decision.engine import get_news_classifier, NewsItem, ClassificationScore, ValuationImpactLevel
from shared.logging import get_logger
from shared.constants import DEFAULT_DB_PATH


logger = get_logger(__name__)


class AnalysisContext(BaseModel):
    """分析上下文"""
    ticker: str
    event_id: str
    event_url: Optional[str] = None
    event_description: Optional[str] = None
    event_type: str = "announcement"

    # 执行选项
    fetch_search_results: bool = True  # 使用 Tavily 搜索
    fetch_market_data: bool = True
    save_to_db: bool = True

    # AI 追踪
    ai_participants: List[str] = []
    reasoning_log: List[Dict[str, Any]] = []


class AnalysisResult(BaseModel):
    """分析结果"""
    success: bool
    event_id: str
    decision_bundle: Optional[DecisionBundle] = None
    error_message: Optional[str] = None
    steps_completed: List[str] = []
    ai_calls: List[Dict[str, Any]] = []
    prompt_tokens_used: int = 0  # 总使用的 prompt tokens

    # 新增：估值分析结果
    classification_score: Optional[ClassificationScore] = None
    valuation_level: Optional[str] = None
    duration_estimate: Optional[str] = None


class EventAnalyzer:
    """
    事件分析器（Tavily 集成版）

    完整的 AI 协同工作流：
    1. 感知层：获取行情 + Tavily AI 搜索
    2. Kimi：清洗摘要
    3. GLM-4：逻辑推演
    4. MiniMax：生成指令
    5. 存储：写入数据库

    Token 防火墙策略：
    - Tavily 搜索限制 3 个结果，每个最多 1000 字符
    - 输入超过 8000 Token 自动压缩
    - 1210 错误自动重试

    三级过滤机制：
    1. AI 预判：GLM-4-Flash 快速评分
    2. 深度筛选：仅对 >7 分新闻启动 Tavily 搜索
    3. 估值分析：区分短期情绪与长期价值重塑
    """

    def __init__(self):
        """初始化分析器"""
        self.market_mgr = get_market_manager()
        self.kimi = KimiClient()
        self.glm4 = GLM4Client()
        self.minimax = MiniMaxClient()
        self.tavily = get_tavily_client()
        self.classifier = get_news_classifier()  # 新增：分类器

    async def analyze_event(
        self,
        ticker: str,
        event_url: Optional[str] = None,
        event_description: Optional[str] = None,
        event_type: str = "announcement",
        **kwargs
    ) -> AnalysisResult:
        """
        分析单个事件

        Args:
            ticker: 股票代码
            event_url: 事件 URL（可选，仅作记录）
            event_description: 事件描述
            event_type: 事件类型
            **kwargs: 其他参数

        Returns:
            AnalysisResult 分析结果
        """
        # 生成事件 ID
        event_id = f"EVT_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"开始分析事件: {event_id} - {ticker}")

        # 构建上下文
        context = AnalysisContext(
            ticker=ticker,
            event_id=event_id,
            event_url=event_url,
            event_description=event_description,
            event_type=event_type,
            **kwargs
        )

        result = AnalysisResult(
            success=False,
            event_id=event_id,
            steps_completed=[],
            ai_calls=[],
            prompt_tokens_used=0,
            classification_score=None,  # 新增
            valuation_level=None,  # 新增
            duration_estimate=None,  # 新增
        )

        try:
            # ========== 步骤 0: AI 预判（新增） ==========
            logger.info(f"[步骤 0] AI 预判：快速评分")
            classification_score = await self._classification_step(context)
            result.classification_score = classification_score
            result.valuation_level = classification_score.valuation_level.value
            result.duration_estimate = classification_score.duration_estimate.value
            result.steps_completed.append("classification")

            # 检查是否需要深度分析
            if classification_score.total_score < 7.0:
                logger.info(f"[预判] 评分 {classification_score.total_score:.1f} < 7.0，跳过深度分析")
                result.success = True  # 分析完成，但无交易指令
                result.error_message = f"评分过低 ({classification_score.total_score:.1f}/10.0)，无需深度分析"
                return result

            # ========== 步骤 1: 感知层 ==========
            logger.info(f"[步骤 1] 感知层：获取数据（Tavily 搜索 + 行情）")
            current_price, market_context, search_results = await self._perception_step(context)
            result.steps_completed.append("perception")

            # ========== 步骤 2: Kimi 清洗 ==========
            logger.info(f"[步骤 2] Kimi：清洗摘要")
            summary_result = await self._kimi_step(context, search_results)
            result.steps_completed.append("kimi")
            result.prompt_tokens_used += getattr(summary_result, 'prompt_tokens', 0)
            result.ai_calls.append({
                "model": "kimi",
                "action": "summarize_event",
                "duration_ms": 0,
                "success": True,
            })

            # ========== 步骤 3: GLM-4 推演 ==========
            logger.info(f"[步骤 3] GLM-4：逻辑推演")
            reasoning_result = await self._glm4_step(
                context, summary_result.summary, current_price, market_context
            )
            result.steps_completed.append("glm4")
            result.prompt_tokens_used += getattr(reasoning_result, 'prompt_tokens', 0)
            result.ai_calls.append({
                "model": "glm4",
                "action": "reason_event",
                "success": reasoning_result.logic_valid,
            })

            # 检查逻辑是否成立
            if not reasoning_result.logic_valid or reasoning_result.confidence < 0.5:
                logger.info(f"逻辑不成立或置信度过低，停止生成交易指令")
                result.success = True  # 分析完成，但无交易指令
                result.error_message = f"逻辑不成立或置信度过低 (confidence={reasoning_result.confidence})"
                return result

            # ========== 步骤 4: MiniMax 打包 ==========
            logger.info(f"[步骤 4] MiniMax：生成指令")
            decision_bundle = await self._minimax_step(
                context, reasoning_result, current_price
            )
            result.steps_completed.append("minimax")
            result.prompt_tokens_used += getattr(decision_bundle, 'prompt_tokens', 0)
            result.ai_calls.append({
                "model": "minimax",
                "action": "generate_decision_bundle",
                "success": True,
            })

            if not decision_bundle:
                raise RuntimeError("决策包生成失败")

            # ========== 步骤 5: 存储到数据库 ==========
            if context.save_to_db:
                logger.info(f"[步骤 5] 存储到数据库")
                await self._storage_step(context, decision_bundle, reasoning_result)
                result.steps_completed.append("storage")

            result.success = True
            result.decision_bundle = decision_bundle

            logger.info(f"✅ 事件分析完成: {event_id}, 总 Token: {result.prompt_tokens_used}")
            return result

        except Exception as e:
            logger.error(f"❌ 事件分析失败: {e}")
            result.error_message = str(e)
            result.success = False
            return result

    async def _classification_step(
        self,
        context: AnalysisContext,
    ) -> ClassificationScore:
        """
        步骤 0：AI 预判（新增）

        使用 GLM-4-Flash 快速评分，决定是否启动深度分析

        Args:
            context: 分析上下文

        Returns:
            ClassificationScore 分类评分
        """
        from decision.engine import NewsItem

        # 构建新闻项
        news = NewsItem(
            title=context.event_description[:200] if context.event_description else "未知事件",
            content=context.event_description[:500] if context.event_description else "",
            source="system",
            ticker=context.ticker,
        )

        # 调用分类器
        score = await self.classifier.classify(news)

        logger.info(
            f"[预判] 评分={score.total_score:.1f}/10.0, "
            f"类别={score.category.value}, "
            f"估值级别={score.valuation_level.value}"
        )

        return score

    async def _perception_step(
        self,
        context: AnalysisContext,
    ) -> tuple:
        """
        感知层：获取数据（并行优化版）

        使用 asyncio.gather 并行获取：
        - 实时行情数据
        - Tavily AI 搜索结果
        - 历史汇率数据（如需）

        Returns:
            (current_price, market_context, search_results)
        """
        # 并行获取行情和搜索结果
        async def _fetch_quote():
            """获取实时行情"""
            if not context.fetch_market_data:
                return 10.0, ""
            try:
                quote = await self.market_mgr.get_realtime_quote(context.ticker)
                market_context = f"""
当前价格: {quote.current_price}
涨跌幅: {(quote.current_price - quote.prev_close) / quote.prev_close * 100:+.2f}%
成交量: {quote.volume:,}
"""
                return quote.current_price, market_context
            except Exception as e:
                logger.warning(f"获取行情失败: {e}，使用默认值")
                return 10.0, "行情数据获取失败"

        async def _fetch_search():
            """获取 Tavily 搜索结果"""
            if not context.fetch_search_results or not context.event_description:
                return context.event_description or ""

            try:
                logger.info(f"[感知] 使用 Tavily 搜索: {context.ticker}")
                tavily_response = await self.tavily.search_for_stock_event(
                    ticker=context.ticker,
                    event_description=context.event_description[:200],
                )

                if tavily_response.success:
                    search_results = self.tavily.format_results_for_ai(tavily_response)
                    logger.info(
                        f"[感知] Tavily 搜索成功: {len(tavily_response.results)} 结果, "
                        f"{tavily_response.total_compressed_chars} 字符"
                    )
                    return search_results
                else:
                    logger.warning(f"[感知] Tavily 搜索失败: {tavily_response.error_message}")
                    return f"【事件描述】{context.event_description}"

            except Exception as e:
                logger.warning(f"[感知] Tavily 搜索异常: {e}，使用原始描述")
                return context.event_description

        # 并行执行
        logger.info("[感知] 并行获取数据...")
        (current_price, market_context), search_results = await asyncio.gather(
            _fetch_quote(),
            _fetch_search(),
        )

        return current_price, market_context, search_results

    async def _kimi_step(
        self,
        context: AnalysisContext,
        search_results: str,
    ) -> Any:
        """Kimi 步骤：清洗摘要"""
        if not search_results or len(search_results) < 50:
            # 内容太短，直接返回
            from decision.ai_matrix.kimi.client import KimiSummaryResult
            return KimiSummaryResult(
                summary=search_results or "无内容",
                key_facts=[],
                extracted_numbers={},
                original_length=len(search_results),
            )

        summary_result = await self.kimi.summarize_announcement(search_results)

        logger.info(f"Kimi 摘要完成: {summary_result.compressed_ratio}% 压缩比")
        logger.debug(f"摘要: {summary_result.summary[:200]}...")

        return summary_result

    async def _glm4_step(
        self,
        context: AnalysisContext,
        summary: str,
        current_price: float,
        market_context: str,
    ) -> Any:
        """GLM-4 步骤：逻辑推演（含估值分析）"""
        # 增强的推理请求，包含估值分析
        enhanced_summary = f"""{summary}

【估值重塑分析】
请重点分析：该消息如何改变 {context.ticker} 的估值模型？
- 短期情绪扰动 vs 长期价值重塑
- 估值影响级别：{context.valuation_level if hasattr(context, 'valuation_level') and context.valuation_level else '待评估'}
- 预计影响时长：{context.duration_estimate if hasattr(context, 'duration_estimate') and context.duration_estimate else '待评估'}
"""

        request = ReasoningRequest(
            ticker=context.ticker,
            event_summary=enhanced_summary,  # 使用增强摘要
            current_price=current_price,
            event_type=context.event_type,
            market_context=market_context if market_context else None,
        )

        reasoning_result = await self.glm4.reason_event(request)

        logger.info(
            f"GLM-4 推演完成: "
            f"逻辑成立={reasoning_result.logic_valid}, "
            f"置信度={reasoning_result.confidence}"
        )

        return reasoning_result

    async def _minimax_step(
        self,
        context: AnalysisContext,
        reasoning_result: Any,
        current_price: float,
    ) -> Optional[DecisionBundle]:
        """MiniMax 步骤：生成决策包"""
        decision_bundle = await self.minimax.generate_decision_bundle(
            event_id=context.event_id,
            ticker=context.ticker,
            reasoning_result=reasoning_result,
            current_price=current_price,
            default_quantity=1000,
        )

        if decision_bundle:
            # 验证决策包
            if self.minimax.validate_decision_bundle(decision_bundle):
                logger.info(
                    f"MiniMax 决策包: {decision_bundle.action} "
                    f"{decision_bundle.quantity}股 "
                    f"@{decision_bundle.entry_plan.get('trigger_price', 0)}"
                )
            else:
                logger.warning("决策包验证失败")
                return None

        return decision_bundle

    async def _storage_step(
        self,
        context: AnalysisContext,
        decision_bundle: DecisionBundle,
        reasoning_result: Any,
    ) -> None:
        """存储步骤：写入数据库"""
        async with get_db_context() as db:
            # 创建 TradeEvent
            event = TradeEvent(
                id=context.event_id,
                ticker=decision_bundle.ticker,
                ticker_name=decision_bundle.ticker,
                direction=Direction.LONG if decision_bundle.action == "BUY" else Direction.SHORT,
                current_status=EventStatus.OBSERVING,
                event_description=context.event_description or "AI 分析生成",
                logic_summary=decision_bundle.reasoning[:500],
                confidence=decision_bundle.confidence,
                source_type="tavily_ai_analysis",  # 标记来源
                category=context.event_type,
                ai_participants=["tavily", "kimi", "glm4", "minimax"],  # 包含 Tavily
                reasoning_log=[
                    {
                        "step": "tavily",
                        "action": "ai_search",
                        "timestamp": datetime.now().isoformat(),
                    },
                    {
                        "step": "kimi",
                        "action": "summarize_announcement",
                        "timestamp": datetime.now().isoformat(),
                    },
                    {
                        "step": "glm4",
                        "action": "reason_event",
                        "logic_valid": reasoning_result.logic_valid,
                        "confidence": reasoning_result.confidence,
                        "timestamp": datetime.now().isoformat(),
                    },
                    {
                        "step": "minimax",
                        "action": "generate_decision_bundle",
                        "final_action": decision_bundle.action,
                        "timestamp": datetime.now().isoformat(),
                    },
                ],
                entry_plan=decision_bundle.entry_plan,
                exit_plan=decision_bundle.exit_plan,
            )

            db.add(event)
            await db.commit()

            logger.info(f"事件已存储到数据库: {context.event_id}")


# =============================================================================
# 便捷函数
# =============================================================================

async def analyze_event(
    ticker: str,
    event_url: Optional[str] = None,
    event_description: Optional[str] = None,
    event_type: str = "announcement",
) -> AnalysisResult:
    """
    分析事件的便捷函数

    Args:
        ticker: 股票代码
        event_url: 事件 URL（可选）
        event_description: 事件描述
        event_type: 事件类型

    Returns:
        AnalysisResult 分析结果
    """
    analyzer = EventAnalyzer()
    return await analyzer.analyze_event(
        ticker=ticker,
        event_url=event_url,
        event_description=event_description,
        event_type=event_type,
    )
