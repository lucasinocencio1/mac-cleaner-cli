"""Tests for src.config."""
import unittest

from src import config as config_module


class TestConfig(unittest.TestCase):
    def test_load_returns_dict(self) -> None:
        cfg = config_module.load()
        self.assertIsInstance(cfg, dict)

    def test_load_has_expected_keys(self) -> None:
        cfg = config_module.load()
        for key in ("exclude_targets", "downloads_days_old", "large_files_mb", "backup_retention_days"):
            self.assertIn(key, cfg)
