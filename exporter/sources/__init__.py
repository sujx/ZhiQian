"""sources 包：数据源工厂"""

from __future__ import annotations

from exporter.config import ExportConfig


def create_source(config: ExportConfig):
    """根据配置创建数据源实例"""
    from exporter.sources.local import LocalSource

    return LocalSource(config.source_dir)
