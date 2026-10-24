from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SETUP_PY = APP_ROOT / "retailedge" / "page" / "retailedge_setup" / "retailedge_setup.py"


class TestRetailEdgeSetupBusinessWording(unittest.TestCase):
	def test_setup_resource_descriptions_do_not_expose_platform_implementation_names(self):
		source = SETUP_PY.read_text(encoding="utf-8")
		self.assertNotIn("Open ERPNext Bank Account", source)
		self.assertNotIn("Open ERPNext Mode of Payment", source)
		self.assertIn("Bank Account records used by RetailEdge payments and reconciliation", source)
		self.assertIn("payment methods used by sales, collections and payments", source)


if __name__ == "__main__":
	unittest.main()
