from __future__ import annotations

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.sales_analysis import (
	SUPPORTED_GROUP_BY,
	_add_line_to_bucket,
	_finalise_bucket,
	_new_bucket,
	_normalise_group_by,
	_period_group,
)

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "sales_analysis.py"
COMPONENT = ROOT / "public" / "js" / "sales_reporting" / "SalesReportingReport.vue"
BUNDLE = ROOT / "public" / "js" / "sales_reporting.bundle.js"
PAGE_JSON = ROOT / "retailedge" / "page" / "sales_analysis" / "sales_analysis.json"
PAGE_JS = ROOT / "retailedge" / "page" / "sales_analysis" / "sales_analysis.js"
REPORT_CENTER = ROOT / "report_center.py"
CAPABILITIES = ROOT / "reporting_capabilities.py"
ACTIONS = ROOT / "reporting_actions.py"
SORTING = ROOT / "report_sorting.py"
HOOKS = ROOT / "hooks.py"


class TestSalesAnalysis(FrappeTestCase):
	def test_supported_dimensions_exclude_cashier_until_authoritative_attribution_exists(self):
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
				"Customer",
				"Customer Group",
				"Branch",
				"Salesperson",
				"Warehouse",
			),
		)
		self.assertNotIn("Cashier", SUPPORTED_GROUP_BY)
		self.assertEqual(_normalise_group_by("item group"), "Item Group")
		self.assertEqual(_normalise_group_by(""), "Month")

	def test_period_grouping_is_stable_for_day_week_month_quarter_and_year(self):
		self.assertEqual(_period_group("2026-09-22", "Day"), ("2026-09-22", "2026-09-22"))
		self.assertEqual(_period_group("2026-09-22", "Week")[0], "2026-W39")
		self.assertEqual(_period_group("2026-09-22", "Month")[0], "2026-09")
		self.assertEqual(_period_group("2026-09-22", "Quarter"), ("2026-Q3", "Q3 2026"))
		self.assertEqual(_period_group("2026-09-22", "Year"), ("2026", "2026"))

	def test_returns_reverse_quantity_revenue_and_recorded_cost(self):
		bucket = _new_bucket("Products", "Products")
		_add_line_to_bucket(
			bucket,
			frappe._dict(name="SINV-1", is_return=0),
			frappe._dict(
				parent="SINV-1",
				qty=2,
				stock_qty=2,
				base_net_amount=200,
				incoming_rate=60,
			),
			include_cost=True,
		)
		_add_line_to_bucket(
			bucket,
			frappe._dict(name="SINV-RET-1", is_return=1),
			frappe._dict(
				parent="SINV-RET-1",
				qty=-1,
				stock_qty=-1,
				base_net_amount=-100,
				incoming_rate=60,
			),
			include_cost=True,
		)

		row = _finalise_bucket(bucket, include_cost=True)
		self.assertEqual(row["sold_qty"], 2)
		self.assertEqual(row["returned_qty"], 1)
		self.assertEqual(row["net_qty"], 1)
		self.assertEqual(row["sales_value"], 200)
		self.assertEqual(row["returns_value"], 100)
		self.assertEqual(row["net_sales"], 100)
		self.assertEqual(row["recorded_cost"], 60)
		self.assertEqual(row["gross_profit"], 40)
		self.assertEqual(row["invoice_count"], 2)
		self.assertAlmostEqual(row["gross_margin_percent"], 40)

	def test_salesperson_weighting_does_not_double_count_revenue_or_cost(self):
		ada = _new_bucket("Ada", "Ada")
		bola = _new_bucket("Bola", "Bola")
		header = frappe._dict(name="SINV-1", is_return=0)
		item = frappe._dict(
			parent="SINV-1",
			qty=4,
			stock_qty=4,
			base_net_amount=400,
			incoming_rate=50,
		)
		_add_line_to_bucket(ada, header, item, weight=0.75, include_cost=True)
		_add_line_to_bucket(bola, header, item, weight=0.25, include_cost=True)
		ada_row = _finalise_bucket(ada, include_cost=True)
		bola_row = _finalise_bucket(bola, include_cost=True)

		self.assertEqual(ada_row["net_sales"], 300)
		self.assertEqual(bola_row["net_sales"], 100)
		self.assertEqual(ada_row["recorded_cost"], 150)
		self.assertEqual(bola_row["recorded_cost"], 50)
		self.assertEqual(ada_row["gross_profit"] + bola_row["gross_profit"], 200)

	def test_cost_fields_are_removed_when_profitability_is_not_visible(self):
		bucket = _new_bucket("Lagos", "Lagos")
		_add_line_to_bucket(
			bucket,
			frappe._dict(name="SINV-1", is_return=0),
			frappe._dict(
				parent="SINV-1",
				qty=1,
				stock_qty=1,
				base_net_amount=100,
			),
			include_cost=False,
		)
		row = _finalise_bucket(bucket, include_cost=False)
		self.assertNotIn("recorded_cost", row)
		self.assertNotIn("gross_profit", row)
		self.assertNotIn("gross_margin_percent", row)

	def test_backend_reuses_authoritative_sales_and_sales_team_contracts(self):
		source = BACKEND.read_text(encoding="utf-8")
		for token in (
			"_get_permitted_invoice_headers",
			"_filter_headers_by_salesperson",
			"get_sales_team_allocations",
			"should_hide_cost_price",
			'frappe.get_doc("Page", "profitability-intelligence").is_permitted()',
			'"cashier_dimension": "Not exposed; document owner is not treated as cashier"',
			"MAX_ITEM_SCAN_ROWS",
			"MAX_INVOICE_SCAN_ROWS",
		):
			self.assertIn(token, source)

		self.assertNotIn("frappe.db.sql", source)
		self.assertNotIn("frappe.db.commit", source)
		self.assertNotIn("ignore_permissions", source)
		self.assertNotIn('"owner"', source)

	def test_page_provider_catalogue_and_governance_are_wired(self):
		for path in (PAGE_JSON, PAGE_JS):
			self.assertTrue(path.exists(), f"Missing Sales Analysis Page fixture: {path}")

		component = COMPONENT.read_text(encoding="utf-8")
		bundle = BUNDLE.read_text(encoding="utf-8")
		report_center = REPORT_CENTER.read_text(encoding="utf-8")
		capabilities = CAPABILITIES.read_text(encoding="utf-8")
		actions = ACTIONS.read_text(encoding="utf-8")
		sorting = SORTING.read_text(encoding="utf-8")
		hooks = HOOKS.read_text(encoding="utf-8")

		for token in (
			"sales_analysis:",
			'providerKey: "sales-analysis"',
			'label="Group By"',
			'"Sales by Category"',
			'"Sales by Branch"',
			'"Sales by Salesperson"',
			'"Sales by Warehouse"',
		):
			self.assertIn(token, component)
		self.assertIn('key: "sales-analysis"', bundle)
		self.assertIn('pageMethod: "retailedge.sales_analysis.get_sales_analysis"', bundle)
		self.assertIn('"target": "sales-analysis"', report_center)
		self.assertIn('"sales-analysis": ReportCapabilitySpec', capabilities)
		self.assertIn('if key == "sales-analysis"', actions)
		self.assertIn('"sales-analysis": frozenset', sorting)
		self.assertIn('"retailedge.sales_analysis.get_sales_analysis"', hooks)
