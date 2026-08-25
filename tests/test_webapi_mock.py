"""WebAPISource 端到端测试（基于 mock 服务器）

验证: 登录 → 知识库列表 → 切换 → 文件夹列表 → 拉取笔记 → 下载HTML → 完整导出
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path

# 允许从项目根导入 exporter 包
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests" / "fixtures"))

logging.basicConfig(level=logging.CRITICAL)
from mock_wiz_api import start_mock_server, KB_GUID  # noqa: E402


def test_source_chain():
    server, base = start_mock_server()
    try:
        from exporter.sources.webapi.source import WebAPISource

        src = WebAPISource("test@wiz.local", "secret", base)

        # 1. 登录
        assert src.login(), "登录失败"
        assert src.auth.token == "mock-token-123"

        # 2. 知识库列表
        kbs = src.discover_sources()
        assert "个人笔记" in kbs, kbs

        # 3. 文件夹列表
        src.switch_source("个人笔记")
        folders = src.get_folder_list()
        assert "/技术/Python/" in folders, folders
        print(f"✓ 文件夹列表: {folders}")

        # 4. 拉取指定文件夹笔记
        docs = src.get_all_documents(folders=["/技术/Python/", "/生活/"])
        titles = [d.title for d in docs]
        assert "Python 并发指南" in titles and "生活记录" in titles, titles
        print(f"✓ 文件夹过滤拉取: {titles}")

        # 5. 下载笔记 HTML
        py_doc = next(d for d in docs if d.title == "Python 并发指南")
        html, images = src.get_document_html(py_doc.guid)
        assert html and "Python 并发" in html
        print("✓ 笔记 HTML 下载")
    finally:
        server.shutdown()


def test_end_to_end_export():
    import shutil
    import tempfile

    server, base = start_mock_server()
    try:
        from exporter.config import ExportConfig
        from exporter.app import WizNoteExporter

        out = Path(tempfile.mkdtemp(prefix="wizweb_"))
        cfg = ExportConfig(
            source_type="webapi",
            username="test@wiz.local",
            password="secret",
            as_url=base,
            kb_guid=KB_GUID,
            include_folders=["/技术/", "/技术/Python/", "/生活/"],
            output_dir=str(out),
            max_workers=2,
        )
        exp = WizNoteExporter(cfg)
        stats = exp.export_all()
        print(f"✓ 端到端导出: 成功 {stats.success}/{stats.total}, 失败 {stats.failed}")

        assert stats.total == 3, stats.total          # 技术1 + Python1 + 生活1
        assert stats.success == 3, stats.success
        assert stats.failed == 0

        # 输出文件检查
        files = list(out.rglob("*.md"))
        assert len(files) == 3, [f.name for f in files]
        # 代码块笔记：语言标记 + 内容正确
        tech_md = next(f for f in files if "技术笔记一" in f.name)
        content = tech_md.read_text(encoding="utf-8")
        assert "```python" in content and "x = 1" in content, content
        # 列表笔记
        py_md = next(f for f in files if "Python" in f.name)
        content2 = py_md.read_text(encoding="utf-8")
        assert "线程" in content2 and "协程" in content2
        print(f"✓ 输出文件: {[f.name for f in files]}")
    finally:
        server.shutdown()


if __name__ == "__main__":
    test_source_chain()
    test_end_to_end_export()
    print("\n=== WebAPI mock 全部测试通过 ===")
