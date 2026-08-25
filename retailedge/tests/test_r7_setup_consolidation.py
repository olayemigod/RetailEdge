from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestR7SetupConsolidation(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_branch_setup_rejects_cross_company_and_non_leaf_defaults(self):
		source = self.read("branch_profile.py")
		for contract in (
			"COMPANY_LINK_FIELDS",
			"LEAF_FIELDS",
			"_validate_company_links(doc)",
			"_validate_leaf_defaults(doc)",
			'"default_pos_profile": ("POS Profile", "company")',
			'"default_warehouse": ("Warehouse", "company")',
			'"default_cost_center": ("Cost Center", "company")',
			'"default_cash_account": ("Account", "company")',
			"must belong to Company",
			"must be a leaf",
			"must be enabled",
		):
			self.assertIn(contract, source)

	def test_branch_setup_validation_does_not_add_accounting_or_stock_writes(self):
		source = self.read("branch_profile.py")
		for forbidden in (
			"ignore_permissions=True",
			"frappe.db.commit",
			'frappe.new_doc("GL Entry")',
			'frappe.new_doc("Stock Ledger Entry")',
		):
			self.assertNotIn(forbidden, source)


if __name__ == "__main__":
	unittest.main()
