from __future__ import annotations

import unittest
from pathlib import Path

import frappe

from retailedge import hooks
from retailedge.report_edgeui import EDGESUITE_METADATA_FLAG, build_filter_summary, build_report_metadata
from retailedge.retailedge.report.retailedge_branch_performance_summary import (
	retailedge_branch_performance_summary as branch_report,
)
from retailedge.retailedge.report.retailedge_cashier_expense_review import (
	retailedge_cashier_expense_review as expense_report,
)
from retailedge.retailedge.report.retailedge_daily_sales_audit_register import (
	retailedge_daily_sales_audit_register as audit_report,
)


class TestRetailEdgeReportEdgeUI(unittest.TestCase):
	def app_path(self, *parts: str) -> Path:
		return Path(frappe.get_app_path("retailedge", *parts))

	def test_hooks_load_report_surface_after_foundation_assets(self):
		self.assertIn(
			"/assets/retailedge/css/retailedge_report_edgeui.css",
			hooks.app_include_css,
		)
		self.assertIn(
			"/assets/retailedge/js/retailedge_report_edgeui.js",
			hooks.app_include_js,
		)
		self.assertLess(
			hooks.app_include_js.index("/assets/retailedge/js/retailedge_ui_bridge.js"),
			hooks.app_include_js.index("/assets/retailedge/js/retailedge_report_edgeui.js"),
		)

	def test_adapter_is_fail_open_and_preserves_native_report_surface(self):
		adapter = self.app_path("public", "js", "retailedge_report_edgeui.js").read_text()
		for component in (
			"EdgePageHeader",
			"EdgeDashboardLayout",
			"EdgeStatCard",
			"EdgeStatusBadge",
			"EdgeEmptyState",
			"EdgeIcon",
		):
			self.assertIn(component, adapter)
		self.assertIn("show_and_render_summary", adapter)
		self.assertIn("fallback(extracted.cards)", adapter)
		self.assertIn("showNativeSummary(report)", adapter)
		self.assertNotIn("coreedge/public", adapter.lower())
		self.assertNotIn("frappe.client.save", adapter)

	def test_pilot_reports_register_and_attach_to_shared_adapter(self):
		paths = {
			"RetailEdge Branch Performance Summary": self.app_path(
				"retailedge",
				"report",
				"retailedge_branch_performance_summary",
				"retailedge_branch_performance_summary.js",
			),
			"RetailEdge Cashier Expense Review": self.app_path(
				"retailedge",
				"report",
				"retailedge_cashier_expense_review",
				"retailedge_cashier_expense_review.js",
			),
			"RetailEdge Daily Sales Audit Register": self.app_path(
				"retailedge",
				"report",
				"retailedge_daily_sales_audit_register",
				"retailedge_daily_sales_audit_register.js",
			),
		}
		for report_name, path in paths.items():
			content = path.read_text()
			self.assertIn(f'attachRetailEdgeReportEdgeUI(report, "{report_name}"', content)
			self.assertIn(f'retailedgeReportEdgeUI?.refresh(report, "{report_name}")', content)
			self.assertIn("filters:", content)

	def test_filter_summary_is_compact_and_context_aware(self):
		summary = build_filter_summary(
			{
				"from_date": "2026-07-01",
				"to_date": "2026-07-31",
				"company": "ProcessEdge Retail",
				"branch": "Abuja",
				"only_pos_invoices": 1,
			},
			(
				("company", "Company"),
				("branch", "Branch"),
				("only_pos_invoices", "Only POS Invoices"),
			),
		)
		self.assertIn("2026-07-01 to 2026-07-31", summary)
		self.assertIn("Company: ProcessEdge Retail", summary)
		self.assertIn("Branch: Abuja", summary)
		self.assertIn("Only POS Invoices", summary)

	def test_metadata_marker_is_not_a_normal_summary_card(self):
		metadata = build_report_metadata(
			title="Test Report",
			icon="report",
			filters={},
			filter_fields=(),
			row_count=2,
			empty_message="No records",
		)
		self.assertEqual(metadata[EDGESUITE_METADATA_FLAG], 1)
		self.assertEqual(metadata["row_count"], 2)
		self.assertEqual(metadata["filter_summary"], "All permitted records")

	def test_branch_performance_summary_and_recommendations_use_report_rows(self):
		rows = [
			{
				"invoice_count": 3,
				"gross_sales": 120000,
				"cashier_expenses": 5000,
				"net_cash_expected": 70000,
				"outstanding_amount": 20000,
				"audit_variance": -1500,
				"payment_issues": 2,
			}
		]
		cards = branch_report.get_report_summary(rows)
		metadata = branch_report.get_edgesuite_metadata({}, rows)
		labels = {card["label"] for card in cards}
		self.assertIn("Credit / Outstanding", labels)
		self.assertIn("Net Cash Expected", labels)
		self.assertEqual(metadata["row_count"], 1)
		self.assertGreaterEqual(len(metadata["recommendations"]), 3)

	def test_expense_metadata_excludes_totals_row(self):
		rows = [
			{
				"name": "RE-EXP-1",
				"amount": 5000,
				"expense_status": "Pending Ledger",
				"daily_audit_inclusion_status": "Needs Clarification",
				"posting_ready": 0,
			},
			{"_is_totals_row": 1, "name": "Totals", "amount": 5000},
		]
		metadata = expense_report.get_edgesuite_metadata({}, rows)
		self.assertEqual(metadata["row_count"], 1)
		titles = {item["title"] for item in metadata["recommendations"]}
		self.assertIn("Request clarification", titles)
		self.assertIn("Resolve posting blockers", titles)
		self.assertIn("Complete ledger handoff", titles)

	def test_daily_audit_summary_uses_absolute_variance(self):
		rows = [
			{
				"cash_sales_amount": 100000,
				"expected_cash_amount": 90000,
				"actual_closing_cash_amount": 88000,
				"net_variance_amount": -2000,
				"review_required": 1,
				"clarification_required": 1,
			},
			{
				"cash_sales_amount": 50000,
				"expected_cash_amount": 45000,
				"actual_closing_cash_amount": 46000,
				"net_variance_amount": 1000,
				"review_required": 0,
				"clarification_required": 0,
			},
		]
		cards = {card["label"]: card["value"] for card in audit_report.get_report_summary(rows)}
		metadata = audit_report.get_edgesuite_metadata({}, rows)
		self.assertEqual(cards["Absolute Variance"], 3000)
		self.assertEqual(cards["Review Required"], 1)
		self.assertEqual(cards["Clarification Required"], 1)
		self.assertEqual(metadata["row_count"], 2)

	def test_report_phase_contains_no_document_write_operations(self):
		paths = [
			self.app_path("report_edgeui.py"),
			self.app_path("public", "js", "retailedge_report_edgeui.js"),
			self.app_path(
				"retailedge",
				"report",
				"retailedge_branch_performance_summary",
				"retailedge_branch_performance_summary.py",
			),
			self.app_path(
				"retailedge",
				"report",
				"retailedge_cashier_expense_review",
				"retailedge_cashier_expense_review.py",
			),
			self.app_path(
				"retailedge",
				"report",
				"retailedge_daily_sales_audit_register",
				"retailedge_daily_sales_audit_register.py",
			),
		]
		combined = "\n".join(path.read_text().lower() for path in paths)
		for forbidden in (
			"doc.save(",
			"doc.submit(",
			"frappe.client.save",
			"frappe.db.set_value",
			"frappe.delete_doc",
		):
			self.assertNotIn(forbidden, combined)
