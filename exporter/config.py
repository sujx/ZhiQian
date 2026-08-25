"""配置管理：数据类 + JSON 加载 + CLI 参数覆盖"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class ExportConfig:
    """导出配置（最小版只保留 local 路径必需的字段）"""

    # 数据源
    source_type: str = "local"           # local | webapi
    source_dir: str = ""                 # local: 为知笔记数据目录
    username: str = ""                   # webapi: 账号
    password: str = ""                   # webapi: 密码
    as_url: str = "https://as.wiz.cn"    # webapi: AS 服务器
    kb_guid: str = ""                    # webapi: 知识库 GUID（空=个人库）
    include_folders: List[str] = field(default_factory=list)  # webapi: 限定文件夹

    # 输出
    output_dir: str = "./notes"
    preserve_structure: bool = True

    # 转换
    image_strategy: str = "file"         # file | base64（最小版仅 file）
    add_frontmatter: bool = True

    # 高级
    incremental: bool = False
    max_workers: int = 4               # 并发导出线程数（1 = 串行）
    exclude_folders: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        """返回配置错误列表，空列表表示合法"""
        errors = []
        if self.source_type not in ("local", "webapi"):
            errors.append(f"不支持的 source_type: {self.source_type}")
        if self.source_type == "local":
            if not self.source_dir:
                errors.append("local 模式必须指定 source_dir (--input)")
            if not os.path.isdir(self.source_dir):
                errors.append(f"源目录不存在: {self.source_dir}")
        else:
            if not self.username:
                errors.append("webapi 模式必须指定用户名 (--username)")
            if not self.password:
                errors.append("webapi 模式必须指定密码 (--password)")
        if self.max_workers < 1:
            errors.append("max_workers 必须 >= 1")
        return errors


def load_config(path: Optional[str] = None) -> ExportConfig:
    """加载配置文件，缺失时返回默认配置"""
    config = ExportConfig()
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in asdict(config):
            if key in data:
                setattr(config, key, data[key])
    return config


def merge_cli(config: ExportConfig, args) -> ExportConfig:
    """CLI 参数覆盖配置（仅覆盖显式传入的参数）"""
    mapping = {
        "source_type": "source",
        "source_dir": "input",
        "output_dir": "output",
        "image_strategy": "images",
        "max_workers": "workers",
        "username": "username",
        "password": "password",
        "as_url": "as_url",
        "kb_guid": "kb",
    }
    for attr, cli_name in mapping.items():
        value = getattr(args, cli_name, None)
        if value is not None:
            setattr(config, attr, value)
    # webapi 模式：未显式指定 --workers 时默认 2（网络 IO，避免触发 API 限流）
    if (config.source_type == "webapi"
            and getattr(args, "workers", None) is None
            and config.max_workers == 4):
        config.max_workers = 2
    # 文件夹过滤：--folders 多值
    if getattr(args, "folders", None):
        config.include_folders = list(args.folders)
    if getattr(args, "no_frontmatter", False):
        config.add_frontmatter = False
    if getattr(args, "flat", False):
        config.preserve_structure = False
    if getattr(args, "incremental", False):
        config.incremental = True
    return config
