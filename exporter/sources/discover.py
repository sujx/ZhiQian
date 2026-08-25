"""自动发现为知笔记数据目录

扫描常见安装位置（跨平台：用户文档目录、主目录、
macOS Application Support、Linux 隐藏目录、Windows 盘符根目录），
浅层验证目录下存在 index.db 后返回。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# 常见目录名（新版英文 + 旧版中文）
_DIR_NAMES = ["My Knowledge", "我的知识库", "WizNote"]
_MAX_SCAN_DEPTH = 4


def _has_index_db(dirpath: Path, max_depth: int = _MAX_SCAN_DEPTH) -> bool:
    """浅层扫描目录，判断是否含 index.db"""
    root_depth = len(dirpath.parts)
    try:
        for dpath, dirnames, filenames in os.walk(dirpath):
            depth = len(Path(dpath).parts) - root_depth
            if depth > max_depth:
                dirnames[:] = []
                continue
            if "index.db" in filenames:
                return True
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(".")
                           and d != ".wizfulltextindex"]
    except OSError:
        return False
    return False


def find_wiznote_dirs() -> List[str]:
    """扫描常见位置，返回所有含 index.db 的为知笔记数据目录（去重）"""
    home = Path.home()
    candidates: List[Path] = []

    # 1) 用户文档目录（跨平台）
    docs = home / "Documents"
    for name in _DIR_NAMES:
        candidates.append(docs / name)
    # 2) 用户主目录（跨平台）
    for name in _DIR_NAMES:
        candidates.append(home / name)
    # 3) macOS 特定位置
    if sys.platform == "darwin":
        app_support = home / "Library" / "Application Support"
        candidates.extend([
            app_support / "WizNote",
            app_support / "wiznote",
            home / "WizNote",
        ])
    # 4) Linux 特定位置
    elif sys.platform.startswith("linux"):
        candidates.extend([home / ".wiznote", home / "WizNote"])
    # 5) 各盘符根目录（仅 Windows）
    if os.name == "nt":
        for letter in "CDEFGH":
            drive = Path(f"{letter}:/")
            if drive.exists():
                for name in _DIR_NAMES:
                    candidates.append(drive / name)

    found: List[Path] = []
    for cand in candidates:
        if cand.is_dir() and _has_index_db(cand) and cand not in found:
            logger.info(f"发现为知笔记数据目录: {cand}")
            found.append(cand)

    return [str(p) for p in found]
