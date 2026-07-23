from __future__ import annotations

import unittest
from pathlib import Path

import frappe

from retailedge.retailedge.report.pos_closing_variance_vs_expenses import (
	pos_closing_variance_vs_expenses as variance_report,
)


class TestPOSClosingVarianceEdgeUI(unittest.TestCase):
	def app_path(self, *parts: str) -> Path:
		return Path(frappe.get_app_path("retailedge", *parts))

	def test_native_summary_uses_only_closing_summary_rows(self):
		rows = [
			{
				"row_id": "closing::SHIFT-1",
				"shortage": 1500,
				"expenses": 1000,
				"retail_cashier_expense_total": 800,
				"unmatched_shortage": 500,
			},
			{
				"row_id": "closing::SHIFT-1::expense::1",
				"parent_row": "closing::SHIFT-1",
				"shortage": 1500,
				"expenses": 1000,
				"retail_cashier_expense_total": 800,
				"unmatched_shortage": 500,
			},
			{
				"row_id": "closing::SHIFT-2",
				"shortage": 0,
				"expenses": 250,
				"retail_cashier_expense_total": 250,
				"unmatched_shortage": 0,
			},
		]
		cards = {card["label"]: card["value"] for card in variance_report.get_summary(rows)}
		self.assertEqual(cards["Total Shortage"], 1500)
		self.assertEqual(cards["Total Expenses"], 1250)
		self.assertEqual(cards["Total RetailEdge Cashier Expenses"], 1050)
		self.assertEqual(cards["Unmatched Shortage"], 500)

	def test_client_surface_uses_existing_rows_and_shared_render_summary(self):
		path = self.app_path(
			"retailedge",
			"report",
			"pos_closing_variance_vs_expenses",
			"pos_closing_variance_vs_expenses.js",
		)
		content = path.read_text()
		self.assertIn('attachRetailEdgeReportEdgeUI(report, "POS Closing Variance vs Expenses"', content)
		self.assertIn("renderPOSClosingVarianceEdgeUI(report)", content)
		self.assertIn("retailedgeReportEdgeUI.renderSummary", content)
		self.assertIn("!row?.parent_row", content)
		self.assertIn("absoluteAdjustedVariance", content)
		self.assertIn("totalUnmatchedShortage", content)
		self.assertIn("missingBranchCount", content)
		self.assertIn("pendingExpenseCount", content)
		self.assertIn('tree: true', content)
		self.assertIn('name_field: "row_id"', content)
		self.assertIn('parent_field: "parent_row"', content)
		self.assertIn("filters:", content)

	def test_pos_variance_edgeui_phase_contains_no_operational_or_accounting_writes(self):
		path = self.app_path(
			"retailedge",
			"report",
			"pos_closing_variance_vs_expenses",
			"pos_closing_variance_vs_expenses.js",
		)
		content = path.read_text().lower()
		for forbidden in (
			"doc.save(",
			"doc.submit(",
			"frappe.client.save",
			"frappe.db.set_value",
			"frappe.delete_doc",
			"make_payment_entry",
			"make_journal_entry",
			"reconcile_vouchers",
			"create_cashier_expense",
			"submit_closing_shift",
		):
			self.assertNotIn(forbidden, content)
