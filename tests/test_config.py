"""Tests for configuration module."""

import json
import os
import tempfile
import pytest
from pathlib import Path
from sqlink.config import Config, find_config, CONFIG_FILENAME


class TestConfig:
    def test_defaults(self):
        c = Config()
        assert c.max_joins == 5
        assert c.disabled_rules == []
        assert c.output_format == "text"
        assert c.color is True

    def test_to_dict(self):
        c = Config(max_joins=3, disabled_rules=["SQ001"])
        d = c.to_dict()
        assert d["max_joins"] == 3
        assert d["disabled_rules"] == ["SQ001"]

    def test_from_dict(self):
        c = Config.from_dict({"max_joins": 10, "color": False})
        assert c.max_joins == 10
        assert c.color is False

    def test_from_dict_defaults(self):
        c = Config.from_dict({})
        assert c.max_joins == 5

    def test_roundtrip(self):
        c = Config(max_joins=7, disabled_rules=["SQ001", "WH002"], output_format="json")
        d = c.to_dict()
        c2 = Config.from_dict(d)
        assert c2.max_joins == 7
        assert c2.disabled_rules == ["SQ001", "WH002"]
        assert c2.output_format == "json"

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / CONFIG_FILENAME
            c = Config(max_joins=3, disabled_rules=["SQ001"])
            c.save(path)
            assert path.exists()

            loaded = Config.load(path)
            assert loaded.max_joins == 3
            assert loaded.disabled_rules == ["SQ001"]

    def test_load_nonexistent(self):
        c = Config.load("/nonexistent/path/.sqlink.json")
        assert c.max_joins == 5  # defaults

    def test_merge(self):
        c1 = Config(max_joins=5, disabled_rules=["SQ001"])
        c2 = Config(max_joins=10, disabled_rules=["WH002"])
        merged = c1.merge(c2)
        assert merged.max_joins == 10
        assert "SQ001" in merged.disabled_rules
        assert "WH002" in merged.disabled_rules

    def test_merge_preserves_original(self):
        c1 = Config(max_joins=5)
        c2 = Config(max_joins=10)
        merged = c1.merge(c2)
        assert c1.max_joins == 5  # unchanged


class TestFindConfig:
    def test_finds_in_current_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text(json.dumps({"max_joins": 7}))
            c = find_config(tmpdir)
            assert c.max_joins == 7

    def test_finds_in_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / CONFIG_FILENAME
            config_path.write_text(json.dumps({"max_joins": 8}))
            subdir = Path(tmpdir) / "sub"
            subdir.mkdir()
            c = find_config(subdir)
            assert c.max_joins == 8

    def test_returns_defaults_when_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            c = find_config(tmpdir)
            assert c.max_joins == 5

    def test_severity_threshold(self):
        c = Config(severity_threshold="error")
        assert c.severity_threshold == "error"
