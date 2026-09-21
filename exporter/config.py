"""配置管理：数据类 + JSON 加载 + CLI 参数覆盖"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from typing import List, Optional


# JSON 配置文件中各字段的期望类型
_TYPE_MAP = {
    "source_type": str,
    "source_dir": str,
    "output_dir": str,
    "preserve_structure": bool,
    "image_strategy": str,
    "add_frontmatter": bool,
    "incremental": bool,
    "max_workers": int,
    "exclude_folders": list,
    "resume": bool,
}

_VALID_IMAGE_STRATEGIES = ("file", "base64")
_MAX_WORKERS_LIMIT = 32
_MIN_DISK_SPACE_MB = 50  # 输出目录至少需要的剩余空间


@dataclass
class ExportConfig:
    """导出配置（最小版只保留 local 路径必需的字段）"""

    # 数据源
    source_type: str = "local"           # 固定为 local
    source_dir: str = ""                 # 为知笔记本地数据目录

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
    resume: bool = False               # 断点续导：跳过已导出的笔记

    def validate(self) -> List[str]:
        """返回配置错误列表，空列表表示合法"""
        errors = []

        # --- 数据源 ---
        if self.source_type != "local":
            errors.append(f"不支持的 source_type: {self.source_type}")
        if not self.source_dir:
            errors.append("local 模式必须指定 source_dir (--input)")
        elif not os.path.isdir(self.source_dir):
            errors.append(f"源目录不存在: {self.source_dir}")

        # --- 输出目录 ---
        if not self.output_dir:
            errors.append("output_dir 不能为空")

        # --- 转换选项 ---
        if self.image_strategy not in _VALID_IMAGE_STRATEGIES:
            errors.append(
                f"image_strategy 必须是 {', '.join(_VALID_IMAGE_STRATEGIES)}，"
                f"当前: {self.image_strategy}")

        # --- 并发 ---
        if not isinstance(self.max_workers, int) or self.max_workers < 1:
            errors.append("max_workers 必须是 >= 1 的整数")
        elif self.max_workers > _MAX_WORKERS_LIMIT:
            errors.append(f"max_workers 不能超过 {_MAX_WORKERS_LIMIT}")

        # --- 列表字段 ---
        if not isinstance(self.exclude_folders, list):
            errors.append("exclude_folders 必须是列表")

        return errors


def validate_output_dir(path: str) -> List[str]:
    """输出目录预检：可创建/可写/磁盘空间，返回错误列表"""
    errors = []
    if not path:
        errors.append("输出目录路径为空")
        return errors

    target = os.path.abspath(path)

    # 找到最近的已有祖先目录来检查权限和磁盘空间
    check_dir = target
    while not os.path.exists(check_dir):
        parent = os.path.dirname(check_dir)
        if parent == check_dir:
            break
        check_dir = parent

    if os.path.exists(check_dir):
        if not os.access(check_dir, os.W_OK):
            errors.append(f"无写入权限: {check_dir}")
        try:
            usage = shutil.disk_usage(check_dir)
            free_mb = usage.free // (1024 * 1024)
            if free_mb < _MIN_DISK_SPACE_MB:
                errors.append(
                    f"磁盘剩余空间不足 ({free_mb} MB < {_MIN_DISK_SPACE_MB} MB)")
        except OSError:
            pass  # 无法检测时不阻断

    # 尝试创建目录（验证路径是否可用）
    try:
        os.makedirs(target, exist_ok=True)
    except OSError as e:
        errors.append(f"无法创建输出目录 {target}: {e}")

    return errors


def load_config(path: Optional[str] = None) -> ExportConfig:
    """加载配置文件，缺失时返回默认配置；自动修正 JSON 中的类型错误"""
    config = ExportConfig()
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, expected in _TYPE_MAP.items():
            if key not in data:
                continue
            val = data[key]
            # bool 在 Python 中是 int 子类，必须先判 bool
            if expected is int and isinstance(val, bool):
                continue  # JSON true/false 不是合法 int，跳过让默认值生效
            if expected is int and isinstance(val, str):
                try:
                    val = int(val)
                except ValueError:
                    continue
            if expected is bool and isinstance(val, str):
                val = val.lower() in ("true", "1", "yes")
            if expected is list and not isinstance(val, list):
                continue
            setattr(config, key, val)
    return config


def merge_cli(config: ExportConfig, args) -> ExportConfig:
    """CLI 参数覆盖配置（仅覆盖显式传入的参数）"""
    mapping = {
        "source_dir": "input",
        "output_dir": "output",
        "image_strategy": "images",
        "max_workers": "workers",
    }
    for attr, cli_name in mapping.items():
        value = getattr(args, cli_name, None)
        if value is not None:
            setattr(config, attr, value)
    # 文件夹过滤：--folders 多值
    if getattr(args, "folders", None):
        config.include_folders = list(args.folders)
    if getattr(args, "no_frontmatter", False):
        config.add_frontmatter = False
    if getattr(args, "flat", False):
        config.preserve_structure = False
    if getattr(args, "incremental", False):
        config.incremental = True
    if getattr(args, "resume", False):
        config.resume = True
    return config
