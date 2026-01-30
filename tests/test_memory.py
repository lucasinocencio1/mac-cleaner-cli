"""Tests for src.memory."""
import unittest

from src.memory import approximate_free_bytes, vm_stat_summary


class TestMemory(unittest.TestCase):
    def test_vm_stat_summary_returns_dict(self) -> None:
        out = vm_stat_summary()
        self.assertIsInstance(out, dict)

    def test_approximate_free_bytes_returns_int(self) -> None:
        n = approximate_free_bytes()
        self.assertIsInstance(n, int)
        self.assertGreaterEqual(n, 0)
