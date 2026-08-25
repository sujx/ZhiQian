"""导出控制测试：暂停/继续/停止"""

from __future__ import annotations

import logging
import threading
import time

logging.disable(logging.CRITICAL)

from exporter.config import ExportConfig
from exporter.app import WizNoteExporter


def _make_exporter(wiznote_fixture_dir, tmp_path, workers=1):
    cfg = ExportConfig(
        source_type="local", source_dir=str(wiznote_fixture_dir),
        output_dir=str(tmp_path), max_workers=workers)
    return WizNoteExporter(cfg)


class TestPauseResume:
    def test_pause_blocks_then_resume(self, wiznote_fixture_dir, tmp_path):
        exp = _make_exporter(wiznote_fixture_dir, tmp_path)
        pause = threading.Event()
        pause.set()  # 预置暂停

        progress = []
        t = threading.Thread(
            target=lambda: exp.export_all(
                progress_callback=lambda *a: progress.append(a),
                pause_event=pause), daemon=True)
        t.start()

        time.sleep(1.0)
        # 暂停中：worker 挂起，不应有进展
        assert len(progress) == 0, f"暂停应挂起，实际已完成 {len(progress)}"

        pause.clear()
        t.join(timeout=30)
        assert len(progress) == 4, f"恢复后应导出全部，实际 {len(progress)}"

    def test_cancel_releases_pause(self, wiznote_fixture_dir, tmp_path):
        """暂停状态下停止：应快速退出而不是挂死"""
        exp = _make_exporter(wiznote_fixture_dir, tmp_path)
        pause = threading.Event()
        cancel = threading.Event()
        pause.set()  # 暂停
        cancel.set()  # 同时停止

        progress = []
        t = threading.Thread(
            target=lambda: exp.export_all(
                progress_callback=lambda *a: progress.append(a),
                cancel_event=cancel, pause_event=pause), daemon=True)
        t.start()
        t.join(timeout=10)
        assert not t.is_alive(), "停止应解除暂停等待并退出"
        assert len(progress) < 4

    def test_pause_with_concurrency(self, wiznote_fixture_dir, tmp_path):
        """并发模式（2 线程）下暂停/恢复"""
        exp = _make_exporter(wiznote_fixture_dir, tmp_path, workers=2)
        pause = threading.Event()
        pause.set()

        progress = []
        t = threading.Thread(
            target=lambda: exp.export_all(
                progress_callback=lambda *a: progress.append(a),
                pause_event=pause), daemon=True)
        t.start()
        time.sleep(1.0)
        # 暂停中：至多完成并发数（2）篇在途任务
        assert len(progress) <= 2, f"并发暂停应最多完成在途任务，实际 {len(progress)}"
        pause.clear()
        t.join(timeout=30)
        assert len(progress) == 4

    def test_cancel_in_serial_mode(self, wiznote_fixture_dir, tmp_path):
        """P0 修复回归：串行模式（workers=1）下 cancel 应立即生效

        之前 _safe_export_one 的 cancel 检查在 pause 块内，
        无 pause 时 cancel 完全失效。修复后入口独立检查。
        """
        exp = _make_exporter(wiznote_fixture_dir, tmp_path, workers=1)
        cancel = threading.Event()
        cancel.set()  # 预置取消

        progress = []
        t = threading.Thread(
            target=lambda: exp.export_all(
                progress_callback=lambda *a: progress.append(a),
                cancel_event=cancel), daemon=True)
        t.start()
        t.join(timeout=10)
        assert not t.is_alive(), "串行模式 cancel 应立即退出"
        # 全部被跳过（cancel 在每篇入口返回"已取消"）
        assert len(progress) == 0, f"应全部取消，实际完成 {len(progress)}"
