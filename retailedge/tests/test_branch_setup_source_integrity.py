from __future__ import annotations

import importlib
import unittest
from pathlib import Path


APP_PACKAGE = Path(__file__).resolve().parents[1]
BRANCH_SETUP_SOURCE = APP_PACKAGE / "branch_setup.py"


class TestBranchSetupSourceIntegrity(unittest.TestCase):
	def test_branch_setup_source_contains_no_null_bytes(self):
		self.assertNotIn(b"\x00", BRANCH_SETUP_SOURCE.read_bytes())

	def test_branch_setup_service_imports(self):
		module = importlib.import_module("retailedge.branch_setup")
		self.assertTrue(callable(module.get_branch_setup_context))
		self.assertTrue(callable(module.save_branch_setup))


if __name__ == "__main__":
	unittest.main()
