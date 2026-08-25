"""配置管理单元测试：默认值 / CLI 合并 / webapi 默认并发 2"""

from __future__ import annotations

import argparse

from exporter.config import ExportConfig, load_config, merge_cli


def _args(**overrides):
    defaults = dict(source=None, input=None, output=None, images=None,
                    workers=None, username=None, password=None, as_url=None,
                    kb=None, folders=None, no_frontmatter=False, flat=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestDefaults:
    def test_local_default(self):
        cfg = ExportConfig()
        assert cfg.source_type == "local"
        assert cfg.max_workers == 4
        assert cfg.image_strategy == "file"

    def test_validate_local_requires_dir(self):
        cfg = ExportConfig()
        errors = cfg.validate()
        assert any("source_dir" in e for e in errors)

    def test_validate_webapi_requires_credentials(self):
        cfg = ExportConfig(source_type="webapi")
        errors = cfg.validate()
        assert any("用户名" in e for e in errors)
        assert any("密码" in e for e in errors)


class TestMergeCli:
    def test_webapi_default_workers_2(self):
        cfg = merge_cli(ExportConfig(), _args(source="webapi", username="u",
                                              password="p"))
        assert cfg.max_workers == 2

    def test_explicit_workers_respected(self):
        cfg = merge_cli(ExportConfig(),
                        _args(source="webapi", username="u", password="p",
                              workers=6))
        assert cfg.max_workers == 6

    def test_local_workers_4(self):
        cfg = merge_cli(ExportConfig(), _args(source="local", input="x"))
        assert cfg.max_workers == 4

    def test_folders_parsed(self):
        cfg = merge_cli(ExportConfig(), _args(folders=["/a/", "/b/"]))
        assert cfg.include_folders == ["/a/", "/b/"]

    def test_flat_flag(self):
        cfg = merge_cli(ExportConfig(), _args(flat=True))
        assert cfg.preserve_structure is False


class TestLoadConfig:
    def test_load_example(self):
        import os
        example = os.path.join(os.path.dirname(__file__), "..", "config.example.json")
        cfg = load_config(example)
        assert cfg.source_type == "local"
        assert cfg.max_workers == 4
        assert cfg.include_folders == []
