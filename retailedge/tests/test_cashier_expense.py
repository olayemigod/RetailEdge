from __future__ import annotations

from datetime import datetime
import json
from types import SimpleNamespace
from unittest.mock import patch

import retailedge.tests._cashier_expense_regression_suite as _legacy
from retailedge.tests._cashier_expense_regression_suite import *


def _set_up_cashier_expense_service_read_permission(self):
	self._cashier_expense_read_permission = patch(
		"retailedge.cashier_expense_read_scope.frappe.has_permission",
		return_value=True,
	)
	self._cashier_expense_global_branch_access = patch(
		"retailedge.cashier_expense_read_scope.user_has_global_branch_access",
		return_value=True,
	)
	self._cashier_expense_read_permission.start()
	self._cashier_expense_global_branch_access.start()
	self.addCleanup(self._cashier_expense_global_branch_access.stop)
	self.addCleanup(self._cashier_expense_read_permission.stop)


_legacy.CashierExpenseServiceTests.setUp = _set_up_cashier_expense_service_read_permission


class CashierContextTests(_legacy.CashierContextTests):
	@patch("retailedge.cashier_context.resolve_cash_payment_account")
	@patch("retailedge.cashier_context._get_shift_window")
	@patch("retailedge.cashier_context._coerce_doc")
	@patch("retailedge.cashier_context.frappe.get_meta")
	@patch("retailedge.cashier_context.frappe.get_all")
	@patch(
		"retailedge.cashier_context._has_doctype",
		side_effect=lambda doctype: doctype in {"Sales Invoice", "Sales Invoice Payment", "Payment Entry"},
	)
	def test_get_shift_cash_sales_ignores_non_cash_and_cancelled_invoices(
		self,
		_mock_has_doctype,
		mock_get_all,
		mock_get_meta,
		mock_coerce_doc,
		mock_shift_window,
		mock_payment_account,
	):
		opening_shift = SimpleNamespace(
			doctype="POS Opening Shift",
			name="OPEN-1",
			company="Demo Company",
			pos_profile="PROFILE-1",
			user="cashier@example.com",
			period_start_date=datetime(2026, 5, 11, 9, 0, 0),
		)
		invoice = SimpleNamespace(
			doctype="Sales Invoice",
			name="SINV-1",
			posting_date=datetime(2026, 5, 11, 10, 0, 0),
			posting_time=None,
			payments=[
				_legacy._Row(mode_of_payment="Card", account="Bank - DEMO", amount=200, base_amount=200),
			],
		)
		mock_shift_window.return_value = {
			"opening_shift": opening_shift,
			"closing_shift": None,
			"company": "Demo Company",
			"pos_profile": "PROFILE-1",
			"user": "cashier@example.com",
			"shift_start": datetime(2026, 5, 11, 9, 0, 0),
			"shift_end": datetime(2026, 5, 11, 11, 0, 0),
		}

		def _meta_for(doctype):
			if doctype == "Sales Invoice":
				return SimpleNamespace(
					has_field=lambda field: field
					in {"payments", "is_pos", "company", "posa_pos_opening_shift", "pos_profile"}
				)
			if doctype == "Sales Invoice Payment":
				return SimpleNamespace(
					has_field=lambda field: field in {"mode_of_payment", "account", "amount", "base_amount"}
				)
			return SimpleNamespace(has_field=lambda field: False)

		mock_get_meta.side_effect = _meta_for

		def _fake_get_all(doctype, filters=None, fields=None, **kwargs):
			if doctype == "Sales Invoice":
				return [SimpleNamespace(name="SINV-1")]
			if doctype == "Payment Entry":
				return []
			return []

		mock_get_all.side_effect = _fake_get_all
		mock_coerce_doc.return_value = invoice
		mock_payment_account.return_value = {
			"payment_account": "Cash - DEMO",
			"mode_of_payment": "Cash",
			"source": "mode_of_payment_account",
			"message": None,
		}
		result = get_shift_cash_sales(opening_shift="OPEN-1", company="Demo Company", pos_profile="PROFILE-1")
		self.assertEqual(result["cash_sales"], 0)
		self.assertEqual(result["matched_invoice_count"], 1)
		self.assertEqual(result["matched_payment_count"], 0)
		self.assertEqual(result["source"], "sales_invoice.posa_pos_opening_shift")
		self.assertIsNone(result["message"])


R2_NATIVE_SECTIONS = [
	"Home",
	"Point of Sale",
	"Sales",
	"Purchases",
	"Stock",
	"Money & Banking",
	"Expenses",
	"Customers",
	"Suppliers & Payables",
	"Operations Review",
	"Banking & Reconciliation",
	"Insights & Dashboards",
	"Reports",
	"Selling Setup",
	"Stock Setup",
	"Finance Setup",
	"Business Setup",
]

R2_FORBIDDEN_NATIVE_TARGETS = {
	"Journal Entry",
	"RetailEdge Bank Match Batch Job",
	"Error Log",
	"RetailEdge Branch Profile User",
	"Item Group",
	"UOM",
}

R2_REQUIRED_LINKS = {
	"Business Hub": ("Page", "retailedge-business-hub"),
	"Sales Invoices": ("DocType", "Sales Invoice"),
	"Purchase Operations": ("Page", "professional-purchasing"),
	"Payments": ("DocType", "Payment Entry"),
	"Cashier Expenses": ("Page", "cashier-expenses"),
	"Customers": ("DocType", "Customer"),
	"Suppliers": ("DocType", "Supplier"),
	"Reports Centre": ("Page", "reports-centre"),
	"Branch Performance": ("Page", "branch-performance-dashboard"),
	"Salesperson Performance": ("Page", "salesperson-performance-dashboard"),
	"Daily Sales Audit": ("Page", "daily-sales-audit"),
	"Bank Matching & Reconciliation": ("Page", "bank-matching-reconciliation"),
	"Banking Readiness": ("Page", "banking-readiness"),
	"Stock Position": ("Page", "stock-position"),
	"Stock Locations": ("DocType", "Warehouse"),
	"Settings": ("DocType", "RetailEdge Settings"),
	"Branch Setup": ("DocType", "RetailEdge Branch Profile"),
}

R2_SHORTCUTS = [
	"Business Hub",
	"Start POS",
	"Sales Invoices",
	"Purchase Operations",
	"Payments",
	"Cashier Expenses",
	"Reports Centre",
	"Branch Performance",
]


class BranchProfileTests(_legacy.BranchProfileTests):
	def test_workspace_json_contains_required_order_and_labels(self):
		path = _legacy.APP_ROOT / "retailedge/workspace/retailedge/retailedge.json"
		data = json.loads(path.read_text())
		links = data.get("links", [])

		sections = [row.get("label") for row in links if row.get("type") == "Card Break"]
		self.assertEqual(sections, R2_NATIVE_SECTIONS)
		for row in links:
			if row.get("type") == "Card Break":
				self.assertEqual(row.get("close"), 1, f"Section {row.get('label')} must start collapsed.")

		link_rows = [row for row in links if row.get("type") == "Link"]
		by_label = {row.get("label"): row for row in link_rows}
		for label, (link_type, target) in R2_REQUIRED_LINKS.items():
			self.assertIn(label, by_label)
			self.assertEqual(by_label[label].get("link_type"), link_type)
			self.assertEqual(by_label[label].get("link_to"), target)

		targets = [(row.get("link_type"), row.get("link_to")) for row in link_rows if row.get("link_to")]
		self.assertEqual(len(targets), len(set(targets)))
		self.assertFalse(R2_FORBIDDEN_NATIVE_TARGETS.intersection({target for _, target in targets}))
		self.assertFalse(
			[
				row
				for row in link_rows
				if "edgepay" in str(row.get("label") or "").lower()
				or "edgepay" in str(row.get("link_to") or "").lower()
			]
		)

		shortcut_labels = [row.get("label") for row in data.get("shortcuts", [])]
		self.assertEqual(shortcut_labels, R2_SHORTCUTS)

	def test_standard_workspace_sidebar_json_exists_and_is_grouped(self):
		paths = [
			_legacy.APP_ROOT / "workspace_sidebar/retailedge.json",
			_legacy.APP_ROOT / "retailedge/workspace_sidebar/retailedge/retailedge.json",
		]
		for path in paths:
			self.assertTrue(path.exists(), f"Missing standard sidebar fixture: {path}")

		sidebars = [json.loads(path.read_text()) for path in paths]
		self.assertEqual(sidebars[0], sidebars[1])
		data = sidebars[0]
		self.assertEqual(data.get("doctype"), "Workspace Sidebar")
		self.assertEqual(data.get("app"), "retailedge")
		self.assertEqual(data.get("standard"), 1)

		items = data.get("items", [])
		sections = [row.get("label") for row in items if row.get("type") == "Section Break"]
		self.assertEqual(sections, R2_NATIVE_SECTIONS)
		for row in items:
			if row.get("type") == "Section Break":
				self.assertEqual(
					row.get("keep_closed"), 1, f"Sidebar section {row.get('label')} must start collapsed."
				)

		self.assertEqual(items[0].get("label"), "Home")
		self.assertEqual(items[0].get("link_type"), "Workspace")
		self.assertEqual(items[0].get("link_to"), "RetailEdge")

		link_rows = [row for row in items[1:] if row.get("type") == "Link"]
		by_label = {row.get("label"): row for row in link_rows}
		for label, (link_type, target) in R2_REQUIRED_LINKS.items():
			self.assertIn(label, by_label)
			self.assertEqual(by_label[label].get("link_type"), link_type)
			self.assertEqual(by_label[label].get("link_to"), target)

		targets = [(row.get("link_type"), row.get("link_to")) for row in link_rows if row.get("link_to")]
		self.assertEqual(len(targets), len(set(targets)))
		self.assertFalse(R2_FORBIDDEN_NATIVE_TARGETS.intersection({target for _, target in targets}))
		self.assertFalse(
			[
				row
				for row in link_rows
				if "edgepay" in str(row.get("label") or "").lower()
				or "edgepay" in str(row.get("link_to") or "").lower()
			]
		)
