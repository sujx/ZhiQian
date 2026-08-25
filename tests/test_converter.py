"""MarkdownConverter 单元测试：转换核心 + 后处理 + 噪音清理"""

from __future__ import annotations

from bs4 import BeautifulSoup

from exporter.models import WizDocument
from exporter.pipeline.converter import MarkdownConverter
from exporter.pipeline.preprocessor import HTMLPreprocessor


def _doc(title="测试笔记"):
    return WizDocument(guid="g1", title=title, location="/测试/",
                       tags=["tag1"], created=None, modified=None)


def _convert(html: str, doc=None, frontmatter=True) -> str:
    """完整链路：预处理（提取语言标记）→ 转换"""
    body = HTMLPreprocessor().process(html)
    return MarkdownConverter().convert(body, doc or _doc(), frontmatter)


class TestBasicConversion:
    def test_headings_and_bold(self):
        md = _convert("<h1>标题</h1><p><strong>加粗</strong>和<em>斜体</em></p>",
                      frontmatter=False)
        assert md.startswith("# 标题")
        assert "**加粗**" in md
        assert "_斜体_" in md  # html2text 使用下划线强调

    def test_lists(self):
        md = _convert("<ul><li>A</li><li>B</li></ul>"
                      "<ol><li>1</li><li>2</li></ol>", frontmatter=False)
        assert "A" in md and "B" in md
        assert "1. " in md or "1." in md  # 有序列表恢复
        assert "\\-" not in md  # 列表符号未被转义

    def test_code_block_with_language(self):
        html = '<pre><code class="language-python">\nprint(1)\n</code></pre>'
        md = _convert(html, frontmatter=False)
        assert "```python" in md
        assert "print(1)" in md
        assert md.count("```") == 2

    def test_table(self):
        html = ("<table><tr><th>A</th><th>B</th></tr>"
                "<tr><td>1</td><td>2</td></tr></table>")
        md = _convert(html, frontmatter=False)
        assert "A| B" in md
        assert "---|---" in md
        assert "1| 2" in md

    def test_frontmatter(self):
        md = _convert("<p>正文</p>")
        assert md.startswith("---")
        assert 'title: "测试笔记"' in md
        assert "tags: [tag1]" in md
        assert 'location: "/测试/"' in md


class TestPostprocess:
    def test_blank_line_compression(self):
        conv = MarkdownConverter()
        assert conv._normalize_blank_lines("a\n\n\n\nb") == "a\n\nb"

    def test_blank_lines_kept_in_code_block(self):
        conv = MarkdownConverter()
        text = "```\na\n\n\n\nb\n```"
        assert conv._normalize_blank_lines(text) == text

    def test_ordered_list_unescape(self):
        conv = MarkdownConverter()
        assert conv._unescape_list_markers("1\\. 步骤\n2\\. 步骤") == "1. 步骤\n2. 步骤"

    def test_dash_list_unescape(self):
        conv = MarkdownConverter()
        assert conv._unescape_list_markers("\\- 项目") == "- 项目"


class TestNoiseCleaning:
    """转换噪音清理（微信文章等复杂 HTML 场景）"""

    def test_empty_link_removed(self):
        conv = MarkdownConverter()
        assert conv._clean_line("正文 [](<>) 内容") == "正文  内容"

    def test_empty_link_in_heading(self):
        conv = MarkdownConverter()
        out = conv._clean_line("# [](<>)[](<>)**标题**")
        assert "[](<>)" not in out
        assert out.startswith("# **标题**")

    def test_empty_image_removed(self):
        conv = MarkdownConverter()
        assert conv._clean_line("![](./a.jpg)![]()") == "![](./a.jpg)"

    def test_bold_misalignment_fixed(self):
        conv = MarkdownConverter()
        out = conv._clean_line("**即：****内容****结尾。********【块】******")
        assert "****" not in out
        assert "**即：**" in out

    def test_code_block_not_touched(self):
        conv = MarkdownConverter()
        text = "```\n**keep**  ****\n[](<>)\n```"
        assert conv._clean_markdown_noise(text) == text

    def test_leading_punctuation_cleaned(self):
        conv = MarkdownConverter()
        assert conv._clean_line("，正文") == "正文"
