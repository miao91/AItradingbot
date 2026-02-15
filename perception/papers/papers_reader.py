"""
AI TradeBot - 本地报刊阅读引擎

解析 D:\报刊订阅\{YYYYMMDD} 目录下的英文原版报纸（WSJ/FT等）
调用 Kimi-128k 进行情报脱水，提取宏观参数
"""
import os
import asyncio
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import aiofiles

from shared.logging import get_logger
from shared.llm.clients import KimiClient, get_kimi_client

logger = get_logger(__name__)


# =============================================================================
# 配置
# =============================================================================

PAPERS_READER_CONFIG = {
    "local_papers_path": os.getenv("LOCAL_PAPERS_PATH", "D:\\报刊订阅"),
    "supported_formats": [".pdf", ".txt", ".html", ".htm"],
    "max_content_length": 50000,  # 字符数限制
    "supported_sources": ["WSJ", "FT", "Bloomberg", "Reuters", "Economist"],
}


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class PaperMetadata:
    """报刊元数据"""
    file_path: str
    file_name: str
    file_size: int
    source: str  # WSJ, FT, etc.
    date: str  # YYYYMMDD format
    file_type: str  # pdf, txt, html


@dataclass
class ExtractedMacroParam:
    """提取的宏观参数"""
    param_name: str
    value: str
    source: str
    confidence: float  # 0-1
    reasoning: str


@dataclass
class PaperAnalysisResult:
    """报刊分析结果"""
    metadata: PaperMetadata
    raw_content: str
    summary: str  # Kimi 提取的摘要
    extracted_params: List[ExtractedMacroParam]
    macro_viewpoints: List[str]  # 核心宏观观点
    affected_tickers: List[str]  # 影响的标的
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# 报刊阅读引擎
# =============================================================================

class PapersReader:
    """
    本地报刊阅读引擎

    扫描本地报刊目录，调用 Kimi-128k 进行深度分析
    """

    def __init__(self, config: Optional[Dict] = None):
        """初始化引擎"""
        self.config = config or PAPERS_READER_CONFIG
        self.papers_path = Path(self.config["local_papers_path"])
        self.kimi_client: Optional[KimiClient] = None

        # 确保目录存在
        self.papers_path.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"[报刊引擎] 初始化完成: "
            f"路径={self.papers_path}, "
            f"支持格式={self.config['supported_formats']}"
        )

    async def scan_today_papers(self) -> List[PaperMetadata]:
        """
        扫描今日报刊

        Returns:
            List[PaperMetadata] 报刊元数据列表
        """
        today_str = datetime.now().strftime("%Y%m%d")
        today_path = self.papers_path / today_str

        if not today_path.exists():
            logger.warning(f"[报刊引擎] 今日目录不存在: {today_path}")
            return []

        papers = []

        for file_path in today_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.config["supported_formats"]:
                metadata = self._parse_metadata(file_path)
                if metadata:
                    papers.append(metadata)

        logger.info(f"[报刊引擎] 扫描到 {len(papers)} 份报刊")
        return papers

    def _parse_metadata(self, file_path: Path) -> Optional[PaperMetadata]:
        """解析文件元数据"""
        try:
            file_name = file_path.name
            file_size = file_path.stat().st_size

            # 尝试识别来源
            source = "Unknown"
            for s in self.config["supported_sources"]:
                if s.upper() in file_name.upper():
                    source = s
                    break

            # 从目录名获取日期
            date = file_path.parent.name

            return PaperMetadata(
                file_path=str(file_path),
                file_name=file_name,
                file_size=file_size,
                source=source,
                date=date,
                file_type=file_path.suffix.lower().replace(".", "")
            )
        except Exception as e:
            logger.error(f"[报刊引擎] 解析元数据失败: {e}")
            return None

    async def read_paper_content(self, metadata: PaperMetadata) -> str:
        """
        读取报刊内容

        Args:
            metadata: 报刊元数据

        Returns:
            str 文件内容
        """
        file_path = Path(metadata.file_path)

        if not file_path.exists():
            logger.error(f"[报刊引擎] 文件不存在: {file_path}")
            return ""

        try:
            if metadata.file_type == "txt":
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                return content[:self.config["max_content_length"]]

            elif metadata.file_type == "html":
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    html_content = await f.read()

                # 简单的 HTML 清理
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                text = soup.get_text(separator=' ', strip=True)
                return text[:self.config["max_content_length"]]

            elif metadata.file_type == "pdf":
                # PDF 解析需要额外库
                return await self._read_pdf_content(file_path)

            else:
                logger.warning(f"[报刊引擎] 不支持的文件类型: {metadata.file_type}")
                return ""

        except Exception as e:
            logger.error(f"[报刊引擎] 读取文件失败: {e}")
            return ""

    async def _read_pdf_content(self, file_path: Path) -> str:
        """读取 PDF 内容"""
        try:
            import PyPDF2

            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()

            import io
            pdf_file = io.BytesIO(content)
            reader = PyPDF2.PdfReader(pdf_file)

            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"

            return text[:self.config["max_content_length"]]

        except ImportError:
            logger.error("[报刊引擎] PyPDF2 未安装，无法读取 PDF")
            return ""
        except Exception as e:
            logger.error(f"[报刊引擎] PDF 读取失败: {e}")
            return ""

    async def analyze_paper(self, metadata: PaperMetadata) -> Optional[PaperAnalysisResult]:
        """
        分析报刊内容

        Args:
            metadata: 报刊元数据

        Returns:
            PaperAnalysisResult 分析结果
        """
        if not self.kimi_client:
            self.kimi_client = await get_kimi_client()

        # 读取内容
        raw_content = await self.read_paper_content(metadata)

        if not raw_content or len(raw_content) < 100:
            logger.warning(f"[报刊引擎] 内容为空或过短: {metadata.file_name}")
            return None

        logger.info(
            f"[报刊引擎] 开始分析: {metadata.file_name} "
            f"({len(raw_content)} 字符)"
        )

        # 调用 Kimi 进行分析
        prompt = self._build_analysis_prompt(metadata, raw_content)

        try:
            response = await self.kimi_client.call(
                prompt=prompt,
                max_tokens=8000,
                temperature=0.3
            )

            # 解析结果
            result = self._parse_analysis_result(metadata, raw_content, response)

            logger.info(
                f"[报刊引擎] 分析完成: "
                f"提取参数={len(result.extracted_params)}, "
                f"宏观观点={len(result.macro_viewpoints)}"
            )

            return result

        except Exception as e:
            logger.error(f"[报刊引擎] 分析失败: {e}")
            return None

    def _build_analysis_prompt(self, metadata: PaperMetadata, content: str) -> str:
        """构建分析提示词"""
        return f"""你是 AI TradeBot 的全球情报分析专家。

请仔细阅读以下来自 {metadata.source} 的报刊内容，并提取关键宏观参数：

【来源】{metadata.source}
【日期】{metadata.date}
【文件名】{metadata.file_name}

【内容】
{content[:30000]}

请按以下 JSON 格式返回分析结果：
{{
    "summary": "整体摘要（3-5句话，概括核心宏观观点）",
    "extracted_params": [
        {{
            "param_name": "参数名称（如：Fed利率预期、通胀目标、GDP增长预期等）",
            "value": "参数值",
            "source": "提及的具体来源或报告",
            "confidence": 0.9,
            "reasoning": "为什么这个参数重要"
        }}
    ],
    "macro_viewpoints": [
        "核心宏观观点1",
        "核心宏观观点2",
        "核心宏观观点3"
    ],
    "affected_tickers": [
        "受影响的主要股票代码或板块（如：600000.SH, 银行板块, 科技板块等）"
    ]
}}

请严格按 JSON 格式返回，不要添加其他内容："""

    def _parse_analysis_result(
        self,
        metadata: PaperMetadata,
        raw_content: str,
        response
    ) -> PaperAnalysisResult:
        """解析分析结果"""
        import json

        # 处理 LLMResponse 对象
        response_text = response.content if hasattr(response, 'content') else str(response)

        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response_text)

            # 解析参数
            extracted_params = []
            for param in data.get("extracted_params", []):
                extracted_params.append(ExtractedMacroParam(
                    param_name=param.get("param_name", ""),
                    value=param.get("value", ""),
                    source=param.get("source", ""),
                    confidence=float(param.get("confidence", 0.5)),
                    reasoning=param.get("reasoning", "")
                ))

            return PaperAnalysisResult(
                metadata=metadata,
                raw_content=raw_content,
                summary=data.get("summary", response_text[:500]),
                extracted_params=extracted_params,
                macro_viewpoints=data.get("macro_viewpoints", []),
                affected_tickers=data.get("affected_tickers", [])
            )

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"[报刊引擎] 解析结果失败: {e}")
            # 返回原始响应作为摘要
            return PaperAnalysisResult(
                metadata=metadata,
                raw_content=raw_content,
                summary=response_text[:1000],
                extracted_params=[],
                macro_viewpoints=[],
                affected_tickers=[]
            )

    async def analyze_today_papers(self) -> List[PaperAnalysisResult]:
        """
        分析今日所有报刊

        Returns:
            List[PaperAnalysisResult] 分析结果列表
        """
        papers = await self.scan_today_papers()

        if not papers:
            logger.info("[报刊引擎] 今日无报刊需要分析")
            return []

        results = []

        for paper in papers:
            try:
                result = await self.analyze_paper(paper)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"[报刊引擎] 分析 {paper.file_name} 失败: {e}")

        logger.info(f"[报刊引擎] 今日报刊分析完成: {len(results)}/{len(papers)}")
        return results


# =============================================================================
# 全局单例
# =============================================================================

_papers_reader: Optional[PapersReader] = None


def get_papers_reader() -> PapersReader:
    """获取全局报刊阅读器实例"""
    global _papers_reader
    if _papers_reader is None:
        _papers_reader = PapersReader()
    return _papers_reader


# =============================================================================
# 便捷函数
# =============================================================================

async def parse_today_papers() -> List[PaperAnalysisResult]:
    """解析今日报刊"""
    reader = get_papers_reader()
    return await reader.analyze_today_papers()


# =============================================================================
# 主程序（用于测试）
# =============================================================================

async def main():
    """主程序（用于测试）"""
    reader = get_papers_reader()

    # 扫描今日报刊
    papers = await reader.scan_today_papers()

    print(f"发现 {len(papers)} 份报刊:")
    for paper in papers:
        print(f"  - {paper.file_name} ({paper.source})")

    # 分析第一份
    if papers:
        result = await reader.analyze_paper(papers[0])
        if result:
            print(f"\n摘要: {result.summary}")
            print(f"提取参数: {len(result.extracted_params)}")
            print(f"宏观观点: {len(result.macro_viewpoints)}")


if __name__ == "__main__":
    asyncio.run(main())
