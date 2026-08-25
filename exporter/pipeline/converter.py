"""MarkdownConverter：HTML → Markdown 转换 + 后处理 + YAML frontmatter"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List, Optional

import html2text
from bs4 import BeautifulSoup

from exporter.models import WizDocument

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^\s*(```|~~~)")


class MarkdownConverter:
    """基于 html2text 的转换器，带空行/列表标记/frontmatter 后处理"""

    def __init__(self) -> None:
        self.h2t = html2text.HTML2Text()
        self.h2t.body_width = 0           # 不自动换行
        self.h2t.unicode_snob = True
        self.h2t.protect_links = True
        self.h2t.inline_links = True
        self.h2t.single_line_break = True
        self.h2t.backquote_code_style = True   # 代码块输出 ``` 围栏并保留换行
        self.h2t.ignore_links = False

    def convert(self, soup: BeautifulSoup, doc: WizDocument,
                add_frontmatter: bool = True) -> str:
        """转换 body 为 Markdown 文本"""
        # 收集代码块语言（按出现顺序）
        langs = [pre.get("data-lang", "")
                 for pre in soup.find_all("pre") if pre.get("data-lang")]
        md = self.h2t.handle(str(soup))
        md = self._postprocess(md)
        md = self._inject_languages(md, langs)
        if add_frontmatter:
            md = self._add_frontmatter(md, doc)
        return md

    # ---------- 后处理 ----------

    def _postprocess(self, text: str) -> str:
        if not text:
            return ""
        text = self._normalize_blank_lines(text)
        text = self._unescape_list_markers(text)
        text = self._clean_markdown_noise(text)
        # 修复代码块周围空行
        text = re.sub(r"```\n\n", "```\n", text)
        text = re.sub(r"\n\n```", "\n```", text)
        # 行尾去空格 + 末尾换行
        lines = [line.rstrip() for line in text.split("\n")]
        result = "\n".join(lines).rstrip() + "\n"
        return result

    def _clean_markdown_noise(self, text: str) -> str:
        """清理 html2text 产生的 Markdown 噪音（代码块内不处理）

        覆盖: 空链接 [](<>)、空图片 ![]()、相邻加粗星号错位 **A****B**、
        标题前悬挂空链接、多余星号。
        """
        out: list[str] = []
        in_fence = False
        for line in text.splitlines():
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                out.append(line)
                continue
            if in_fence:
                out.append(line)
                continue
            line = self._clean_line(line)
            out.append(line)
        return "\n".join(out)

    @staticmethod
    def _clean_line(line: str) -> str:
        """单行噪音清理（仅正文，不涉及代码块）"""
        # 空图片: ![]() / ![alt]() 且无资源 → 删除
        line = re.sub(r"!\[[^\]]*\]\(\)", "", line)
        # 空链接: [](<>) / [](< >) / []()（链接文本为空的悬挂链接）
        line = re.sub(r"\[\]\(\s*<>\s*\)", "", line)
        line = re.sub(r"\[\]\(\)", "", line)
        # 相邻加粗错位: **A****B** → **A**B**（4+ 星号归一为 2 个）
        line = re.sub(r"\*{4,}", "**", line)
        # 3 个星号（奇数残留）→ 1 个
        line = re.sub(r"\*{3}", "*", line)
        # 行首残留逗号/空格（空链接删除后的残留）
        line = re.sub(r"^[，,\s]+", "", line)
        return line

    def _normalize_blank_lines(self, text: str) -> str:
        """压缩连续空行为单个，代码块内原样保留"""
        out: list[str] = []
        blank = 0
        in_fence = False
        for line in text.splitlines():
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                out.append(line)
                blank = 0
                continue
            if in_fence:
                out.append(line)
                continue
            if line.strip() == "":
                blank += 1
                if blank <= 1:
                    out.append("")
                continue
            blank = 0
            out.append(line)
        return "\n".join(out)

    def _unescape_list_markers(self, text: str) -> str:
        """恢复 html2text 转义的列表符号 \\-、\\1. 和分割线 \\***"""
        dash_re = re.compile(r"^(\s*)\\-\s+")            # 匹配字面 "\- " → "- "
        ol_re = re.compile(r"^(\s*)(\d+)\\\.\s+")        # 匹配字面 "1\. " → "1. "
        hr_re = re.compile(r"^\s*\\([*_\-]{3,})\s*$")
        out: list[str] = []
        in_fence = False
        for line in text.splitlines():
            if _FENCE_RE.match(line):
                in_fence = not in_fence
                out.append(line)
                continue
            if in_fence:
                out.append(line)
                continue
            line = dash_re.sub(r"\1- ", line)
            line = ol_re.sub(r"\1\2. ", line)
            if hr_re.match(line):
                line = line.replace("\\", "")
            out.append(line)
        return "\n".join(out)

    def _inject_languages(self, text: str, langs: List[str]) -> str:
        """按序把语言注入到 ``` 围栏行

        约定：html2text 的 backquote_code_style 输出围栏为独立行 ```，
        且 pre 内代码不包含独立 ``` 行（html2text 已知限制）。
        """
        if not langs:
            return text
        iterator = iter(langs)
        out: list[str] = []
        for line in text.splitlines():
            if line.strip() == "```" and not line.startswith(" "):
                lang = next(iterator, "")
                out.append(f"```{lang}" if lang else line)
            else:
                out.append(line)
        return "\n".join(out)

    # ---------- frontmatter ----------

    def _add_frontmatter(self, md: str, doc: WizDocument) -> str:
        if md.startswith("---\n"):
            return md
        lines = ["---"]
        title = (doc.title or "无标题").replace('"', "'")
        lines.append(f'title: "{title}"')
        if doc.created:
            lines.append(f"created: {self._fmt(doc.created)}")
        if doc.modified:
            lines.append(f"modified: {self._fmt(doc.modified)}")
        if doc.tags:
            tags = ", ".join(doc.tags)
            lines.append(f"tags: [{tags}]")
        lines.append(f'location: "{doc.location}"')
        lines.append("---")
        lines.append("")
        return "\n".join(lines) + md

    @staticmethod
    def _fmt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
