from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
PATCH = APP_ROOT / "patches" / "ensure_retailedge_cashier_operational_permissions.py"
PATCHES = APP_ROOT / "patches.txt"
FIXTURE = APP_ROOT / "tests" / "browser_persona_fixture.py"


class TestCashierOperationalPermissionBaseline(unittest.TestCase):
	def test_cashier_gets_only_required_operational_master_reads(self):
		source = PATCH.read_text(encoding="utf-8")

		for doctype in (
			"Branch",
			"POS Profile",
			"Warehouse",
			"Mode of Payment",
			"Customer",
			"Item",
			"UOM",
			"Price List",
			"Item Price",
		):
			self.assertIn(f'\t"{doctype}",', source)

		self.assertIn('_grant(doctype, role, ("read", "select"))', source)

	def test_cashier_sales_invoice_authority_is_bounded(self):
		source = PATCH.read_text(encoding="utf-8")

		for permission in ("read", "create", "write", "submit"):
			self.assertIn(f'\t"{permission}",', source)
		self.assertIn('_grant("Sales Invoice", role, SALES_INVOICE_PERMISSIONS)', source)

		for forbidden in (
			'"delete"',
			'"cancel"',
			'"amend"',
			'"Journal Entry"',
			'"GL Entry"',
			'"Payment Entry"',
		):
			self.assertNotIn(forbidden, source)

	def test_cashier_persona_stays_cashier_only(self):
		fixture = FIXTURE.read_text(encoding="utf-8")
		self.assertIn(
			'"browser-cashier@example.com": ("Browser Cashier", ("RetailEdgeCashier",)),',
			fixture,
		)

	def test_patch_is_registered_after_company_visibility_patch(self):
		patches = PATCHES.read_text(encoding="utf-8")
		company_patch = "retailedge.patches.ensure_retailedge_cashier_company_read"
		operational_patch = "retailedge.patches.ensure_retailedge_cashier_operational_permissions"
		self.assertIn(company_patch, patches)
		self.assertIn(operational_patch, patches)
		self.assertLess(patches.index(company_patch), patches.index(operational_patch))


if __name__ == "__main__":
	unittest.main()
