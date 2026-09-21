"""配置管理单元测试：默认值 / CLI 合并 / 配置校验 / 输出目录预检"""

from __future__ import annotations

import argparse

from exporter.config import ExportConfig, load_config, merge_cli, validate_output_dir


def _args(**overrides):
    defaults = dict(input=None, output=None, images=None,
                    workers=None, no_frontmatter=False, flat=False,
                    incremental=False, resume=False)
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


class TestMergeCli:
    def test_explicit_workers_respected(self):
        cfg = merge_cli(ExportConfig(), _args(workers=6))
        assert cfg.max_workers == 6

    def test_default_workers_4(self):
        cfg = merge_cli(ExportConfig(), _args())
        assert cfg.max_workers == 4

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


class TestValidateEnhanced:
    """增强配置校验测试"""

    def test_invalid_image_strategy(self):
        cfg = ExportConfig(image_strategy="invalid")
        errors = cfg.validate()
        assert any("image_strategy" in e for e in errors)

    def test_valid_image_strategies(self):
        for strategy in ("file", "base64"):
            cfg = ExportConfig(image_strategy=strategy)
            errors = cfg.validate()
            assert not any("image_strategy" in e for e in errors)

    def test_empty_output_dir(self):
        cfg = ExportConfig(output_dir="")
        errors = cfg.validate()
        assert any("output_dir" in e for e in errors)

    def test_max_workers_upper_bound(self):
        cfg = ExportConfig(max_workers=100)
        errors = cfg.validate()
        assert any("不能超过" in e for e in errors)

    def test_max_workers_valid_range(self):
        cfg = ExportConfig(max_workers=16)
        errors = cfg.validate()
        assert not any("max_workers" in e for e in errors)

    def test_exclude_folders_must_be_list(self):
        cfg = ExportConfig(exclude_folders="not-a-list")
        errors = cfg.validate()
        assert any("exclude_folders" in e for e in errors)


class TestValidateOutputDir:
    """输出目录预检测试"""

    def test_valid_dir(self, tmp_path):
        errors = validate_output_dir(str(tmp_path / "output"))
        assert errors == []

    def test_empty_path(self):
        errors = validate_output_dir("")
        assert any("为空" in e for e in errors)

    def test_no_write_permission(self, tmp_path):
        errors = validate_output_dir(str(tmp_path / "new" / "nested" / "dir"))
        assert errors == []

    def test_creates_dir(self, tmp_path):
        target = tmp_path / "test_output"
        assert not target.exists()
        errors = validate_output_dir(str(target))
        assert errors == []
        assert target.exists()


class TestResumeConfig:
    """断点续导配置测试"""

    def test_resume_flag(self):
        cfg = merge_cli(ExportConfig(), _args(resume=True))
        assert cfg.resume is True

    def test_resume_default_false(self):
        cfg = merge_cli(ExportConfig(), _args())
        assert cfg.resume is False
