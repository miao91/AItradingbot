"""
AI TradeBot - GLM-5 核心编排器

GLM-5 作为总指挥，负责：
1. 任务复杂度判定
2. 专家模型调度（Kimi长文、MiniMax语境）
3. 普通快讯直接处理
4. GPU蒙特卡洛代码生成
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from shared.logging import get_logger

logger = get_logger(__name__)


class TaskComplexity(Enum):
    """任务复杂度"""

    SIMPLE = "simple"  # 普通快讯，GLM-5 直接处理
    MEDIUM = "medium"  # 中等复杂，需要基础分析
    COMPLEX = "complex"  # 复杂任务，需要专家协作
    LONG_FORM = "long_form"  # 超长文档，需要分段处理


@dataclass
class AnalysisRequest:
    """分析请求"""

    ticker: str
    event_description: str
    current_price: Optional[float] = None
    context: Optional[Dict[str, Any]] = None
    document_path: Optional[str] = None  # 长文档路径
    complexity: TaskComplexity = TaskComplexity.SIMPLE


@dataclass
class ImpactMatrix:
    """新闻影响矩阵"""

    news_summary: str  # 新闻内容摘要
    geopolitical_score: float  # 地缘政治评分 0-10
    tech_breakthrough: str  # 技术突破描述
    policy_relevance: str  # 国家政策关联
    supply_chain_impact: str  # 产业链发展影响
    cost_price_change: str  # 成本/价格变化预测
    related_companies: List[str]  # 涉及公司/代码
    overall_score: float = 0.0  # 综合影响评分


@dataclass
class AnalysisResult:
    """分析结果"""

    ticker: str
    summary: str
    score: float
    sentiment: str
    exit_plan: Optional[Dict[str, Any]] = None
    reasoning: str = ""
    code_generated: Optional[str] = None
    processing_time_ms: int = 0
    model_used: str = "glm-5"
    expert_models: List[str] = field(default_factory=list)
    # 新增：结构化影响矩阵
    impact_matrix: Optional[ImpactMatrix] = None
    # 新增：多条新闻的影响矩阵列表
    impact_matrices: List[ImpactMatrix] = field(default_factory=list)


class GLM5Orchestrator:
    """
    GLM-5 核心编排器

    职责：
    1. 判定任务复杂度
    2. 调度专家模型
    3. 汇总分析结果
    4. 生成GPU优化代码
    """

    def __init__(self):
        self._glm5_client = None
        self._kimi_client = None
        self._minimax_client = None

        # 性能统计
        self._stats = {
            "total_requests": 0,
            "glm5_direct": 0,
            "kimi_calls": 0,
            "minimax_calls": 0,
            "avg_latency_ms": 0,
        }

        logger.info("[GLM-5 编排器] 初始化完成")

    async def _init_clients(self):
        """延迟初始化客户端"""
        if self._glm5_client is None:
            try:
                from decision.ai_matrix.glm5.client import GLM5Client

                self._glm5_client = GLM5Client()
            except Exception as e:
                logger.error(f"[编排器] GLM-5 客户端初始化失败: {e}")

    def classify_complexity(self, request: AnalysisRequest) -> TaskComplexity:
        """
        判定任务复杂度

        规则：
        - 有长文档路径 → LONG_FORM
        - 事件描述超过500字 → COMPLEX
        - 涉及多个标的 → COMPLEX
        - 默认 → SIMPLE
        """
        if request.document_path:
            return TaskComplexity.LONG_FORM

        if request.event_description and len(request.event_description) > 500:
            return TaskComplexity.COMPLEX

        if request.context and len(request.context.get("tickers", [])) > 1:
            return TaskComplexity.COMPLEX

        return TaskComplexity.SIMPLE

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        """
        分析入口 - GLM-5 总指挥

        根据复杂度决定处理策略：
        - SIMPLE: GLM-5 直接完成 [摘要+打分+估值]
        - MEDIUM: GLM-5 + 基础分析
        - COMPLEX: GLM-5 调度专家协作
        - LONG_FORM: Kimi分段预处理 → GLM-5汇总
        """
        start_time = datetime.now()
        await self._init_clients()

        # 自动判定复杂度
        if request.complexity == TaskComplexity.SIMPLE:
            request.complexity = self.classify_complexity(request)

        self._stats["total_requests"] += 1
        logger.info(f"[编排器] 开始分析: {request.ticker}, 复杂度={request.complexity.value}")

        try:
            if request.complexity == TaskComplexity.SIMPLE:
                result = await self._analyze_simple(request)
                self._stats["glm5_direct"] += 1

            elif request.complexity == TaskComplexity.LONG_FORM:
                result = await self._analyze_long_form(request)
                self._stats["kimi_calls"] += 1

            else:
                result = await self._analyze_complex(request)
                self._stats["minimax_calls"] += 1

        except Exception as e:
            logger.error(f"[编排器] 分析失败: {e}")
            result = self._get_fallback_result(request, str(e))

        # 记录处理时间
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        result.processing_time_ms = int(processing_time)

        # 更新统计
        self._update_stats(processing_time)

        return result

    async def _analyze_simple(self, request: AnalysisRequest) -> AnalysisResult:
        """
        简单任务 - GLM-5 直接完成

        一步完成：摘要 + 打分 + 重估值判断
        """
        prompt = f"""你是 GLM-5，专业的交易分析师。请快速分析以下事件。

【标的】{request.ticker}
【当前价格】{request.current_price or '未知'}
【事件】{request.event_description}

请一步完成以下分析：

1. **事件摘要**（1-2句话）
2. **重要性评分**（0-10分，10分最重要）
3. **情绪判断**（positive/neutral/negative）
4. **投资建议**（买入/观望/卖出，简短理由）
5. **退出策略**
   - 目标价: XX（基于...）
   - 止损价: XX（基于...）
   - 持有周期: XX天/周/月

请简洁回答，不超过300字。"""

        try:
            response = await self._glm5_client.call(
                prompt=prompt,
                max_tokens=500,
                temperature=0.5,
            )

            if response.success:
                return self._parse_glm5_response(request, response.content)
            else:
                return self._get_fallback_result(request, response.error_message)

        except Exception as e:
            return self._get_fallback_result(request, str(e))

    async def _analyze_long_form(self, request: AnalysisRequest) -> AnalysisResult:
        """
        长文档任务 - Kimi预处理 + GLM-5汇总（并行优化版）

        流程：
        1. 并行获取：Kimi 长文处理 + 外部数据（汇率等）
        2. GLM-5 进行终审逻辑汇总
        """
        expert_models = ["kimi-128k"]

        try:
            # 并行：Kimi处理 + 外部数据获取
            async def _fetch_forex():
                """获取汇率数据"""
                try:
                    from core.api.v1.external import get_usdcnh_rate

                    rate = await get_usdcnh_rate()
                    return f"USD/CNH 汇率: {rate}"
                except Exception:
                    return ""

            # 并行执行 Kimi 和汇率获取
            kimi_summary, forex_context = await asyncio.gather(
                self._call_kimi_for_long_document(request),
                _fetch_forex(),
            )

            # GLM-5 汇总分析
            prompt = f"""你是 GLM-5，基于 Kimi 提取的关键信息进行最终决策。

【标的】{request.ticker}
【Kimi 提取的关键信息】
{kimi_summary}
{f"【市场环境】{forex_context}" if forex_context else ""}

请进行最终分析决策：
1. 核心投资逻辑
2. 风险评估
3. 退出策略

请简洁回答，不超过200字。"""

            response = await self._glm5_client.call(
                prompt=prompt,
                max_tokens=400,
                temperature=0.5,
            )

            if response.success:
                result = self._parse_glm5_response(request, response.content)
                result.expert_models = expert_models
                return result
            else:
                return self._get_fallback_result(request, response.error_message)

        except Exception as e:
            return self._get_fallback_result(request, str(e))

    async def _analyze_complex(self, request: AnalysisRequest) -> AnalysisResult:
        """
        复杂任务 - 多专家协作
        """
        # 简化处理，直接用 GLM-5
        return await self._analyze_simple(request)

    async def analyze_with_impact_matrix(
        self,
        news_content: str,
        default_ticker: str = "MARKET",
    ) -> List[ImpactMatrix]:
        """
        结构化影响矩阵分析

        将新闻/快讯解析为标准化的影响矩阵

        Args:
            news_content: 新闻内容（可以是多条新闻的合并文本）
            default_ticker: 默认标的

        Returns:
            List[ImpactMatrix]: 影响矩阵列表
        """
        await self._init_clients()

        prompt = f"""你是 GLM-5，专业的投资分析师。请分析以下新闻，并输出结构化的 JSON 数据。

【新闻内容】
{news_content}

请严格按照以下 JSON 格式输出一个数组，每条重要新闻对应一个对象：

```json
[
  {{
    "news_summary": "新闻摘要（1-2句话，简明扼要）",
    "geopolitical_score": 8.5,
    "tech_breakthrough": "技术突破描述（如：涉及XX纳米工艺/专利/核心技术节点，或填'无直接影响'）",
    "policy_relevance": "国家政策关联（如：符合XX产业政策/受XX禁令影响，或填'无直接关联'）",
    "supply_chain_impact": "产业链影响（上游/中游/下游地位变化，如：'上游原材料供应商受益'）",
    "cost_price_change": "成本/价格变化预测（如：'预计原材料成本上涨5-10%，终端产品可能涨价3%'）",
    "related_companies": ["公司名称/股票代码"],
    "overall_score": 7.5
  }}
]
```

评分规则：
- geopolitical_score (0-10): 对全球/区域局势的影响权重，10分最高
- overall_score (0-10): 综合投资影响评分，考虑上述所有因素

请只输出 JSON 数组，不要有其他文字。"""

        try:
            response = await self._glm5_client.call(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.3,
            )

            if response.success:
                return self._parse_impact_matrix(response.content)
            else:
                logger.error(f"[矩阵分析] GLM-5 调用失败: {response.error_message}")
                return []

        except Exception as e:
            logger.error(f"[矩阵分析] 异常: {e}")
            return []

    def _parse_impact_matrix(self, content: str) -> List[ImpactMatrix]:
        """解析 GLM-5 返回的影响矩阵 JSON"""
        import json
        import re

        matrices = []

        # 尝试提取 JSON 数组
        try:
            # 查找 JSON 数组
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                json_str = json_match.group(0)
                data_list = json.loads(json_str)

                for item in data_list:
                    matrix = ImpactMatrix(
                        news_summary=item.get("news_summary", ""),
                        geopolitical_score=float(item.get("geopolitical_score", 0)),
                        tech_breakthrough=item.get("tech_breakthrough", "无"),
                        policy_relevance=item.get("policy_relevance", "无"),
                        supply_chain_impact=item.get("supply_chain_impact", "无"),
                        cost_price_change=item.get("cost_price_change", "无"),
                        related_companies=item.get("related_companies", []),
                        overall_score=float(item.get("overall_score", 0)),
                    )
                    matrices.append(matrix)

                logger.info(f"[矩阵分析] 解析成功，共 {len(matrices)} 条影响矩阵")

        except json.JSONDecodeError as e:
            logger.error(f"[矩阵分析] JSON 解析失败: {e}")
        except Exception as e:
            logger.error(f"[矩阵分析] 解析异常: {e}")

        return matrices

    async def detect_industry_from_company(
        self,
        company_name: str,
        ticker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        检测公司所属行业

        优先级：
        1. 调用 Tushare 获取行业分类
        2. 使用 GLM-5 推断行业
        3. 返回默认行业

        Args:
            company_name: 公司名称
            ticker: 股票代码（可选）

        Returns:
            {
                "industry": "行业名称",
                "methodology": {...},  # 行业估值方法论
                "source": "tushare|ai|default"
            }
        """
        from decision.engine.valuation_tool import (
            get_industry_methodology,
            format_methodology_for_prompt,
        )

        # 1. 尝试 Tushare
        if ticker:
            try:
                # 这里可以调用 Tushare API 获取行业分类
                # 暂时使用模拟数据
                pass
            except Exception as e:
                logger.warning(f"[行业检测] Tushare 获取失败: {e}")

        # 2. 使用 GLM-5 推断行业
        await self._init_clients()

        prompt = f"""你是专业的行业分析师。请判断以下公司属于哪个行业。

公司: {company_name}
股票代码: {ticker or '未知'}

请从以下行业中选择最匹配的一个，只输出行业名称：

1. 互联网/SaaS
2. 半导体/硬件
3. 银行/保险
4. 生物医药(创新药)
5. 传统制造/消费
6. 重资产(钢铁/电力)
7. 资源/矿产
8. 房地产

只输出行业名称，不要有其他文字。"""

        try:
            response = await self._glm5_client.call(
                prompt=prompt,
                max_tokens=50,
                temperature=0.1,
            )

            if response.success:
                # 解析行业
                content = response.content.strip()

                # 匹配行业
                industries = [
                    "互联网/SaaS", "半导体/硬件", "银行/保险",
                    "生物医药(创新药)", "传统制造/消费",
                    "重资产(钢铁/电力)", "资源/矿产", "房地产"
                ]

                matched_industry = "传统制造/消费"  # 默认
                for ind in industries:
                    if ind in content or any(k in content for k in ind.split("/")):
                        matched_industry = ind
                        break

                methodology = get_industry_methodology(matched_industry)

                logger.info(f"[行业检测] GLM-5 推断: {company_name} -> {matched_industry}")

                return {
                    "industry": matched_industry,
                    "methodology": methodology,
                    "source": "ai",
                    "confidence": 0.8,
                }

        except Exception as e:
            logger.error(f"[行业检测] GLM-5 推断失败: {e}")

        # 3. 返回默认
        return {
            "industry": "传统制造/消费",
            "methodology": get_industry_methodology("传统制造/消费"),
            "source": "default",
            "confidence": 0.5,
        }

    async def generate_valuation_report(
        self,
        company_name: str,
        ticker: str,
        impact_matrix: ImpactMatrix,
        current_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        生成专业估值报告

        流程：
        1. 检测行业
        2. 选择估值模型
        3. 调用 GLM-5 生成 Python 估值代码
        4. 执行计算得到三档估值

        Args:
            company_name: 公司名称
            ticker: 股票代码
            impact_matrix: 影响矩阵
            current_price: 当前价格

        Returns:
            估值报告字典
        """
        # 1. 检测行业
        industry_info = await self.detect_industry_from_company(company_name, ticker)
        industry = industry_info["industry"]
        methodology = industry_info["methodology"]

        # 2. 准备估值报告
        report = {
            "company": company_name,
            "ticker": ticker,
            "industry": industry,
            "model": methodology.get("core_models", ["P/E"]),
            "core_logic": methodology.get("core_logic", ""),
            "reference_metrics": methodology.get("reference_metrics", []),
            "three_tier_valuation": {
                "bullish": None,
                "neutral": None,
                "bearish": None,
            },
            "pricing_diagnosis": {
                "current_price": current_price,
                "avg_valuation": None,
                "drift_pct": None,
            },
            "conclusion": None,
        }

        # 3. 如果有当前价格，计算三档估值
        if current_price:
            # 简化版：基于影响矩阵评分调整
            score_factor = impact_matrix.overall_score / 10.0  # 0-1

            # 三档估值（基于当前价格）
            report["three_tier_valuation"] = {
                "bullish": round(current_price * (1 + 0.15 + score_factor * 0.15), 2),
                "neutral": round(current_price * (1 + score_factor * 0.05 - 0.02), 2),
                "bearish": round(current_price * (0.85 - (1 - score_factor) * 0.1), 2),
            }

            # 定价诊断
            avg = sum([
                report["three_tier_valuation"]["bullish"],
                report["three_tier_valuation"]["neutral"],
                report["three_tier_valuation"]["bearish"],
            ]) / 3

            drift = (avg - current_price) / current_price * 100

            report["pricing_diagnosis"] = {
                "current_price": current_price,
                "avg_valuation": round(avg, 2),
                "drift_pct": round(drift, 2),
            }

            # 结论
            if drift > 15:
                report["conclusion"] = "显著折价"
                report["conclusion_detail"] = f"估值均值高于市价 {drift:.1f}%，存在上涨空间"
            elif drift < -15:
                report["conclusion"] = "显著溢价"
                report["conclusion_detail"] = f"估值均值低于市价 {abs(drift):.1f}%，需谨慎"
            else:
                report["conclusion"] = "定价合理"
                report["conclusion_detail"] = "估值与市场价格基本一致"

        logger.info(f"[估值报告] {company_name} ({industry}): {report.get('conclusion', '待评估')}")

        return report

    async def _call_kimi_for_long_document(self, request: AnalysisRequest) -> str:
        """调用 Kimi 处理长文档"""
        try:
            from decision.ai_matrix.kimi.client import KimiClient

            if self._kimi_client is None:
                self._kimi_client = KimiClient()

            prompt = f"""请提取以下文档中与「{request.ticker}」相关的关键投资信息：

1. 核心业务影响
2. 财务数据变化
3. 风险因素
4. 机遇与挑战

请用要点形式总结，不超过500字。"""

            response = await self._kimi_client.call(
                prompt=prompt,
                max_tokens=800,
            )

            return response.content if response.success else "长文分析失败"

        except Exception as e:
            logger.error(f"[编排器] Kimi 调用失败: {e}")
            return f"Kimi 分析异常: {str(e)}"

    async def generate_gpu_monte_carlo_code(
        self,
        ticker: str,
        current_price: float,
        volatility: float = 0.25,
        simulations: int = 100000,
    ) -> str:
        """
        利用 GLM-5 编写针对 RTX 5080 的优化版蒙特卡洛 Python 代码

        特点：
        - 利用 CuPy 进行 GPU 加速
        - 多进程并行
        - 优化的随机数生成
        """
        prompt = f"""你是 GLM-5，专业的量化工程师。请编写针对 NVIDIA RTX 5080 优化的蒙特卡洛模拟代码。

【参数】
- 标的: {ticker}
- 当前价格: {current_price}
- 波动率: {volatility}
- 模拟次数: {simulations}

【要求】
1. 优先使用 CuPy（CUDA），降级到 NumPy
2. 使用 GPU 并行计算
3. 计算 VaR 和 Expected Shortfall
4. 返回三档估值（悲观/中性/乐观）
5. 代码要简洁、高效、无错误

请只输出 Python 代码，不要解释。"""

        try:
            response = await self._glm5_client.call(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.3,  # 代码生成用低温度
            )

            if response.success:
                return response.content
            else:
                return self._get_default_monte_carlo_code(ticker, current_price)

        except Exception as e:
            logger.error(f"[编排器] GPU 代码生成失败: {e}")
            return self._get_default_monte_carlo_code(ticker, current_price)

    def _get_default_monte_carlo_code(self, ticker: str, current_price: float) -> str:
        """获取默认蒙特卡洛代码模板"""
        return f'''# RTX 5080 优化蒙特卡洛模拟
import numpy as np

def monte_carlo_simulation(ticker="{ticker}", current_price={current_price}, n_sims=100000):
    """GPU 降级版蒙特卡洛模拟"""
    np.random.seed(42)

    # 参数
    volatility = 0.25
    drift = 0.05
    dt = 1/252

    # 并行模拟
    random_returns = np.random.normal(drift * dt, volatility * np.sqrt(dt), n_sims)
    final_prices = current_price * np.exp(random_returns * 252)

    # 计算统计量
    var_95 = np.percentile(final_prices, 5)
    var_99 = np.percentile(final_prices, 1)
    es_95 = final_prices[final_prices <= var_95].mean()

    return {{
        "ticker": ticker,
        "current_price": current_price,
        "mean_price": final_prices.mean(),
        "var_95": var_95,
        "var_99": var_99,
        "expected_shortfall": es_95,
    }}

result = monte_carlo_simulation()
print(result)
'''

    def _parse_glm5_response(self, request: AnalysisRequest, content: str) -> AnalysisResult:
        """解析 GLM-5 响应"""
        # 默认值
        score = 5.0
        sentiment = "neutral"
        summary = content[:200] if content else "分析完成"
        exit_plan = None

        # 简单解析
        content_lower = content.lower()

        # 评分提取
        import re

        score_match = re.search(r"评分[：:]\s*(\d+(?:\.\d+)?)", content)
        if score_match:
            score = float(score_match.group(1))

        # 情绪判断
        if "positive" in content_lower or "正面" in content_lower or "利好" in content_lower:
            sentiment = "positive"
        elif "negative" in content_lower or "负面" in content_lower or "利空" in content_lower:
            sentiment = "negative"

        # 退出计划提取
        target_match = re.search(r"目标价[：:]\s*(\d+(?:\.\d+)?)", content)
        stop_match = re.search(r"止损价[：:]\s*(\d+(?:\.\d+)?)", content)

        if target_match or stop_match:
            exit_plan = {
                "take_profit": float(target_match.group(1)) if target_match else None,
                "stop_loss": float(stop_match.group(1)) if stop_match else None,
            }

        return AnalysisResult(
            ticker=request.ticker,
            summary=summary,
            score=score,
            sentiment=sentiment,
            exit_plan=exit_plan,
            reasoning=content,
            model_used="glm-5",
        )

    def _get_fallback_result(self, request: AnalysisRequest, error: str) -> AnalysisResult:
        """获取失败时的默认结果"""
        return AnalysisResult(
            ticker=request.ticker,
            summary=f"分析失败: {error[:100]}",
            score=0.0,
            sentiment="neutral",
            reasoning=error,
            model_used="fallback",
        )

    def _update_stats(self, latency_ms: float) -> None:
        """更新统计信息"""
        total = self._stats["total_requests"]
        old_avg = self._stats["avg_latency_ms"]
        self._stats["avg_latency_ms"] = (old_avg * (total - 1) + latency_ms) / total

    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return self._stats.copy()


# =============================================================================
# 全局单例（向后兼容）
# =============================================================================

_orchestrator: Optional[GLM5Orchestrator] = None


def get_orchestrator() -> GLM5Orchestrator:
    """获取全局编排器实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = GLM5Orchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    """重置编排器（用于测试）"""
    global _orchestrator
    _orchestrator = None
