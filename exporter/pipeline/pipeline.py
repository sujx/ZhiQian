"""ExportPipeline：串联 HTML 清洗 → 图片处理 → Markdown 转换"""

from __future__ import annotations

from typing import Dict, List, Tuple

from bs4 import BeautifulSoup

from exporter.models import WizDocument
from exporter.pipeline.converter import MarkdownConverter
from exporter.pipeline.images import ImageProcessor
from exporter.pipeline.preprocessor import HTMLPreprocessor


class ExportPipeline:
    """单篇笔记的处理管线"""

    def __init__(self, image_strategy: str = "file",
                 add_frontmatter: bool = True) -> None:
        self.preprocessor = HTMLPreprocessor()
        self.converter = MarkdownConverter()
        self.images = ImageProcessor(image_strategy)
        self.add_frontmatter = add_frontmatter

    def run(self, html: str, images: Dict[str, bytes],
            doc: WizDocument) -> Tuple[str, List[dict]]:
        """处理一篇笔记

        Returns:
            (markdown_text, resources): resources 为需落盘资源 [{filename, data}]
        """
        body = self.preprocessor.process(html)
        resources = self.images.process_images(body, images)
        md = self.converter.convert(body, doc, self.add_frontmatter)
        return md, resources
