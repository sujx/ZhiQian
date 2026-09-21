"""StorageManager：输出目录结构 + Markdown/附件写入 + 文件名清理"""

from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Dict, Optional

from exporter.models import WizDocument

logger = logging.getLogger(__name__)

# 非法文件名字符按平台区分：
# - Windows: 保留完整 Windows 保留字符集
# - POSIX (macOS/Linux): 仅 / 与 NUL 非法，冒号/问号/星号等合法，不过度替换
if os.name == "nt":
    _ILLEGAL = re.compile(r'[<>:"/\\|?*\r\n\t\x00-\x1f\x7f]')
else:
    _ILLEGAL = re.compile(r"[/\r\n\t\x00-\x1f\x7f]")


class StorageManager:
    """负责 .md 文件与附件的落盘，保持文件夹层级"""

    def __init__(self, base_dir: str, preserve_structure: bool = True) -> None:
        self.base_dir = Path(base_dir)
        self.preserve_structure = preserve_structure
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.note_index: Dict[str, dict] = {}
        self._index_lock = threading.Lock()
        self._load_index()

    # ---------- 索引（增量备份基础） ----------

    def _load_index(self) -> None:
        """从 index.json 恢复上次导出的索引（含修改时间）"""
        index_file = self.base_dir / "_metadata" / "index.json"
        if index_file.exists():
            try:
                import json
                with open(index_file, "r", encoding="utf-8") as f:
                    records = json.load(f)
                self.note_index = {r.get("guid"): r for r in records
                                   if r.get("guid")}
                logger.info(f"加载索引 {len(self.note_index)} 条记录")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"加载索引失败（视为全新导出）: {e}")
                self.note_index = {}

    def is_note_modified(self, guid: str, modified) -> bool:
        """判断笔记是否需要重新导出（增量模式用）

        无记录 / 记录无修改时间 / 当前修改时间更新 → True
        """
        record = self.note_index.get(guid)
        if record is None:
            return True
        saved = record.get("modified")
        if not saved or modified is None:
            return True
        try:
            from datetime import datetime
            saved_dt = datetime.fromisoformat(str(saved))
            cur_dt = modified if isinstance(modified, datetime) \
                else datetime.fromisoformat(str(modified))
            return cur_dt > saved_dt
        except (ValueError, TypeError):
            return True

    def save_index(self) -> None:
        """把索引写盘（_metadata/index.json），供下次增量比对"""
        import json

        meta_dir = self.base_dir / "_metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(meta_dir / "index.json", "w", encoding="utf-8") as f:
                json.dump(list(self.note_index.values()), f,
                          ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error(f"保存索引失败: {e}")

    def checkpoint(self) -> None:
        """线程安全的索引持久化（断点续导用），每篇成功导出后调用"""
        with self._index_lock:
            self.save_index()

    def is_exported(self, guid: str) -> bool:
        """判断笔记是否已导出（断点续导用）"""
        return guid in self.note_index

    # ---------- 路径计算 ----------

    def note_dir(self, doc: WizDocument) -> Path:
        """计算笔记所在目录（含群组名 + location 层级）"""
        path = self.base_dir / self.sanitize(doc.source_name or "个人笔记")
        if self.preserve_structure:
            for part in doc.folder_parts:
                path = path / self.sanitize(part)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_note(self, doc: WizDocument, content: str) -> Optional[Path]:
        """保存 Markdown，重名时追加 GUID 前 8 位"""
        try:
            directory = self.note_dir(doc)
            # 标题已带 .md/.markdown 扩展名时不再追加
            title_ext = Path(doc.title).suffix.lower()
            if title_ext in (".md", ".markdown"):
                filename = self.sanitize(Path(doc.title).stem) + title_ext
            else:
                filename = self.sanitize(doc.title) + ".md"
            filepath = directory / filename

            if filepath.exists():
                stem = Path(filename).stem
                filepath = directory / f"{stem}_{doc.guid[:8]}.md"

            filepath.write_text(content, encoding="utf-8")
            self.note_index[doc.guid] = {
                "guid": doc.guid,
                "title": doc.title,
                "path": str(filepath.relative_to(self.base_dir)),
                "location": doc.location,
                "tags": doc.tags,
                "modified": doc.modified.isoformat() if doc.modified else "",
            }
            return filepath
        except OSError as e:
            logger.error(f"保存笔记失败 {doc.title}: {e}")
            return None

    def save_asset(self, note_path: Path, name: str, data: bytes) -> Optional[Path]:
        """保存附件/图片到 <笔记目录>/assets/，重名递增 _1/_2"""
        try:
            assets_dir = note_path.parent / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)

            safe = self.sanitize(name)
            target = assets_dir / safe
            if target.exists():
                stem, ext = os.path.splitext(safe)
                i = 1
                while target.exists():
                    target = assets_dir / f"{stem}_{i}{ext}"
                    i += 1
            target.write_bytes(data)
            return target
        except OSError as e:
            logger.error(f"保存附件失败 {name}: {e}")
            return None

    # ---------- 工具 ----------

    @staticmethod
    def sanitize(name: str) -> str:
        """清理文件名非法字符，截断超长名"""
        if not name:
            return "未命名"
        clean = _ILLEGAL.sub("_", name).strip(" .")
        if len(clean) > 200:
            stem, ext = os.path.splitext(clean)
            clean = stem[:200] + ext
        return clean or "未命名"
