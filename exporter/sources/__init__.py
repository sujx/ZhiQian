"""sources 包：数据源工厂"""

from __future__ import annotations

from exporter.config import ExportConfig


def create_source(config: ExportConfig):
    """根据配置创建数据源实例"""
    if config.source_type == "local":
        from exporter.sources.local import LocalSource

        return LocalSource(config.source_dir)
    elif config.source_type == "webapi":
        from exporter.sources.webapi.source import WebAPISource

        return WebAPISource(config.username, config.password, config.as_url)
    else:
        raise ValueError(f"不支持的 source_type: {config.source_type}")
