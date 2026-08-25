"""WebAPISource：在线 API 数据源（实现 DataSourceAdapter 接口）

流程: 登录 → 知识库列表(discover_sources) → 切换知识库(switch_source)
      → 遍历文件夹拉取笔记(get_all_documents) → 下载笔记HTML/附件
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from exporter.models import WizAttachment, WizDocument
from exporter.sources.base import DataSourceAdapter
from exporter.sources.webapi.auth import WizNoteAuth
from exporter.sources.webapi.client import WizNoteAPIClient

logger = logging.getLogger(__name__)


class WebAPISource(DataSourceAdapter):
    """在线 API 数据源"""

    name = "在线知识库"

    def __init__(self, username: str, password: str, as_url: str):
        self.auth = WizNoteAuth(username, password, as_url)
        self.client: Optional[WizNoteAPIClient] = None
        self._folders: List[str] = []
        self._logged_in = False

    # ---------- 登录 ----------

    def login(self) -> bool:
        if self.auth.login():
            self._logged_in = True
            self._use_kb(self.auth.kb_guid, self.auth.kb_server)
            return True
        return False

    def _use_kb(self, kb_guid: str, kb_server: str) -> None:
        from exporter.sources.webapi.client import WizNoteAPIClient

        self.client = WizNoteAPIClient(self.auth, kb_guid, kb_server)
        self._folders = self.client.get_all_folders()

    # ---------- 数据源接口 ----------

    def discover_sources(self) -> List[str]:
        """返回知识库名称列表（需先 login）"""
        if not self._logged_in:
            self.login()
        return [kb["name"] for kb in self.auth.get_kb_list()]

    def switch_source(self, name: str) -> bool:
        """切换知识库（按名称）"""
        for kb in self.auth.get_kb_list():
            if kb["name"] == name:
                self.auth.switch_kb(kb["kbGuid"])
                self._use_kb(kb["kbGuid"], kb["kbServer"])
                return True
        return False

    def select_kb(self, kb_guid: str) -> bool:
        """按 GUID 选择知识库（CLI --kb / GUI 下拉用）"""
        for kb in self.auth.get_kb_list():
            if kb["kbGuid"] == kb_guid:
                self.auth.switch_kb(kb_guid)
                self._use_kb(kb_guid, kb["kbServer"])
                return True
        return False

    def get_folder_list(self) -> List[str]:
        """返回当前知识库的文件夹列表（供 GUI 展示/选择）"""
        if self.client is None:
            return []
        return list(self._folders)

    def get_all_documents(self, folders: Optional[List[str]] = None) -> List[WizDocument]:
        """拉取当前知识库全部（或指定文件夹）笔记元数据"""
        if self.client is None:
            return []
        target = folders if folders else self._folders
        docs: List[WizDocument] = []
        for folder in target:
            for note in self.client.get_all_notes_in_folder(folder):
                guid = note.get("docGuid") or note.get("guid", "")
                docs.append(WizDocument(
                    guid=guid,
                    title=note.get("title") or "无标题",
                    location=folder,
                    modified=self._parse_ts(note.get("dataModified")),
                    source_name=self.auth.kb_list[0]["name"]
                    if self.auth.kb_list else "在线知识库",
                ))
        return docs

    @staticmethod
    def _parse_ts(value) -> Optional[object]:
        if not value:
            return None
        from datetime import datetime
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    def get_document_html(self, guid: str) -> Tuple[Optional[str], Dict[str, bytes]]:
        """下载笔记，返回 (html, {}) — 在线资源随 HTML 引用"""
        if self.client is None:
            return None, {}
        data = self.client.download_note(guid)
        if not data:
            return None, {}
        html = data.get("html", "")
        return html or None, {}

    def get_document_attachments(self, guid: str) -> List[WizAttachment]:
        """在线 API 附件列表需额外接口，暂返回空（附件随下载跳过）"""
        return []

    def download_attachment(self, guid: str, att_guid: str) -> Optional[bytes]:
        return None
