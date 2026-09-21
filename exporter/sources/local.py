"""LocalSource：从为知笔记本地缓存读取

为知笔记本地存储结构（实测）:
    <source_dir>/                    # --input 指向（如 "My Knowledge"）
        Data/                        # 可选层级
            <email>/
                index.db             # SQLite 元数据库（位于数据根目录）
                My Notes/*.ziw       # 笔记：ZIP 文件，名为 <笔记标题>.ziw
                云原生/*.ziw          #   按 DOCUMENT_LOCATION 分类存放
                ...
                group/<gid>/         # 群组库（可选），结构同个人库

笔记 ZIP (.ziw) 内: index.html（多编码: utf-8/utf-16-le/gbk）+ index_files/ 图片附件
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from exporter.models import WizAttachment, WizDocument
from exporter.sources.base import DataSourceAdapter

logger = logging.getLogger(__name__)

_HTML_ENCODINGS = ["utf-8", "utf-16-le", "gbk", "gb2312"]
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
_WINDOWS_ILLEGAL = '<>:"/\\|?*\r\n'
_MAX_SCAN_DEPTH = 4  # 扫描 index.db 的最大目录深度
_MAX_ZIP_ENTRY_BYTES = 100 * 1024 * 1024  # ZIP 单条目大小上限（100 MB）


class _SourceCtx:
    """单个库（个人或群组）的路径上下文"""

    def __init__(self, name: str, db_path: Path):
        self.name = name
        self.db_path = db_path
        self.root = db_path.parent  # 数据根目录（index.db 所在目录）
        # 旧版附件目录（兼容）：<root>/attachments
        self.attachments_dir = self.root / "attachments" \
            if (self.root / "attachments").is_dir() else None


class LocalSource(DataSourceAdapter):
    """本地缓存数据源"""

    name = "个人笔记"

    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        self._contexts: List[_SourceCtx] = []
        self._current: Optional[_SourceCtx] = None
        self._discover()

    # ---------- 目录发现 ----------

    def _discover(self) -> None:
        """扫描所有含 index.db 的目录作为数据源（支持多级目录结构）"""
        root = self.source_dir
        if not root.is_dir():
            logger.warning(f"源目录不存在: {root}")
            return

        db_paths = self._find_index_dbs(root)
        if not db_paths:
            logger.error(f"未找到 index.db，请确认 --input 指向为知笔记数据目录: {root}")
            return

        for db in db_paths:
            # 群组库: index.db 位于 <root>/group/<gid>/ 下
            if db.parent.name == "group" or db.parent.parent.name == "group":
                gname = self._read_group_name(db) or f"群组-{db.parent.name[:8]}"
                self._contexts.append(_SourceCtx(name=gname, db_path=db))
            else:
                # 个人库：避免重复添加（如 My Knowledge 和 My Knowledge/Data 同时命中）
                if not any(c.db_path == db for c in self._contexts):
                    self._contexts.append(_SourceCtx(name="个人笔记", db_path=db))

        if self._contexts:
            self._current = self._contexts[0]
        logger.info(f"发现 {len(self._contexts)} 个数据源: "
                    f"{[c.name for c in self._contexts]}")

    def _find_index_dbs(self, root: Path) -> List[Path]:
        """在 root 下深度 <= _MAX_SCAN_DEPTH 的目录中查找 index.db"""
        found: List[Path] = []
        root_depth = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            depth = len(current.parts) - root_depth
            if depth > _MAX_SCAN_DEPTH:
                dirnames[:] = []
                continue
            if "index.db" in filenames:
                found.append(current / "index.db")
            # 跳过明显的无关目录，加速扫描
            dirnames[:] = [d for d in dirnames
                           if d not in (".wizfulltextindex", "thumbcache")
                           and not d.startswith(".")]
        return found

    def _read_group_name(self, db_path: Path) -> Optional[str]:
        """从 WIZ_META 读取群组名（兼容多种 META_NAME 格式）"""
        try:
            conn = sqlite3.connect(str(db_path))
            try:
                row = conn.execute(
                    "SELECT META_VALUE FROM WIZ_META WHERE META_VALUE != '' "
                    "AND META_NAME IN ('DATABASE','GROUP') ORDER BY META_NAME LIMIT 1"
                ).fetchone()
                if row and row[0]:
                    return str(row[0]).strip() or None
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"读取群组名失败 {db_path}: {e}")
        return None

    # ---------- 数据源接口 ----------

    def discover_sources(self) -> List[str]:
        return [ctx.name for ctx in self._contexts]

    def switch_source(self, name: str) -> bool:
        for ctx in self._contexts:
            if ctx.name == name:
                self._current = ctx
                return True
        return False

    # ---------- 元数据读取 ----------

    def _connect(self) -> sqlite3.Connection:
        if self._current is None:
            raise RuntimeError("未发现有效数据源")
        conn = sqlite3.connect(str(self._current.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_documents(self) -> List[WizDocument]:
        """获取当前库全部文档元数据"""
        if self._current is None:
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DOCUMENT_GUID, DOCUMENT_TITLE, DOCUMENT_LOCATION, "
                "DT_CREATED, DT_MODIFIED, DOCUMENT_ATTACHEMENT_COUNT "
                "FROM WIZ_DOCUMENT"
            ).fetchall()

            docs = []
            for row in rows:
                docs.append(WizDocument(
                    guid=row["DOCUMENT_GUID"],
                    title=row["DOCUMENT_TITLE"] or "无标题",
                    location=row["DOCUMENT_LOCATION"] or "/",
                    created=self._parse_dt(row["DT_CREATED"]),
                    modified=self._parse_dt(row["DT_MODIFIED"]),
                    attachment_count=row["DOCUMENT_ATTACHEMENT_COUNT"] or 0,
                    source_name=self._current.name,
                ))

            # 批量补标签
            for doc in docs:
                tag_rows = conn.execute(
                    "SELECT t.TAG_NAME FROM WIZ_DOCUMENT_TAG dt "
                    "JOIN WIZ_TAG t ON dt.TAG_GUID = t.TAG_GUID "
                    "WHERE dt.DOCUMENT_GUID = ?",
                    (doc.guid,),
                ).fetchall()
                doc.tags = [r["TAG_NAME"] for r in tag_rows]

            logger.info(f"[{self._current.name}] 获取 {len(docs)} 个文档")
            return docs
        finally:
            conn.close()

    @staticmethod
    def _parse_dt(value) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    # ---------- 笔记文件定位 ----------

    def _doc_path_from_db(self, guid: str) -> Optional[Tuple[str, str]]:
        """从数据库查询笔记标题与位置，返回 (title, location)"""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT DOCUMENT_TITLE, DOCUMENT_LOCATION FROM WIZ_DOCUMENT "
                "WHERE DOCUMENT_GUID = ?",
                (guid,),
            ).fetchone()
            if row is None:
                return None
            return (row["DOCUMENT_TITLE"] or "无标题",
                    row["DOCUMENT_LOCATION"] or "/")
        finally:
            conn.close()

    def _safe_join(self, root: Path, *parts: str) -> Optional[Path]:
        """拼接路径并校验结果仍在 root 之下，防止路径穿越"""
        try:
            joined = root.joinpath(*parts)
        except (ValueError, OSError):
            return None
        resolved = joined.resolve()
        root_resolved = root.resolve()
        if not resolved.is_relative_to(root_resolved):
            logger.warning(f"路径穿越已拦截: {joined} 不在 {root} 内")
            return None
        return joined

    def _locate_note_file(self, title: str, location: str,
                          guid: Optional[str] = None) -> Optional[Path]:
        """定位笔记 ZIP 文件: <root>/<location>/<title>.ziw（多级容错）"""
        root = self._current.root
        loc_parts = [p for p in location.strip("/").split("/") if p]

        # 校验 location 不含路径穿越成分
        base = self._safe_join(root, *loc_parts) if loc_parts else root
        if base is None:
            base = root

        # 候选1: 精确路径（最常规）
        candidates = []
        candidates.append(base / f"{title}.ziw")

        # 候选2: 标题清洗非法字符后的文件名
        cleaned = "".join("_" if c in _WINDOWS_ILLEGAL else c for c in title)
        if cleaned != title:
            candidates.append(base / f"{cleaned}.ziw")

        # 候选3: 位置目录缺失时，回退到数据根目录
        if loc_parts:
            candidates.append(root / f"{title}.ziw")

        # 候选4: 按 GUID 命名的文件（兼容旧格式 {GUID} / GUID.ziw）
        if guid:
            candidates.extend([
                base / f"{{{guid}}}",
                base / f"{{{guid}}}.ziw",
                base / f"{guid}.ziw",
                root / f"{{{guid}}}",
                root / f"{{{guid}}}.ziw",
            ])

        # 候选5: 旧版 notes/ 目录结构（notes/{GUID} 或 notes/<title>.ziw）
        notes_dir = root / "notes"
        if notes_dir.is_dir():
            if guid:
                candidates.append(notes_dir / f"{{{guid}}}")
                candidates.append(notes_dir / f"{{{guid}}}.ziw")
            candidates.append(notes_dir / f"{title}.ziw")

        for cand in candidates:
            if cand.is_file():
                return cand

        # 候选6: 目录内模糊匹配（宽松归一化精确 → 前缀评分降级）
        if base.is_dir():
            title_norm = self._normalize_name(title)
            best, best_score = None, 0
            for f in base.glob("*.ziw"):
                f_norm = self._normalize_name(f.stem)
                if f_norm == title_norm:
                    return f  # 精确命中
                # 前缀评分：共享公共前缀越长越可能是同一篇
                score = 0
                for a, b in zip(f_norm, title_norm):
                    if a != b:
                        break
                    score += 1
                if score >= 15 and score > best_score:
                    best, best_score = f, score
            if best is not None:
                logger.debug(f"模糊匹配命中: {best.name} <- {title}")
                return best
        return None

    @staticmethod
    def _normalize_name(name: str) -> str:
        """文件名归一化：小写，非字母数字字符统一为 -（容错 |、/ 等替换）"""
        name = re.sub(r"[\W_]+", "-", name, flags=re.UNICODE).lower()
        return name.strip("-")

    # ---------- 内容读取 ----------

    def get_document_html(self, guid: str) -> Tuple[Optional[str], Dict[str, bytes]]:
        """打开笔记 .ziw，提取 index.html 和图片"""
        if self._current is None:
            return None, {}

        info = self._doc_path_from_db(guid)
        if info is None:
            logger.warning(f"数据库中不存在该笔记: {guid}")
            return None, {}
        title, location = info

        note_path = self._locate_note_file(title, location, guid)
        if note_path is None:
            logger.warning(f"笔记文件不存在: {title} ({location})")
            return None, {}

        html: Optional[str] = None
        images: Dict[str, bytes] = {}
        try:
            with zipfile.ZipFile(note_path, "r") as zf:
                for info in zf.infolist():
                    if info.file_size > _MAX_ZIP_ENTRY_BYTES:
                        logger.warning(
                            f"ZIP 条目 uncompressed大小超限（{info.file_size} > "
                            f"{_MAX_ZIP_ENTRY_BYTES}），已跳过: {info.filename}")
                        continue
                    name = info.filename
                    if name.endswith("index.html"):
                        html = self._decode_html(zf.read(name))
                    elif Path(name).suffix.lower() in _IMAGE_EXTS:
                        images[name] = zf.read(name)
        except zipfile.BadZipFile:
            logger.error(f"笔记文件损坏（非 ZIP）: {note_path}")
            return None, {}
        except Exception as e:  # noqa: BLE001
            logger.error(f"解压笔记失败 {guid}: {e}")
            return None, {}
        return html, images

    @staticmethod
    def _decode_html(data: bytes) -> str:
        """多编码尝试解码 HTML"""
        for enc in _HTML_ENCODINGS:
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="ignore")

    def get_document_attachments(self, guid: str) -> List[WizAttachment]:
        if self._current is None:
            return []
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT ATTACHMENT_GUID, DOCUMENT_GUID, ATTACHMENT_NAME "
                "FROM WIZ_DOCUMENT_ATTACHMENT WHERE DOCUMENT_GUID = ?",
                (guid,),
            ).fetchall()
            return [
                WizAttachment(
                    guid=r["ATTACHMENT_GUID"],
                    document_guid=r["DOCUMENT_GUID"],
                    name=r["ATTACHMENT_NAME"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def download_attachment(self, guid: str, att_guid: str) -> Optional[bytes]:
        """附件获取：优先笔记 .ziw 内部（index_files/ 同名），兜底旧版附件目录"""
        if self._current is None:
            return None
        info = self._doc_path_from_db(guid)
        if info is None:
            return None
        title, location = info
        note_path = self._locate_note_file(title, location, guid)

        atts = self.get_document_attachments(guid)
        name = next((a.name for a in atts if a.guid == att_guid), "")
        if not name:
            return None

        # 1) ZIP 内部查找：优先完整路径匹配，兜底 basename 匹配
        if note_path is not None:
            try:
                with zipfile.ZipFile(note_path, "r") as zf:
                    # 优先：精确路径匹配（如 index_files/<name>）
                    for info in zf.infolist():
                        if info.file_size > _MAX_ZIP_ENTRY_BYTES:
                            continue
                        zname = info.filename
                        if zname.endswith(name) or zname.endswith(f"index_files/{name}"):
                            return zf.read(zname)
                    # 兜底：basename 匹配（仅当无歧义时）
                    basename_matches = []
                    for info in zf.infolist():
                        if info.file_size > _MAX_ZIP_ENTRY_BYTES:
                            continue
                        zname = info.filename
                        if os.path.basename(zname) == name:
                            basename_matches.append(zname)
                    if len(basename_matches) == 1:
                        return zf.read(basename_matches[0])
                    if len(basename_matches) > 1:
                        logger.warning(f"附件名歧义（{len(basename_matches)} 个同名文件），跳过: {name}")
            except Exception as e:  # noqa: BLE001
                logger.debug(f"从笔记 ZIP 读取附件失败 {name}: {e}")

        # 2) 旧版附件目录兜底: {att_guid}{name} / {name} / {att_guid}
        if self._current.attachments_dir is not None:
            att_dir = self._current.attachments_dir
            for cand in (f"{att_guid}{name}", name, att_guid):
                p = self._safe_join(att_dir, cand)
                if p is not None and p.is_file():
                    return p.read_bytes()
        return None
