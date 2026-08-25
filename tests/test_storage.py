"""StorageManager 单元测试：文件名清理 / 重名 / 目录层级 / 增量"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from exporter.models import WizDocument
from exporter.storage.manager import StorageManager


def _doc(title, location="/测试/", guid="g1", source="个人笔记",
         created=None, modified=None):
    return WizDocument(guid=guid, title=title, location=location,
                       source_name=source, created=created, modified=modified)


class TestSanitize:
    def test_illegal_chars(self):
        sm = StorageManager("x")
        # < > : " 各替换为一个 _，共 3 个下划线
        assert sm.sanitize('a<b>:"c') == "a_b___c"

    def test_slash_replaced(self):
        sm = StorageManager("x")
        assert sm.sanitize("a/b\\c") == "a_b_c"

    def test_control_chars(self):
        sm = StorageManager("x")
        assert "\x08" not in sm.sanitize("a\x08b")

    def test_empty_fallback(self):
        sm = StorageManager("x")
        assert sm.sanitize("") == "未命名"

    def test_posix_rules_allow_colon(self):
        """跨平台：POSIX 规则下冒号/问号/星号合法，仅 / 与 NUL 替换"""
        import exporter.storage.manager as m

        old = m._ILLEGAL
        m._ILLEGAL = re.compile(r"[/\r\n\t\x00-\x1f\x7f]")
        try:
            sm = StorageManager("x")
            assert sm.sanitize("会议:纪要?重要*版") == "会议:纪要?重要*版"
            assert sm.sanitize("a/b") == "a_b"
            assert sm.sanitize("a\x00b") == "a_b"
        finally:
            m._ILLEGAL = old


class TestSaveNote:
    def test_folder_structure(self, tmp_path):
        sm = StorageManager(str(tmp_path))
        doc = _doc("笔记A", location="/技术/前端/", guid="g-001")
        path = sm.save_note(doc, "# 内容")
        rel = path.relative_to(tmp_path)
        assert rel == Path("个人笔记/技术/前端/笔记A.md")

    def test_duplicate_guid_suffix(self, tmp_path):
        sm = StorageManager(str(tmp_path))
        doc1 = _doc("同名", guid="guid-11111111")
        doc2 = _doc("同名", guid="guid-22222222")
        p1 = sm.save_note(doc1, "# a")
        p2 = sm.save_note(doc2, "# b")
        assert p1 != p2
        assert p1.exists() and p2.exists()

    def test_md_extension_not_duplicated(self, tmp_path):
        sm = StorageManager(str(tmp_path))
        doc = _doc("笔记.md", location="/", guid="g-002")
        path = sm.save_note(doc, "# 内容")
        assert path.name == "笔记.md", path.name

    def test_flat_mode(self, tmp_path):
        sm = StorageManager(str(tmp_path), preserve_structure=False)
        doc = _doc("笔记B", location="/技术/深层/", guid="g-003")
        path = sm.save_note(doc, "# 内容")
        # flat 仅扁平 location，库名目录仍保留
        assert path.parent == tmp_path / "个人笔记"


class TestSaveAsset:
    def test_assets_dir(self, tmp_path):
        sm = StorageManager(str(tmp_path))
        note = sm.save_note(_doc("笔记", guid="g-004"), "# 内容")
        asset = sm.save_asset(note, "img.png", b"data")
        assert asset.parent.name == "assets"
        assert asset.name == "img.png"

    def test_asset_duplicate_increment(self, tmp_path):
        sm = StorageManager(str(tmp_path))
        note = sm.save_note(_doc("笔记", guid="g-005"), "# 内容")
        sm.save_asset(note, "a.png", b"1")
        asset2 = sm.save_asset(note, "a.png", b"2")
        assert asset2.name == "a_1.png"


class TestIncremental:
    """增量备份：is_note_modified 判定"""

    def test_new_note_needs_export(self, tmp_path):
        sm = StorageManager(str(tmp_path))
        assert sm.is_note_modified("no-record", None) is True

    def test_older_modified_skipped(self, tmp_path):
        sm = StorageManager(str(tmp_path))
        now = datetime(2026, 6, 1)
        sm.save_note(_doc("笔记", guid="g-101", created=now, modified=now), "# 内容")
        assert sm.is_note_modified("g-101", now) is False

    def test_newer_modified_reexported(self, tmp_path):
        sm = StorageManager(str(tmp_path))
        old = datetime(2026, 6, 1)
        sm.save_note(_doc("笔记", guid="g-102", created=old, modified=old), "# 内容")
        newer = old + timedelta(days=1)
        assert sm.is_note_modified("g-102", newer) is True

    def test_index_persisted_across_runs(self, tmp_path):
        sm1 = StorageManager(str(tmp_path))
        now = datetime(2026, 6, 1)
        sm1.save_note(_doc("笔记", guid="g-103", created=now, modified=now), "# 内容")
        sm1.save_index()  # 写入 _metadata/index.json
        # 重新创建管理器（模拟二次运行）→ 从磁盘恢复索引
        sm2 = StorageManager(str(tmp_path))
        assert sm2.is_note_modified("g-103", now) is False
