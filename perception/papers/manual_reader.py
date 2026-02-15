"""
AI TradeBot - 本地报刊手动解析引擎

从英文报刊中提取宏观参数和估值相关信息
"""
import os
import re
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

MANUAL_READER_CONFIG = {
    # 报纸存储目录
    "papers_dir": "D:\\报刊订阅",

    # 支持的报纸
    "supported_papers": [
        "wallstreet_journal.txt",
        "financial_times.txt",
        "economist.txt",
        "bbc.txt",
        "reuters.txt",
    ],

    # 解析模式
    "parse_mode": "date",  # date: 自动定位当日, manual: 手动指定日期
    "target_date": None,  # 手动指定的日期 YYYY-MM-DD

    # 提取目标
    "extract_targets": [
        "interest_rate",  # 利率预期
        "gdp_growth",     # GDP 增速预测
        "inflation_rate",  # 通胀率
        "industry_outlook", # 行业展望
        "market_sentiment", # 市场情绪
        "valuation_impact",  # 对估值模型的影响
    ],

    # 硬性过滤
    "english_only": True,  # 仅解析英文原版
    "min_content_length": 500,  # 最小内容长度
}


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class PaperSection:
    """报纸章节"""
    title: str
    content: str
    section_type: str  # macro, market, company, etc.
    relevance_score: float = 0.0  # 相关性评分


@dataclass
class PaperAnalysis:
    """报纸分析结果"""
    date: str
    paper_name: str
    sections: List[PaperSection] = field(default_factory=list)
    extracted_params: Dict[str, Any] = field(default_factory=dict)

    # 提取的宏观参数
    interest_rate: Optional[str] = None  # 利率预期
    gdp_growth: Optional[str] = None  # GDP 增速
    inflation_rate: Optional[str] = None  # 通胀率
    industry_outlook: Optional[str] = None  # 行业展望
    market_sentiment: Optional[str] = None  # 市场情绪

    processing_time_ms: float = 0.0


# =============================================================================
# 报纸解析器
# =============================================================================

class ManualPaperReader:
    """
    本地报刊手动解析引擎

    从英文报刊文件中提取宏观参数和估值相关信息
    """

    def __init__(self, config: Optional[Dict] = None):
        """初始化解析器"""
        self.config = config or MANUAL_READER_CONFIG
        self.papers_dir = Path(self.config["papers_dir"])

    def parse_paper(self, paper_name: str, target_date: Optional[str] = None) -> PaperAnalysis:
        """
        解析单个报纸文件

        Args:
            paper_name: 报纸文件名（如 wall_street_journal.txt）
            target_date: 目标日期（YYYY-MM-DD），默认为今天

        Returns:
            PaperAnalysis 分析结果
        """
        logger.info(f"[报刊解析] 开始解析: {paper_name}")

        start_time = asyncio.get_event_loop().time()

        # 定位报纸文件
        paper_file = self.papers_dir / paper_name

        if not paper_file.exists():
            logger.error(f"[报刊解析] 文件不存在: {paper_file}")
            return self._create_error_result(paper_name, "文件不存在")

        try:
            # 读取文件内容
            with open(paper_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 硬性过滤：检查是否为英文内容
            if not self._is_english_content(content):
                logger.warning(f"[报刊解析] 内容非英文，跳过: {paper_name}")
                return self._create_error_result(paper_name, "非英文内容")

            # 按章节分割（通常报纸有分段标记）
            sections = self._extract_sections(content)

            if not sections:
                logger.warning(f"[报刊解析] 未找到有效章节: {paper_name}")
                return self._create_error_result(paper_name, "未找到有效章节")

            # 提取宏观参数
            extracted_params = self._extract_macro_params(sections)

            # 计算相关性评分
            for section in sections:
                section.relevance_score = self._calculate_relevance(section)

            # 按相关性排序，只保留高相关章节
            top_sections = sorted(sections, key=lambda x: -x.relevance_score)[:5]

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            return PaperAnalysis(
                date=target_date or datetime.now().strftime("%Y-%m-%d"),
                paper_name=paper_name,
                sections=top_sections,
                extracted_params=extracted_params,
                processing_time_ms=duration_ms,
            )

        except Exception as e:
            logger.error(f"[报刊解析] 解析异常: {e}")
            return self._create_error_result(paper_name, str(e))

    def _is_english_content(self, content: str) -> bool:
        """检查是否为英文内容"""
        # 简单检测：检查是否包含足够的英文字符
        english_chars = len(re.findall(r'[a-zA-Z]{3,}', content))
        total_chars = len(content)
        return english_chars / total_chars > 0.3 if total_chars > 0 else False

    def _extract_sections(self, content: str) -> List[PaperSection]:
        """提取报纸章节"""
        sections = []

        # 常见的章节分隔模式
        section_patterns = [
            r'===+\s*([^=]+)\s*===+',  # === 标题 ===
            r'---+\s*([^=]+)\s*---+',  # --- 标题 ---
            r'\n\s*\n\s*\n',  # 空行分段
        ]

        for pattern in section_patterns:
            matches = list(re.finditer(pattern, content))
            for match in matches:
                section_content = match.group(0).strip()

                # 跳过太短的章节
                if len(section_content) < self.config["min_content_length"]:
                    continue

                # 检测章节类型
                section_type = self._identify_section_type(section_content, match.group(1) if len(match.groups()) > 1 else "general")

                sections.append(PaperSection(
                    title=match.group(1) if len(match.groups()) > 1 else "General",
                    content=section_content[:500],  # 限制长度
                    section_type=section_type,
                    relevance_score=0.0,  # 稍后计算
                ))

        return sections

    def _identify_section_type(self, content: str, title: str = "") -> str:
        """识别章节类型"""
        content_lower = content.lower()

        # 宏观经济章节
        if any(keyword in content_lower for keyword in
               ["fed", "interest rate", "inflation", "gdp", "growth",
                "central bank", "economy", "market", "outlook"]):
            return "macro"

        # 公司章节
        if any(keyword in content_lower for keyword in
               ["earnings", "revenue", "profit", "margin", "outlook", "guidance"]):
            return "company"

        # 市场章节
        if any(keyword in content_lower for keyword in
               ["stock", "index", "rally", "decline", "gain", "loss"]):
            return "market"

        return "general"

    def _extract_macro_params(self, sections: List[PaperSection]) -> Dict[str, Any]:
        """提取宏观参数"""
        params = {}

        for section in sections:
            content = section.content.lower()

            # 利率预期
            if "interest rate" in content and "fed" in content:
                match = re.search(r'(\d+\.?\d*)\s*%', content)
                if match:
                    params["interest_rate"] = match.group()

            # GDP 增速
            if "gdp" in content or "growth" in content:
                match = re.search(r'(\d+\.?\d*)\s*%', content)
                if match:
                    params["gdp_growth"] = match.group()

            # 通胀率
            if "inflation" in content:
                match = re.search(r'(\d+\.?\d*)\s*%', content)
                if match:
                    params["inflation_rate"] = match.group()

            # 行业展望
            if "outlook" in content or "forecast" in content:
                if "positive" in content or "growth" in content or "expand" in content:
                    params["industry_outlook"] = "positive"
                elif "slowdown" in content or "weak" in content or "concern" in content:
                    params["industry_outlook"] = "negative"

            # 市场情绪
            if any(word in content for word in ["bullish", "rally", "surge", "optimistic"]):
                params["market_sentiment"] = "bullish"
            elif any(word in content for word in ["bearish", "decline", "concern", "risk"]):
                params["market_sentiment"] = "bearish"

            # 估值影响
            if "valuation" in content or "priced" in content or "premium" in content:
                params["valuation_impact"] = "significant"
            elif "discount" in content or "cheap" in content:
                params["valuation_impact"] = "moderate"

        return params

    def _calculate_relevance(self, section: PaperSection) -> float:
        """计算相关性评分"""
        score = 0.0

        # 基于关键词
        keywords = {
            "fed": 10, "interest": 9, "rate": 8,
            "growth": 9, "inflation": 8, "gdp": 9,
            "outlook": 7, "market": 6, "stock": 8,
            "bullish": 5, "bearish": 5,
        }

        for keyword, value in keywords.items():
            if keyword.lower() in section.title.lower() + " " + section.content.lower():
                score += value

        return min(score / 30.0, 1.0)  # 归一化到 0-1

    def _create_error_result(self, paper_name: str, error_msg: str) -> PaperAnalysis:
        """创建错误结果"""
        return PaperAnalysis(
            date=datetime.now().strftime("%Y-%m-%d"),
            paper_name=paper_name,
            sections=[],
            extracted_params={},
            processing_time_ms=0,
        )

    async def parse_today_papers(self) -> List[PaperAnalysis]:
        """解析今天的所有报纸"""
        results = []

        for paper_name in self.config["supported_papers"]:
            result = await self.parse_paper(paper_name)
            results.append(result)

        return results

    def get_paper_path(self, date: str) -> Path:
        """获取指定日期的报纸文件路径"""
        date_path = self.papers_dir / date
        if not date_path.exists():
            # 尝试查找最近日期的文件
            available_files = sorted(self.papers_dir.glob("*.txt"), reverse=True)
            if available_files:
                return available_files[0]
        return date_path


# =============================================================================
# 全局单例
# =============================================================================

_paper_reader: Optional[ManualPaperReader] = None


def get_paper_reader() -> ManualPaperReader:
    """获取全局报刊解析器实例"""
    global _paper_reader
    if _paper_reader is None:
        _paper_reader = ManualPaperReader()
    return _paper_reader


# =============================================================================
# 便捷函数
# =============================================================================

async def trigger_manual_analysis(date: Optional[str] = None):
    """
    触发手动报刊解析

    使用 PapersReader 进行 Kimi-128k 深度分析

    Args:
        date: 目标日期 (YYYY-MM-DD)，默认为今天
    """
    # 使用 PapersReader 进行 Kimi 分析
    from perception.papers.papers_reader import get_papers_reader

    reader = get_papers_reader()

    if date:
        logger.info(f"[报刊解析] 手动解析 {date} 的报刊...")
    else:
        logger.info("[报刊解析] 自动解析今日报刊...")

    # 调用 PapersReader 进行分析（使用 Kimi-128k）
    results = await reader.analyze_today_papers()

    if not results:
        logger.warning("[报刊解析] 未找到任何报刊文件或解析失败")
        return []

    logger.info(f"[报刊解析] 解析完成，共 {len(results)} 份报刊")

    # 转换结果格式以兼容 showcase API
    converted_results = []
    for result in results:
        # 将 ExtractedMacroParam 列表转换为字典
        extracted_params_dict = {}
        for param in result.extracted_params:
            extracted_params_dict[param.param_name] = param.value

        converted_results.append(PaperAnalysis(
            date=result.metadata.date,
            paper_name=result.metadata.file_name,
            sections=[],
            extracted_params=extracted_params_dict,
            processing_time_ms=0,
        ))

        # 打印提取的参数
        if result.extracted_params:
            params_str = ", ".join([f"{p.param_name}: {p.value}" for p in result.extracted_params[:3]])
            logger.info(f"[报刊解析] {result.metadata.file_name}: {params_str}...")

    return converted_results
