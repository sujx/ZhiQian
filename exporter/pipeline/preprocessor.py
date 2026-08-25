"""HTMLPreprocessor：清洗、规范化 HTML，为转换做准备"""

from __future__ import annotations

import logging
from typing import Dict

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# 转换后允许保留的 HTML 属性
_KEEP_ATTRS = {"href", "src", "alt", "title", "data-lang"}


class HTMLPreprocessor:
    """HTML 预处理：提取 body、清理属性、标记代码块语言、补全表格结构"""

    def process(self, html: str) -> BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("body") or soup

        # 1. 代码块：先提取语言标记存到 data-lang 属性
        #    （须在属性清理前，否则 code 的 class 会被删除）
        for pre in body.find_all("pre"):
            code = pre.find("code")
            if code is not None:
                lang = self._extract_language(code)
                if lang:
                    pre["data-lang"] = lang

        # 2. 清理冗余属性（保留链接/图片/标题/语言标记属性）
        for tag in body.find_all(True):
            for attr in list(tag.attrs):
                if attr not in _KEEP_ATTRS:
                    del tag[attr]

        # 3. 表格补 thead（html2text 依赖表头结构）
        for table in body.find_all("table"):
            if table.find("thead") is None:
                first_row = table.find("tr")
                if first_row is not None:
                    thead = soup.new_tag("thead")
                    first_row.wrap(thead)

        # 4. 删除空标签（span/div/p 无内容时清理）
        for tag in body.find_all(["span", "div", "p"]):
            if not tag.get_text(strip=True) and not tag.find_all(["img", "br"]):
                tag.decompose()

        return body

    @staticmethod
    def _extract_language(code: Tag) -> str:
        """从 code 标签 class 中提取语言名（language-xxx 或 xxx）"""
        for cls in code.get("class") or []:
            if cls.startswith("language-"):
                return cls[len("language-"):]
            if cls.startswith("lang-"):
                return cls[len("lang-"):]
        return ""
