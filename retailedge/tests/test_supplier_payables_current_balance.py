from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from retailedge import supplier_payables

APP_ROOT = Path(__file__).resolve().parents[1]
BUNDLE = APP_ROOT / "public" / "js" / "purchase_reporting.bundle.js"
ACTIONS = APP_ROOT / "reporting_actions.py"


class TestSupplierPayablesCurrentBalance(unittest.TestCase):
	def test_backend_rejects_historical_outstanding_interpretation(self):
		source = inspect.getsource(supplier_payables._current_filters)
		self.assertIn("nowdate()", source)
		self.assertIn("Historical payables as of a past date require ledger reconstruction", source)
		self.assertIn("resolved.as_of_date = today", source)

	def test_response_identifies_current_balance_basis(self):
		source = inspect.getsource(supplier_payables._with_current_balance_metadata)
		self.assertIn('"balance_basis": "current_outstanding"', source)
		self.assertIn('"historical_balance_supported": False', source)
		self.assertIn('"ageing_date": nowdate()', source)

	def test_page_and_export_use_current_balance_service(self):
		bundle = BUNDLE.read_text(encoding="utf-8")
		actions = ACTIONS.read_text(encoding="utf-8")
		self.assertIn("retailedge.supplier_payables.get_supplier_payables", bundle)
		self.assertIn("from retailedge.supplier_payables import get_supplier_payables_export", actions)


if __name__ == "__main__":
	unittest.main()
