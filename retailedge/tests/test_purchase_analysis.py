from __future__ import annotations

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.purchase_analysis import (
	SUPPORTED_GROUP_BY,
	_add_line_to_bucket,
	_finalise_bucket,
	_new_bucket,
	_normalise_group_by,
	_period_group,
)

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "purchase_analysis.py"
COMPONENT = ROOT / "public" / "js" / "purchase_reporting" / "PurchaseReportingReport.vue"
BUNDLE = ROOT / "public" / "js" / "purchase_reporting.bundle.js"
PAGE_JSON = ROOT / "retailedge" / "page" / "purchase_analysis" / "purchase_analysis.json"
PAGE_JS = ROOT / "retailedge" / "page" / "purchase_analysis" / "purchase_analysis.js"
REPORT_CENTER = ROOT / "report_center.py"
CAPABILITIES = ROOT / "reporting_capabilities.py"
ACTIONS = ROOT / "reporting_actions.py"
SORTING = ROOT / "report_sorting.py"
HOOKS = ROOT / "hooks.py"
OPERATING_DEFAULTS = ROOT / "operating_report_defaults.py"


class TestPurchaseAnalysis(FrappeTestCase):
	def test_supported_dimensions_are_authoritative_purchase_dimensions(self):
		self.assertEqual(
			SUPPORTED_GROUP_BY,
			(
				"Day",
				"Week",
				"Month",
				"Quarter",
				"Year",
				"Item",
				"Item Group",
				"Supplier",
				"Supplier Group",
				"Branch",
				"Warehouse",
			),
		)
		self.assertEqual(_normalise_group_by("supplier group"), "Supplier Group")
		self.assertEqual(_normalise_group_by(""), "Month")

	def test_period_grouping_is_stable(self):
		self.assertEqual(_period_group("2026-09-22", "Day"), ("2026-09-22", "2026-09-22"))
		self.assertEqual(_period_group("2026-09-22", "Week")[0], "2026-W39")
		self.assertEqual(_period_group("2026-09-22", "Month")[0], "2026-09")
		self.assertEqual(_period_group("2026-09-22", "Quarter"), ("2026-Q3", "Q3 2026"))
		self.assertEqual(_period_group("2026-09-22", "Year"), ("2026", "2026"))

	def test_returns_reverse_quantity_and_item_net_purchase_value(self):
		bucket = _new_bucket("Products", "Products")
		_add_line_to_bucket(
			bucket,
			frappe._dict(name="PINV-1", is_return=0),
			frappe._dict(parent="PINV-1", qty=4, base_net_amount=400),
		)
		_add_line_to_bucket(
			bucket,
			frappe._dict(name="PINV-RET-1", is_return=1),
			frappe._dict(parent="PINV-RET-1", qty=-1, base_net_amount=-100),
		)
		row = _finalise_bucket(bucket)

		self.assertEqual(row["purchased_qty"], 4)
		self.assertEqual(row["returned_qty"], 1)
		self.assertEqual(row["net_qty"], 3)
		self.assertEqual(row["purchase_value"], 400)
		self.assertEqual(row["returns_value"], 100)
		self.assertEqual(row["net_purchased"], 300)
		self.assertEqual(row["invoice_count"], 2)
		self.assertEqual(row["average_transaction_value"], 150)
		self.assertEqual(row["average_unit_cost"], 100)

	def test_backend_reuses_purchase_invoice_truth_without_allocating_invoice_balances(self):
		source = BACKEND.read_text(encoding="utf-8")
		for token in (
			"_get_permitted_invoice_headers",
			"_get_invoice_items",
			"_assert_report_access",
			"_validate_purchase_filters",
			'"Submitted ERPNext Purchase Invoice / Purchase Invoice Item"',
			'"outstanding_policy"',
			'"tax_policy"',
			'"supplier_scoring": "No supplier score is invented by this report."',
		):
			self.assertIn(token, source)

		for forbidden in (
			"frappe.db.sql",
			"frappe.db.commit",
			"ignore_permissions",
			"outstanding_amount",
			"base_grand_total",
			"base_total_taxes_and_charges",
			"supplier_score",
		):
			self.assertNotIn(forbidden, source)

	def test_page_provider_catalogue_scope_and_governance_are_wired(self):
		for path in (PAGE_JSON, PAGE_JS):
			self.assertTrue(path.exists(), f"Missing Purchase Analysis Page fixture: {path}")

		component = COMPONENT.read_text(encoding="utf-8")
		bundle = BUNDLE.read_text(encoding="utf-8")
		report_center = REPORT_CENTER.read_text(encoding="utf-8")
		capabilities = CAPABILITIES.read_text(encoding="utf-8")
		actions = ACTIONS.read_text(encoding="utf-8")
		sorting = SORTING.read_text(encoding="utf-8")
		hooks = HOOKS.read_text(encoding="utf-8")
		operating = OPERATING_DEFAULTS.read_text(encoding="utf-8")

		for token in (
			"purchase_analysis:",
			'providerKey: "purchase-analysis"',
			'label="Group By"',
			'"Purchases by Category"',
			'"Purchases by Supplier"',
			'"Purchases by Branch"',
			'"Purchases by Warehouse"',
		):
			self.assertIn(token, component)
		self.assertIn('key: "purchase-analysis"', bundle)
		self.assertIn('pageMethod: "retailedge.purchase_analysis.get_purchase_analysis"', bundle)
		self.assertIn('"target": "purchase-analysis"', report_center)
		self.assertIn('"purchase-analysis": ReportCapabilitySpec', capabilities)
		self.assertIn('if key == "purchase-analysis"', actions)
		self.assertIn('"purchase-analysis": frozenset', sorting)
		self.assertIn('"retailedge.purchase_analysis.get_purchase_analysis"', hooks)
		self.assertIn("def get_purchase_analysis(", operating)
		self.assertIn("_constrain_report_filters(filters)", operating)
