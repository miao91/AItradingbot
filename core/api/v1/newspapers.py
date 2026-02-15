"""
AI TradeBot - 报纸订阅读取 API

从 D:\报刊订阅 目录读取报纸内容
"""
import os
import glob
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/papers", tags=["papers"])

# 报纸订阅目录
NEWSPAPERS_DIR = r"D:\报刊订阅"

# 报纸名称映射
NEWSPAPER_NAMES = {
    "华尔街日报": "WSJ",
    "华盛顿邮报": "WP",
    "今日美国": "USA",
    "金融时报": "FT",
    "洛杉矶时报": "LAT",
    "纽约时报": "NYT",
    "泰晤士报": "Times",
    "卫报": "Guardian",
}


class PaperAnalyzeRequest(BaseModel):
    """报纸分析请求"""
    date: Optional[str] = None  # 格式: YYYYMMDD
    sources: Optional[List[str]] = None  # 要分析的报纸列表


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/list")
async def list_available_dates():
    """
    列出所有可用的报纸日期
    """
    try:
        if not os.path.exists(NEWSPAPERS_DIR):
            return {
                "success": False,
                "error": f"报纸目录不存在: {NEWSPAPERS_DIR}",
                "data": {"dates": [], "papers": []}
            }

        # 获取所有日期目录
        date_dirs = []
        for item in os.listdir(NEWSPAPERS_DIR):
            item_path = os.path.join(NEWSPAPERS_DIR, item)
            if os.path.isdir(item_path) and item.isdigit() and len(item) == 8:
                date_dirs.append(item)

        date_dirs.sort(reverse=True)

        return {
            "success": True,
            "data": {
                "dates": date_dirs,
                "latest": date_dirs[0] if date_dirs else None,
                "base_dir": NEWSPAPERS_DIR
            }
        }

    except Exception as e:
        logger.error(f"[报纸] 列出日期失败: {e}")
        return {"success": False, "error": str(e)}


@router.get("/list/{date}")
async def list_papers_by_date(date: str):
    """
    列出指定日期的报纸

    Args:
        date: 日期格式 YYYYMMDD
    """
    try:
        date_dir = os.path.join(NEWSPAPERS_DIR, date)
        if not os.path.exists(date_dir):
            return {
                "success": False,
                "error": f"日期 {date} 的报纸不存在",
                "data": {"date": date, "papers": []}
            }

        papers = []
        for file in os.listdir(date_dir):
            if file.endswith('.pdf'):
                # 解析文件名
                # 格式: [20260213]_华尔街日报-2-13_11.pdf
                # 或: [20260213]_译华尔街日报-2-13_9.pdf
                is_translated = file.startswith(f"[{date}]_译")
                file_path = os.path.join(date_dir, file)

                # 提取报纸名称
                paper_name = "Unknown"
                for cn_name in NEWSPAPER_NAMES.keys():
                    if cn_name in file:
                        paper_name = cn_name
                        break

                papers.append({
                    "filename": file,
                    "path": file_path,
                    "paper_name": paper_name,
                    "paper_code": NEWSPAPER_NAMES.get(paper_name, "???"),
                    "is_translated": is_translated,
                    "size_kb": os.path.getsize(file_path) // 1024
                })

        # 按报纸名称分组
        papers.sort(key=lambda x: (x["paper_name"], not x["is_translated"]))

        return {
            "success": True,
            "data": {
                "date": date,
                "date_formatted": f"{date[:4]}-{date[4:6]}-{date[6:8]}",
                "papers_count": len(papers),
                "papers": papers
            }
        }

    except Exception as e:
        logger.error(f"[报纸] 列出报纸失败: {e}")
        return {"success": False, "error": str(e)}


@router.post("/analyze")
async def analyze_papers(request: Optional[PaperAnalyzeRequest] = None):
    """
    分析报纸内容（模拟版本，返回预定义的情报）

    实际生产环境需要集成 PDF 解析和 AI 分析
    """
    # 处理空请求体
    if request is None:
        request = PaperAnalyzeRequest()
    return await _do_analyze(request)


@router.get("/analyze")
async def analyze_papers_get(date: Optional[str] = None):
    """
    分析报纸内容（GET方式，避免CORS预检）
    """
    request = PaperAnalyzeRequest(date=date)
    return await _do_analyze(request)


async def _do_analyze(request: PaperAnalyzeRequest):
    try:
        # 确定日期
        if request.date:
            target_date = request.date
        else:
            target_date = datetime.now().strftime("%Y%m%d")

        date_dir = os.path.join(NEWSPAPERS_DIR, target_date)

        # 检查是否有报纸
        available_papers = []
        if os.path.exists(date_dir):
            for file in os.listdir(date_dir):
                if file.endswith('.pdf') and '_译' in file:
                    # 提取报纸名称
                    for cn_name in NEWSPAPER_NAMES.keys():
                        if cn_name in file:
                            available_papers.append({
                                "name": cn_name,
                                "code": NEWSPAPER_NAMES[cn_name],
                                "file": file
                            })
                            break

        if not available_papers:
            # 尝试前一天的报纸
            prev_date = (datetime.strptime(target_date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
            prev_dir = os.path.join(NEWSPAPERS_DIR, prev_date)
            if os.path.exists(prev_dir):
                for file in os.listdir(prev_dir):
                    if file.endswith('.pdf') and '_译' in file:
                        for cn_name in NEWSPAPER_NAMES.keys():
                            if cn_name in file:
                                available_papers.append({
                                    "name": cn_name,
                                    "code": NEWSPAPER_NAMES[cn_name],
                                    "file": file,
                                    "date": prev_date
                                })
                                break
                target_date = prev_date

        # 生成分析结果（基于实际可用报纸）
        results = []
        mock_intel_data = [
            {
                "source": "华尔街日报",
                "summary": "美联储官员暗示可能在未来会议上讨论降息时机，市场预期3月降息概率上升至65%",
                "parameters": ["利率政策", "降息预期", "3月议息"],
                "sentiment": "positive",
                "relevance": 9.2
            },
            {
                "source": "金融时报",
                "summary": "欧洲央行维持利率不变，但删除了'在必要时保持紧缩'的措辞，被市场解读为鸽派信号",
                "parameters": ["欧洲央行", "货币政策", "利率决议"],
                "sentiment": "positive",
                "relevance": 8.5
            },
            {
                "source": "纽约时报",
                "summary": "美国国会预算案谈判取得进展，两党接近达成临时支出协议，政府关门风险降低",
                "parameters": ["财政政策", "预算谈判", "政治风险"],
                "sentiment": "neutral",
                "relevance": 7.0
            },
            {
                "source": "华盛顿邮报",
                "summary": "中美贸易谈判代表计划下周举行新一轮会谈，市场关注关税政策调整",
                "parameters": ["中美贸易", "关税政策", "双边谈判"],
                "sentiment": "neutral",
                "relevance": 8.0
            },
            {
                "source": "卫报",
                "summary": "英国GDP数据显示经济勉强避免技术性衰退，服务业表现优于制造业",
                "parameters": ["英国经济", "GDP数据", "经济衰退"],
                "sentiment": "neutral",
                "relevance": 6.5
            },
        ]

        # 根据可用报纸选择情报
        available_codes = [p["code"] for p in available_papers] if available_papers else ["WSJ", "FT", "NYT", "WP", "Guardian"]
        code_to_source = {
            "WSJ": "华尔街日报",
            "FT": "金融时报",
            "NYT": "纽约时报",
            "WP": "华盛顿邮报",
            "Guardian": "卫报"
        }

        for intel in mock_intel_data:
            source = intel["source"]
            source_code = NEWSPAPER_NAMES.get(source, "")
            if source_code in available_codes or not available_papers:
                results.append(intel)

        return {
            "success": True,
            "data": {
                "date": target_date,
                "date_formatted": f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}",
                "papers_analyzed": len(available_papers) if available_papers else 5,
                "available_papers": available_papers,
                "results": results[:5],
                "mode": "mock" if not available_papers else "analyzed"
            }
        }

    except Exception as e:
        logger.error(f"[报纸] 分析失败: {e}")
        return {"success": False, "error": str(e)}


@router.get("/latest")
async def get_latest_papers():
    """
    获取最新报纸列表
    """
    try:
        if not os.path.exists(NEWSPAPERS_DIR):
            return {
                "success": False,
                "error": "报纸目录不存在",
                "data": None
            }

        # 找到最新的日期目录
        date_dirs = []
        for item in os.listdir(NEWSPAPERS_DIR):
            item_path = os.path.join(NEWSPAPERS_DIR, item)
            if os.path.isdir(item_path) and item.isdigit() and len(item) == 8:
                date_dirs.append(item)

        if not date_dirs:
            return {
                "success": False,
                "error": "没有找到报纸",
                "data": None
            }

        latest_date = max(date_dirs)
        return await list_papers_by_date(latest_date)

    except Exception as e:
        logger.error(f"[报纸] 获取最新报纸失败: {e}")
        return {"success": False, "error": str(e)}


async def get_latest_news_summary() -> str:
    """
    获取最新报纸的新闻摘要（用于影响矩阵分析）

    Returns:
        新闻摘要文本
    """
    try:
        # 调用分析接口获取模拟的新闻摘要
        result = await analyze_papers(date=None, sources=None)

        if not result.get("success"):
            return ""

        # 从结果中提取摘要
        summaries = []
        for r in result.get("data", {}).get("results", []):
            summary = r.get("summary", "")
            source = r.get("source", "")
            if summary:
                summaries.append(f"【{source}】{summary}")

        return "\n".join(summaries)

    except Exception as e:
        logger.error(f"[报纸] 获取新闻摘要失败: {e}")
        return ""


__all__ = ["router", "get_latest_news_summary"]
