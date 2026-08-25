"""数据模型定义（无第三方依赖，最先可测试）"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class WizDocument:
    """为知笔记文档元数据"""

    guid: str
    title: str
    location: str = "/"                # 文件夹路径，如 /技术/前端
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    attachment_count: int = 0
    source_name: str = "个人笔记"       # 所属库名（个人/群组）

    @property
    def folder_parts(self) -> List[str]:
        """location 拆分后的目录层级（不含根）"""
        return [p for p in self.location.strip("/").split("/") if p]


@dataclass
class WizAttachment:
    """为知笔记附件"""

    guid: str
    document_guid: str
    name: str


@dataclass
class ExportStats:
    """导出统计"""

    total: int = 0
    success: int = 0
    failed: int = 0
    skipped_images: int = 0
    attachments: int = 0
    failures: List[dict] = field(default_factory=list)

    def record_failure(self, title: str, guid: str, error: str) -> None:
        self.failures.append({"title": title, "guid": guid, "error": str(error)})

    def summary(self) -> str:
        lines = [
            "=" * 40,
            "导出完成",
            "=" * 40,
            f"总笔记数: {self.total}",
            f"成功导出: {self.success}",
            f"失败数量: {self.failed}",
            f"跳过图片附件: {self.skipped_images}",
            f"复制附件: {self.attachments}",
        ]
        if self.failures:
            lines.append(f"\n失败明细 ({len(self.failures)} 条):")
            for f in self.failures[:10]:
                lines.append(f"  - {f['title']}: {f['error']}")
            if len(self.failures) > 10:
                lines.append(f"  ... 还有 {len(self.failures) - 10} 条")
        return "\n".join(lines)
