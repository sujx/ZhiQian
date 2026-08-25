"""pytest 公共 fixture：fixture 库、mock 服务器、临时输出目录"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

# 允许从项目根导入 exporter 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))

logging.disable(logging.CRITICAL)  # 测试期间静默日志


@pytest.fixture(scope="session")
def wiznote_fixture_dir(tmp_path_factory) -> Path:
    """生成迷你为知笔记库（个人 3 篇 + 群组 1 篇）"""
    from make_fixture_db import main as build_fixture

    out = tmp_path_factory.mktemp("wiznote")
    build_fixture(str(out))
    return out


@pytest.fixture()
def mock_server():
    """启动 mock 为知 API 服务器，返回 base_url"""
    from mock_wiz_api import start_mock_server

    server, base = start_mock_server()
    yield base
    server.shutdown()


@pytest.fixture()
def tmp_output(tmp_path) -> Path:
    """临时输出目录"""
    return tmp_path / "out"
