"""
AI TradeBot - OpenClaw 内容清洗器

功能：
1. 将 HTML 转换为结构化的 Markdown
2. 提取关键信息（标题、正文、表格等）
3. 清理广告、导航栏等无关内容
4. 为后续喂给 Kimi 减少 Token 消耗
"""
import re
from typing import Optional, List, Dict, Any
from html.parser import HTMLParser
from datetime import datetime

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 数据模型
# =============================================================================

class CleanedContent(BaseModel):
    """清洗后的内容"""
    url: Optional[str] = None
    title: str = ""
    markdown: str = ""
    metadata: Dict[str, Any] = {}
    word_count: int = 0
    char_count: int = 0
    processing_time: float = 0  # 处理耗时（秒）


# =============================================================================
# 配置
# =============================================================================

class FormatterConfig:
    """清洗器配置"""

    # 需要移除的标签
    REMOVE_TAGS = [
        "script", "style", "noscript", "iframe",
        "header", "footer", "nav", "aside",
        "form", "input", "button", "select",
        "svg", "path", "use",
    ]

    # 需要移除的类名/ID模式（广告、导航等）
    REMOVE_PATTERNS = [
        r"advertisement", r"ad-", r"_ad", r"banner",
        r"sidebar", r"footer", r"header",
        r"navigation", r"nav-", r"navbar",
        r"social", r"share", r"follow",
        r"comment", r"comments-",
        r"cookie", r"popup", r"modal",
        r"related", r"recommended",
    ]

    # 需要保留的标签（转换后保留结构）
    KEEP_STRUCTURE_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "span", "ul", "ol", "li"]

    # 表格处理
    TABLE_CONVERT = True

    # 代码块处理
    CODE_BLOCK_CONVERT = True

    # 最大文本长度（超过则截断）
    MAX_LENGTH = 50000


# =============================================================================
# HTML 转 Markdown 转换器
# =============================================================================

class HTMLToMarkdownConverter:
    """
    HTML 到 Markdown 转换器

    使用 BeautifulSoup 解析 HTML，转换为格式化的 Markdown
    """

    def __init__(self, config: Optional[FormatterConfig] = None):
        """
        初始化转换器

        Args:
            config: 配置对象
        """
        self.config = config or FormatterConfig()

    def convert(
        self,
        html: str,
        url: Optional[str] = None,
        remove_clutter: bool = True,
    ) -> CleanedContent:
        """
        将 HTML 转换为 Markdown

        Args:
            html: HTML 内容
            url: 来源 URL
            remove_clutter: 是否移除无关内容

        Returns:
            CleanedContent 清洗后的内容
        """
        start_time = datetime.now()

        try:
            # 解析 HTML
            soup = BeautifulSoup(html, 'html.parser')

            # 移除无关标签
            if remove_clutter:
                soup = self._remove_clutter(soup)

            # 提取标题
            title = self._extract_title(soup)

            # 转换为 Markdown
            markdown = self._html_to_markdown(soup)

            # 统计信息
            char_count = len(markdown)
            word_count = len(markdown.split())

            # 处理耗时
            processing_time = (datetime.now() - start_time).total_seconds()

            result = CleanedContent(
                url=url,
                title=title,
                markdown=markdown,
                word_count=word_count,
                char_count=char_count,
                processing_time=processing_time,
                metadata={
                    "source_url": url,
                    "original_length": len(html),
                    "compression_ratio": round(char_count / len(html) * 100, 2) if html else 0,
                }
            )

            logger.info(
                f"HTML converted: {char_count} chars, "
                f"{word_count} words, {processing_time:.3f}s"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to convert HTML to Markdown: {e}")
            return CleanedContent(
                url=url,
                title="",
                markdown="",
                metadata={"error": str(e)},
            )

    def _remove_clutter(self, soup: BeautifulSoup) -> BeautifulSoup:
        """
        移除无关内容

        Args:
            soup: BeautifulSoup 对象

        Returns:
            清理后的 BeautifulSoup 对象
        """
        # 移除指定标签
        for tag_name in self.config.REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 移除匹配模式的元素
        for pattern in self.config.REMOVE_PATTERNS:
            # 检查 class 属性
            for elem in soup.find_all(class_=re.compile(pattern, re.I)):
                elem.decompose()
            # 检查 id 属性
            for elem in soup.find_all(id=re.compile(pattern, re.I)):
                elem.decompose()

        # 移除空元素
        for tag in soup.find_all():
            if not tag.get_text(strip=True) and not tag.find_all():
                tag.decompose()

        return soup

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """
        提取标题

        Args:
            soup: BeautifulSoup 对象

        Returns:
            标题文本
        """
        # 尝试从 h1 标签获取
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        # 尝试从 title 标签获取
        title = soup.find("title")
        if title:
            title_text = title.get_text(strip=True)
            # 清理常见的后缀
            for suffix in ["_东方财富网", " - 东方财富网", " | 新浪财经", "_新浪财经"]:
                title_text = title_text.replace(suffix, "")
            return title_text

        return "Untitled"

    def _html_to_markdown(self, soup: BeautifulSoup) -> str:
        """
        将 HTML 转换为 Markdown

        Args:
            soup: BeautifulSoup 对象

        Returns:
            Markdown 文本
        """
        # 只保留 body 内容
        body = soup.find("body") or soup

        # 递归转换
        markdown_lines = self._convert_element(body)

        # 清理空行
        markdown = "\n".join(
            line for line in markdown_lines
            if line.strip()
        )

        # 截断过长内容
        if len(markdown) > self.config.MAX_LENGTH:
            markdown = markdown[:self.config.MAX_LENGTH] + "\n\n... (内容过长已截断)"

        return markdown

    def _convert_element(self, element: Tag) -> List[str]:
        """
        递归转换 HTML 元素为 Markdown 行

        Args:
            element: BeautifulSoup 元素

        Returns:
            Markdown 行列表
        """
        lines = []

        # 处理文本节点
        if element.name is None:  # 文本节点
            text = str(element).strip()
            if text:
                return [text]
            return []

        # 获取子元素内容
        children_lines = []
        for child in element.children:
            if isinstance(child, Tag):
                children_lines.extend(self._convert_element(child))
            else:
                text = str(child).strip()
                if text:
                    children_lines.append(text)

        children_text = " ".join(children_lines)

        # 根据标签类型转换
        tag = element.name.lower()

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            prefix = "#" * level
            lines.append(f"{prefix} {children_text}")
            lines.append("")  # 标题后空行

        elif tag == "p":
            lines.append(children_text)
            lines.append("")

        elif tag in ("strong", "b"):
            return [f"**{children_text}**"]

        elif tag in ("em", "i"):
            return [f"*{children_text}*"]

        elif tag == "a":
            href = element.get("href", "")
            if href:
                return [f"[{children_text}]({href})"]
            return [children_text]

        elif tag == "br":
            lines.append("")

        elif tag == "hr":
            lines.append("---")
            lines.append("")

        elif tag in ("ul", "ol"):
            lines.extend(children_lines)
            lines.append("")

        elif tag == "li":
            # 检查是否在有序列表中
            parent = element.parent
            is_ordered = parent and parent.name == "ol"
            prefix = "1." if is_ordered else "-"
            lines.append(f"{prefix} {children_text}")

        elif tag == "code":
            return [f"`{children_text}`"]

        elif tag == "pre":
            # 代码块
            lines.append("```")
            lines.append(children_text)
            lines.append("```")
            lines.append("")

        elif tag == "blockquote":
            for line in children_text.split("\n"):
                lines.append(f"> {line}")
            lines.append("")

        elif tag == "table" and self.config.TABLE_CONVERT:
            lines.extend(self._convert_table(element))

        elif tag in ("div", "span", "section", "article"):
            # 容器标签，直接添加子内容
            lines.extend(children_lines)

        else:
            # 其他标签，添加子内容
            lines.extend(children_lines)

        return lines

    def _convert_table(self, table: Tag) -> List[str]:
        """
        转换表格为 Markdown

        Args:
            table: 表格元素

        Returns:
            Markdown 行列表
        """
        rows = table.find_all("tr")
        if not rows:
            return []

        lines = []

        # 表头
        header = rows[0]
        headers = [th.get_text(strip=True) for th in header.find_all(["th", "td"])]
        if headers:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join([" --- " for _ in headers]) + "|")

        # 表体
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if cells:
                lines.append("| " + " | ".join(cells) + " |")

        lines.append("")
        return lines


# =============================================================================
# Jina Reader 集成（简化版）
# =============================================================================

class JinaReaderStyleFormatter:
    """
    Jina Reader 风格的格式化器

    生成类似 Jina Reader (r.jina.ai) 的简洁输出
    """

    def __init__(self):
        self.converter = HTMLToMarkdownConverter()

    def format(
        self,
        html: str,
        url: Optional[str] = None,
    ) -> CleanedContent:
        """
        格式化 HTML 内容

        Args:
            html: HTML 内容
            url: 来源 URL

        Returns:
            CleanedContent
        """
        result = self.converter.convert(html, url=url)

        # 额外的 Jina 风格处理
        # 1. 移除多余的空行
        markdown = re.sub(r"\n{3,}", "\n\n", result.markdown)

        # 2. 标准化空格
        markdown = re.sub(r" +", " ", markdown)

        # 3. 移除行首行尾空格
        lines = [line.strip() for line in markdown.split("\n")]
        markdown = "\n".join(lines)

        result.markdown = markdown
        result.metadata["style"] = "jina_reader"

        return result


# =============================================================================
# 便捷函数
# =============================================================================

def html_to_markdown(
    html: str,
    url: Optional[str] = None,
    style: str = "default",
) -> CleanedContent:
    """
    将 HTML 转换为 Markdown 的便捷函数

    Args:
        html: HTML 内容
        url: 来源 URL
        style: 转换风格 (default/jina)

    Returns:
        CleanedContent
    """
    if style == "jina":
        formatter = JinaReaderStyleFormatter()
        return formatter.format(html, url=url)
    else:
        formatter = HTMLToMarkdownConverter()
        return formatter.convert(html, url=url)


def clean_html(
    html: str,
    remove_clutter: bool = True,
) -> str:
    """
    清理 HTML 的便捷函数

    Args:
        html: HTML 内容
        remove_clutter: 是否移除无关内容

    Returns:
        清理后的 Markdown 文本
    """
    result = html_to_markdown(html, remove_clutter=remove_clutter)
    return result.markdown


def extract_text(
    html: str,
    max_length: int = 1000,
) -> str:
    """
    提取纯文本摘要

    Args:
        html: HTML 内容
        max_length: 最大长度

    Returns:
        文本摘要
    """
    soup = BeautifulSoup(html, 'html.parser')

    # 移除脚本和样式
    for script in soup(["script", "style"]):
        script.decompose()

    # 获取文本
    text = soup.get_text()

    # 清理空格
    text = re.sub(r"\s+", " ", text).strip()

    # 截断
    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text
