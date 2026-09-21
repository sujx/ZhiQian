"""WizNoteExporter：主控制器，编排数据源 → 管线 → 存储"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import List, Optional, Tuple

from exporter.config import ExportConfig
from exporter.models import ExportStats, WizDocument
from exporter.pipeline.pipeline import ExportPipeline
from exporter.sources.base import DataSourceAdapter
from exporter.sources.local import LocalSource
from exporter.storage.manager import StorageManager

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}


class WizNoteExporter:
    """导出主控制器"""

    def __init__(self, config: ExportConfig) -> None:
        self.config = config
        self.source: DataSourceAdapter = self._create_source()
        self.pipeline = ExportPipeline(
            image_strategy=config.image_strategy,
            add_frontmatter=config.add_frontmatter,
        )
        self.storage = StorageManager(
            config.output_dir, config.preserve_structure
        )
        # 线程本地缓存：html2text 解析器有内部状态，并发时必须每线程一份
        self._local = threading.local()

    def _get_pipeline(self) -> ExportPipeline:
        """获取当前线程的 pipeline 实例（并发安全）"""
        pipeline = getattr(self._local, "pipeline", None)
        if pipeline is None:
            pipeline = ExportPipeline(
                image_strategy=self.config.image_strategy,
                add_frontmatter=self.config.add_frontmatter,
            )
            self._local.pipeline = pipeline
        return pipeline

    def _create_source(self) -> DataSourceAdapter:
        from exporter.sources import create_source

        return create_source(self.config)

    # ---------- 列表 ----------

    def list_notes(self) -> None:
        """打印所有库的笔记清单"""
        for src_name in self.source.discover_sources():
            self.source.switch_source(src_name)
            docs = self.source.get_all_documents()
            print(f"\n=== {src_name} ({len(docs)} 篇) ===")
            for doc in docs:
                tag_str = f" [{', '.join(doc.tags)}]" if doc.tags else ""
                print(f"  {doc.title}{tag_str}  <- {doc.location}")

    # ---------- 导出 ----------

    def export_all(self, progress_callback=None, cancel_event=None,
                   pause_event=None) -> ExportStats:
        """导出全部笔记（支持并发，统计由主线程汇总，无线程竞争）

        Args:
            progress_callback: 可选回调 (done, total, title, ok, fail)
            cancel_event: 可选 threading.Event，设置后中断导出
            pause_event: 可选 threading.Event，设置后暂停（每篇任务前挂起）
        """
        stats = ExportStats()
        done = 0

        # 知识库列表
        src_names = self.source.discover_sources()

        for src_name in src_names:
            if cancel_event and cancel_event.is_set():
                logger.warning("导出已取消")
                break
            self.source.switch_source(src_name)
            docs = self.source.get_all_documents()

            # 增量模式：跳过上次导出后未修改的笔记
            if self.config.incremental:
                before = len(docs)
                docs = [d for d in docs
                        if self.storage.is_note_modified(d.guid, d.modified)]
                skipped = before - len(docs)
                logger.info(f"[{src_name}] 增量模式: 共 {before} 篇, "
                            f"跳过 {skipped} 篇未修改")
                stats.total += skipped  # 计入总数但不执行

            # 断点续导：跳过已导出的笔记
            if self.config.resume:
                before = len(docs)
                docs = [d for d in docs
                        if not self.storage.is_exported(d.guid)]
                skipped = before - len(docs)
                if skipped > 0:
                    logger.info(f"[{src_name}] 断点续导: 跳过 {skipped} 篇"
                                f"已导出笔记")
                stats.total += skipped
            stats.total += len(docs)
            logger.info(f"[{src_name}] 开始导出 {len(docs)} 篇"
                        f"(线程数 {self.config.max_workers})")

            results = self._export_batch(docs, cancel_event, pause_event)

            for doc, (ok, reason, skipped, atts) in zip(docs, results):
                if ok:
                    stats.success += 1
                else:
                    stats.failed += 1
                    stats.record_failure(doc.title, doc.guid, reason)
                    logger.error(f"导出失败 [{src_name}] {doc.title}: {reason}")
                stats.skipped_images += skipped
                stats.attachments += atts
                done += 1
                if progress_callback:
                    progress_callback(done, stats.total, doc.title,
                                      stats.success, stats.failed)

        self._save_metadata(stats)
        return stats

    def _export_batch(self, docs: List[WizDocument], cancel_event=None,
                      pause_event=None) -> List[Tuple[bool, str, int, int]]:
        """批量导出一批笔记，返回每篇的 (成功?, 原因, 跳过图片数, 附件数)

        串行（max_workers<=1）时逐个执行；并发时用线程池，
        结果顺序与 docs 一致（主线程按序汇总）。
        """
        if self.config.max_workers <= 1:
            return [self._safe_export_one(doc, cancel_event, pause_event)
                    for doc in docs]

        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: dict = {}
        with ThreadPoolExecutor(
                max_workers=self.config.max_workers,
                thread_name_prefix="exporter") as pool:
            futures = {pool.submit(
                self._safe_export_one, doc, cancel_event, pause_event): doc
                for doc in docs}
            for fut in as_completed(futures):
                doc = futures[fut]
                try:
                    results[doc.guid] = fut.result()
                except Exception as e:  # noqa: BLE001
                    results[doc.guid] = (False, f"异常: {e}", 0, 0)
                if cancel_event and cancel_event.is_set():
                    logger.warning("导出已取消，停止提交新任务")
                    for f in futures:
                        f.cancel()
                    break
        return [results.get(doc.guid, (False, "已取消", 0, 0)) for doc in docs]

    def _safe_export_one(self, doc: WizDocument, cancel_event=None,
                         pause_event=None) -> Tuple[bool, str, int, int]:
        """单篇导出的线程安全包装，返回 (成功?, 失败原因, 跳过图片数, 附件数)

        暂停：pause_event 设置时在任务开始前挂起等待（可随时停止）。
        取消：cancel_event 设置时立即返回（独立于暂停，串行/并发均生效）。
        """
        # 取消检查（独立于暂停，CLI/GUI 串行模式也生效）
        if cancel_event is not None and cancel_event.is_set():
            return False, "已取消", 0, 0
        # 暂停等待
        if pause_event is not None:
            while pause_event.is_set():
                if cancel_event is not None and cancel_event.is_set():
                    return False, "已停止", 0, 0
                time.sleep(0.2)
        try:
            result = self._export_one(doc)
            # 成功导出后立即持久化索引（断点续导检查点）
            if result[0]:
                self.storage.checkpoint()
            return result
        except Exception as e:  # noqa: BLE001
            logger.error(f"导出异常 {doc.title}: {e}")
            return False, f"异常: {e}", 0, 0

    def export_document(self, guid: str) -> Optional[str]:
        """导出单篇（调试用），返回 Markdown 文本"""
        docs = self.source.get_all_documents()
        doc = next((d for d in docs if d.guid == guid), None)
        if doc is None:
            return None
        html, images = self.source.get_document_html(doc.guid)
        if not html:
            return None
        md, _ = self.pipeline.run(html, images, doc)
        return md

    def _export_one(self, doc: WizDocument) -> Tuple[bool, str, int, int]:
        """导出单篇，返回 (成功?, 失败原因, 跳过图片数, 附件数)"""
        html, images = self.source.get_document_html(doc.guid)
        if not html:
            return False, "无法获取笔记内容", 0, 0

        md, resources = self._get_pipeline().run(html, images, doc)
        note_path = self.storage.save_note(doc, md)
        if note_path is None:
            return False, "写入 Markdown 失败", 0, 0

        for res in resources:
            self.storage.save_asset(note_path, res["filename"], res["data"])

        skipped = 0
        attachments = 0
        # 附件（跳过图片附件）
        if doc.attachment_count > 0:
            for att in self.source.get_document_attachments(doc.guid):
                if self._is_image(att.name):
                    skipped += 1
                    continue
                data = self.source.download_attachment(doc.guid, att.guid)
                if data:
                    self.storage.save_asset(note_path, att.name, data)
                    attachments += 1
        return True, "", skipped, attachments

    @staticmethod
    def _is_image(name: str) -> bool:
        return os.path.splitext(name)[1].lower() in _IMAGE_EXTS

    # ---------- 元数据 ----------

    def _save_metadata(self, stats: ExportStats) -> None:
        meta_dir = self.storage.base_dir / "_metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        with open(meta_dir / "index.json", "w", encoding="utf-8") as f:
            json.dump(list(self.storage.note_index.values()), f,
                      ensure_ascii=False, indent=2)
        with open(meta_dir / "report.json", "w", encoding="utf-8") as f:
            json.dump(stats.failures, f, ensure_ascii=False, indent=2)
