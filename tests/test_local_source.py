"""LocalSource 集成测试（基于生成的迷你 fixture 库）"""

from __future__ import annotations

import logging

logging.disable(logging.CRITICAL)
from exporter.sources.local import LocalSource


class TestLocalSource:
    def test_discover_sources(self, wiznote_fixture_dir):
        src = LocalSource(str(wiznote_fixture_dir))
        sources = src.discover_sources()
        assert "个人笔记" in sources
        assert "测试群组" in sources

    def test_get_all_documents(self, wiznote_fixture_dir):
        src = LocalSource(str(wiznote_fixture_dir))
        docs = src.get_all_documents()
        assert len(docs) == 3
        titles = [d.title for d in docs]
        assert "笔记一：列表与标题" in titles
        # 标签关联
        doc1 = next(d for d in docs if "笔记一" in d.title)
        assert doc1.tags == ["前端"]
        # 位置
        assert doc1.location == "/技术/前端"

    def test_get_document_html(self, wiznote_fixture_dir):
        src = LocalSource(str(wiznote_fixture_dir))
        docs = src.get_all_documents()
        doc = next(d for d in docs if "笔记三" in d.title)
        html, images = src.get_document_html(doc.guid)
        assert html is not None
        assert "含图片与附件" in html
        assert any("index_files" in k for k in images), images.keys()

    def test_attachments(self, wiznote_fixture_dir):
        src = LocalSource(str(wiznote_fixture_dir))
        docs = src.get_all_documents()
        doc = next(d for d in docs if "笔记三" in d.title)
        atts = src.get_document_attachments(doc.guid)
        assert len(atts) == 2
        pdf = next(a for a in atts if a.name.endswith(".pdf"))
        data = src.download_attachment(doc.guid, pdf.guid)
        assert data is not None
        assert data.startswith(b"%PDF")

    def test_group_source(self, wiznote_fixture_dir):
        src = LocalSource(str(wiznote_fixture_dir))
        assert src.switch_source("测试群组")
        docs = src.get_all_documents()
        assert len(docs) == 1
        assert docs[0].source_name == "测试群组"


class TestDiscover:
    def test_find_returns_fixture(self, wiznote_fixture_dir):
        # 自动查找：构造一个"文档目录"场景验证发现逻辑
        from exporter.sources.discover import _has_index_db

        assert _has_index_db(wiznote_fixture_dir)
