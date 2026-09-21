"""数据源抽象接口"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from exporter.models import WizAttachment, WizDocument


class DataSourceAdapter(ABC):
    """数据源适配器基类

    数据源只需实现 5 个方法，上层管线完全复用。
    """

    name: str = "默认库"

    @abstractmethod
    def discover_sources(self) -> List[str]:
        """发现所有可用库名（个人库 + 群组库）"""
        raise NotImplementedError

    @abstractmethod
    def switch_source(self, name: str) -> bool:
        """切换到指定库（群组），个人库名返回 False 即可"""
        raise NotImplementedError

    @abstractmethod
    def get_all_documents(self) -> List[WizDocument]:
        """获取当前库全部文档元数据（含标签）"""
        raise NotImplementedError

    @abstractmethod
    def get_document_html(self, guid: str) -> Tuple[Optional[str], Dict[str, bytes]]:
        """获取文档内容

        Returns:
            (html_content, images): html 可为 None（笔记文件缺失）；
            images 为 {zip 内路径: bytes}，用于图片引用解析
        """
        raise NotImplementedError

    @abstractmethod
    def get_document_attachments(self, guid: str) -> List[WizAttachment]:
        """获取文档附件列表"""
        raise NotImplementedError

    @abstractmethod
    def download_attachment(self, guid: str, att_guid: str) -> Optional[bytes]:
        """下载附件内容（local 为读取本地文件）"""
        raise NotImplementedError
