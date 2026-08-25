"""HTMLPreprocessor 与 ImageProcessor 单元测试"""

from __future__ import annotations

import base64

from bs4 import BeautifulSoup

from exporter.pipeline.images import ImageProcessor
from exporter.pipeline.preprocessor import HTMLPreprocessor


class TestPreprocessor:
    def test_body_extraction(self):
        body = HTMLPreprocessor().process(
            "<html><body><p>正文</p></body></html>")
        assert body.find("p").get_text() == "正文"

    def test_attribute_cleaning(self):
        body = HTMLPreprocessor().process(
            '<p style="color:red" class="x" id="y">文本</p>')
        p = body.find("p")
        assert "style" not in p.attrs
        assert "class" not in p.attrs

    def test_code_language_extracted(self):
        body = HTMLPreprocessor().process(
            '<pre><code class="language-javascript">let x</code></pre>')
        pre = body.find("pre")
        assert pre.get("data-lang") == "javascript"

    def test_table_thead_added(self):
        body = HTMLPreprocessor().process(
            "<table><tr><th>A</th></tr><tr><td>1</td></tr></table>")
        assert body.find("thead") is not None

    def test_empty_tag_removed(self):
        body = HTMLPreprocessor().process(
            "<p>有用</p><p> </p><div></div>")
        assert body.find_all("div") == []
        texts = [p.get_text(strip=True) for p in body.find_all("p")]
        assert texts == ["有用"]


class TestImageProcessor:
    PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")

    def test_local_image_to_file(self):
        soup = BeautifulSoup('<img src="index_files/pic.png">', "html.parser")
        res = ImageProcessor("file").process_images(
            soup, {"index_files/pic.png": self.PNG})
        assert len(res) == 1
        assert res[0]["filename"] == "pic.png"
        assert soup.img["src"] == "./assets/pic.png"

    def test_base64_image_extracted(self):
        uri = ("data:image/png;base64,"
               "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
        soup = BeautifulSoup(f'<img src="{uri}">', "html.parser")
        res = ImageProcessor("file").process_images(soup, {})
        assert len(res) == 1
        assert res[0]["filename"].startswith("image_")
        assert soup.img["src"].startswith("./assets/")

    def test_http_image_untouched(self):
        soup = BeautifulSoup(
            '<img src="https://example.com/a.png">', "html.parser")
        res = ImageProcessor("file").process_images(soup, {})
        assert res == []
        assert soup.img["src"] == "https://example.com/a.png"

    def test_duplicate_name_unique(self):
        soup = BeautifulSoup(
            '<img src="index_files/a.png"><img src="index_files/a.png">',
            "html.parser")
        res = ImageProcessor("file").process_images(
            soup, {"index_files/a.png": self.PNG})
        names = [r["filename"] for r in res]
        assert len(set(names)) == 2, names
