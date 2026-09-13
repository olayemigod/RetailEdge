from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge.stock_accounting_integrity import (
	MAX_MISMATCH_ROWS,
	MAX_REVIEW_WINDOW_DAYS,
	_assert_company_wide_branch_scope,
	_load_native_mismatches,
	_summary,
	_validate_filters,
)

APP_ROOT = Path(__file__).resolve().parents[1]


class TestC22StockAccountingIntegrity(unittest.TestCase):
	def test_date_window_is_required_ordered_and_bounded(self):
		with self.assertRaises(frappe.ValidationError):
			_validate_filters(frappe._dict({"company": "Retail", "from_date": "", "as_on_date": "2026-09-01"}))
		with self.assertRaises(frappe.ValidationError):
			_validate_filters(
				frappe._dict({"company": "Retail", "from_date": "2026-09-02", "as_on_date": "2026-09-01"})
			)
		with self.assertRaises(frappe.ValidationError):
			_validate_filters(
				frappe._dict({"company": "Retail", "from_date": "2025-08-31", "as_on_date": "2026-09-01"})
			)

		filters = frappe._dict({"company": "Retail", "from_date": "2025-09-01", "as_on_date": "2026-09-01"})
		_validate_filters(filters)
		self.assertEqual(MAX_REVIEW_WINDOW_DAYS, 366)

	def test_branch_restricted_multi_branch_company_fails_closed(self):
		with patch(
			"retailedge.stock_accounting_integrity.assert_company_wide_report_scope",
			side_effect=frappe.PermissionError,
		) as scope_guard:
			with self.assertRaises(frappe.PermissionError):
				_assert_company_wide_branch_scope("Retail", user="branch.user@example.com")
		scope_guard.assert_called_once_with("Retail", user="branch.user@example.com")

	def test_single_branch_company_can_pass_company_wide_scope_gate(self):
		with patch("retailedge.stock_accounting_integrity.assert_company_wide_report_scope") as scope_guard:
			_assert_company_wide_branch_scope("Retail", user="branch.user@example.com")
		scope_guard.assert_called_once_with("Retail", user="branch.user@example.com")

	def test_native_erpnext_report_is_the_mismatch_authority(self):
		from erpnext.stock.report.stock_and_account_value_comparison import (
			stock_and_account_value_comparison as native_report,
		)

		filters = frappe._dict(
			{
				"company": "Retail",
				"account": None,
				"from_date": "2026-08-01",
				"as_on_date": "2026-09-01",
			}
		)
		columns = [{"fieldname": "difference_value"}]
		rows = [{"difference_value": 125.5, "stock_value": 500, "account_value": 374.5}]
		with patch.object(native_report, "execute", return_value=(columns, rows)) as execute:
			loaded_columns, loaded_rows = _load_native_mismatches(filters)
		execute.assert_called_once_with(filters)
		self.assertEqual(loaded_columns, columns)
		self.assertEqual(loaded_rows, rows)

	def test_summary_aggregates_only_returned_native_differences(self):
		rows = [
			{"ledger_type": "Stock Ledger Entry", "difference_value": 100},
			{"ledger_type": "GL Entry", "difference_value": -40},
		]
		summary = {entry["label"]: entry["value"] for entry in _summary(rows)}
		self.assertEqual(summary["Mismatched Vouchers"], 2)
		self.assertEqual(summary["Absolute Difference"], 140)
		self.assertEqual(summary["Net Difference"], 60)
		self.assertEqual(summary["Stock-led Exceptions"], 1)
		self.assertEqual(summary["GL-led Exceptions"], 1)
		self.assertEqual(MAX_MISMATCH_ROWS, 5000)

	def test_backend_is_read_only_and_delegates_instead_of_reimplementing_formula(self):
		source = (APP_ROOT / "stock_accounting_integrity.py").read_text()
		self.assertIn("stock_and_account_value_comparison", source)
		self.assertIn("native_report.execute(filters)", source)
		self.assertIn("assert_company_wide_report_scope", source)
		self.assertNotIn("stock_value -", source)
		self.assertNotIn("account_value -", source)
		for forbidden in (
			"create_reposting_entries",
			"Repost Item Valuation",
			".insert(",
			".submit(",
			"ignore_permissions=True",
			"frappe.db.set_value(",
			"frappe.db.commit(",
		):
			self.assertNotIn(forbidden, source)

	def test_edgesuite_page_and_governed_export_contract(self):
		component = (
			APP_ROOT / "public" / "js" / "stock_accounting_integrity" / "StockAccountingIntegrityReport.vue"
		).read_text()
		bundle = (APP_ROOT / "public" / "js" / "stock_accounting_integrity.bundle.js").read_text()
		actions = (APP_ROOT / "reporting_actions.py").read_text()
		capabilities = (APP_ROOT / "reporting_capabilities.py").read_text()
		page = json.loads(
			(APP_ROOT / "retailedge" / "page" / "stock_accounting_integrity" / "stock_accounting_integrity.json").read_text()
		)

		self.assertIn("EdgeAppShell", component)
		self.assertIn("EdgeReportShell", component)
		self.assertIn("EdgeExportMenu", component)
		self.assertIn("Open ERPNext Advanced Report", component)
		self.assertIn("Company-wide accounting control", component)
		self.assertIn("stock-accounting-integrity", bundle)
		self.assertIn('if key == "stock-accounting-integrity":', actions)
		self.assertIn('"stock-accounting-integrity": ReportCapabilitySpec', capabilities)
		self.assertEqual(page["name"], "stock-accounting-integrity")
		self.assertEqual({row["role"] for row in page["roles"]}, {"System Manager", "Stock User", "Accounts Manager"})
		for forbidden in ("frappe.ui.Dialog", "frappe.prompt", "frappe.msgprint", "window.EdgeUI"):
			self.assertNotIn(forbidden, component)


if __name__ == "__main__":
	unittest.main()
