from __future__ import annotations

import json

import retailedge.tests._cashier_expense_regression_suite as _legacy
from retailedge.tests._cashier_expense_regression_suite import *  # noqa: F403,F405

R2_NATIVE_SECTIONS = [
	"Home",
	"Sell",
	"Buy",
	"Stock",
	"Money",
	"Expenses",
	"Customers",
	"Suppliers & Payables",
	"Insights",
	"Review & Approvals",
	"Setup",
]

R2_FORBIDDEN_NATIVE_TARGETS = {
	"Journal Entry",
	"RetailEdge Bank Match Batch Job",
	"Error Log",
	"RetailEdge Branch Profile User",
	"Item Group",
	"UOM",
	"Batch",
	"Serial No",
}

R2_REQUIRED_LINKS = {
	"RetailEdge Business Hub": ("Page", "retailedge-business-hub"),
	"Sales Invoices": ("DocType", "Sales Invoice"),
	"Payments": ("DocType", "Payment Entry"),
	"Cashier Expenses": ("DocType", "RetailEdge Cashier Expense"),
	"Customers": ("DocType", "Customer"),
	"Suppliers": ("DocType", "Supplier"),
	"Branch Performance": ("Page", "branch-performance-dashboard"),
	"Salesperson Performance": ("Page", "salesperson-performance-dashboard"),
	"Daily Sales Audit": ("DocType", "RetailEdge Daily Sales Audit"),
	"Bank Matching": ("Report", "RetailEdge Bank Transaction Matching"),
	"Stock Movement History": ("Report", "RetailEdge Stock Movement History"),
}

R2_SHORTCUTS = [
	"RetailEdge Business Hub",
	"Start POS",
	"Sales Invoices",
	"Payments",
	"Cashier Expenses",
	"Stock Movement History",
	"Branch Performance",
	"Daily Sales Audit",
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

		targets = [
			(row.get("link_type"), row.get("link_to"))
			for row in link_rows
			if row.get("link_to")
		]
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
				self.assertEqual(row.get("keep_closed"), 1, f"Sidebar section {row.get('label')} must start collapsed.")

		self.assertEqual(items[0].get("label"), "Home")
		self.assertEqual(items[0].get("link_type"), "Workspace")
		self.assertEqual(items[0].get("link_to"), "RetailEdge")

		link_rows = [row for row in items[1:] if row.get("type") == "Link"]
		by_label = {row.get("label"): row for row in link_rows}
		for label, (link_type, target) in R2_REQUIRED_LINKS.items():
			self.assertIn(label, by_label)
			self.assertEqual(by_label[label].get("link_type"), link_type)
			self.assertEqual(by_label[label].get("link_to"), target)

		targets = [
			(row.get("link_type"), row.get("link_to"))
			for row in link_rows
			if row.get("link_to")
		]
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
