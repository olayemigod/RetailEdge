from __future__ import annotations

from pathlib import Path

from frappe.tests.utils import FrappeTestCase

from retailedge.supplier_performance import (
	_add_payable_metrics,
	_add_purchase_metrics,
	_finalise_supplier_bucket,
	_new_supplier_bucket,
)

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "supplier_performance.py"
COMPONENT = ROOT / "public" / "js" / "purchase_reporting" / "PurchaseReportingReport.vue"
BUNDLE = ROOT / "public" / "js" / "purchase_reporting.bundle.js"
PAGE_JSON = ROOT / "retailedge" / "page" / "supplier_performance" / "supplier_performance.json"
PAGE_JS = ROOT / "retailedge" / "page" / "supplier_performance" / "supplier_performance.js"
REPORT_CENTER = ROOT / "report_center.py"
CAPABILITIES = ROOT / "reporting_capabilities.py"
ACTIONS = ROOT / "reporting_actions.py"
SORTING = ROOT / "report_sorting.py"
HOOKS = ROOT / "hooks.py"
OPERATING_DEFAULTS = ROOT / "operating_report_defaults.py"


class TestSupplierPerformance(FrappeTestCase):
	def test_supplier_metrics_keep_period_activity_and_current_payables_separate(self):
		bucket = _new_supplier_bucket("SUP-001", "Acme Supply")
		_add_purchase_metrics(
			bucket,
			{
				"purchase_value": 1200,
				"returns_value": 200,
				"net_purchased": 1000,
				"invoice_count": 4,
			},
		)
		_add_payable_metrics(
			bucket,
			{
				"outstanding": 350,
				"overdue_days": 20,
			},
		)
		_add_payable_metrics(
			bucket,
			{
				"outstanding": 150,
				"overdue_days": 0,
			},
		)
		row = _finalise_supplier_bucket(bucket)

		self.assertEqual(row["net_purchased"], 1000)
		self.assertEqual(row["invoice_count"], 4)
		self.assertEqual(row["average_invoice_value"], 250)
		self.assertAlmostEqual(row["return_rate_percent"], 200 / 1200 * 100)
		self.assertEqual(row["current_outstanding"], 500)
		self.assertEqual(row["overdue_outstanding"], 350)
		self.assertEqual(row["open_bill_count"], 2)
		self.assertEqual(row["overdue_bill_count"], 1)
		self.assertEqual(row["oldest_overdue_days"], 20)

	def test_return_rate_is_not_invented_without_positive_period_purchase_value(self):
		bucket = _new_supplier_bucket("SUP-RET", "Return Only")
		_add_purchase_metrics(
			bucket,
			{
				"purchase_value": 0,
				"returns_value": 50,
				"net_purchased": -50,
				"invoice_count": 1,
			},
		)
		row = _finalise_supplier_bucket(bucket)
		self.assertIsNone(row["return_rate_percent"])

	def test_backend_composes_existing_purchase_and_payables_owners(self):
		source = BACKEND.read_text(encoding="utf-8")
		for token in (
			"_build_purchase_analysis_dataset",
			"get_supplier_payables_export",
			'group_by="Supplier"',
			'"purchase_basis"',
			'"payables_basis"',
			'"supplier_score"',
			'"delivery_kpi"',
			'"Professional Purchasing remains the operational owner',
		):
			self.assertIn(token, source)

		for forbidden in (
			"frappe.db.sql",
			"ignore_permissions",
			"supplier_score =",
			"on_time_delivery_rate",
			"delivery_score",
		):
			self.assertNotIn(forbidden, source)

	def test_page_provider_catalogue_scope_and_governance_are_wired(self):
		for path in (PAGE_JSON, PAGE_JS):
			self.assertTrue(path.exists(), f"Missing Supplier Performance Page fixture: {path}")

		component = COMPONENT.read_text(encoding="utf-8")
		bundle = BUNDLE.read_text(encoding="utf-8")
		report_center = REPORT_CENTER.read_text(encoding="utf-8")
		capabilities = CAPABILITIES.read_text(encoding="utf-8")
		actions = ACTIONS.read_text(encoding="utf-8")
		sorting = SORTING.read_text(encoding="utf-8")
		hooks = HOOKS.read_text(encoding="utf-8")
		operating = OPERATING_DEFAULTS.read_text(encoding="utf-8")

		for token in (
			"supplier_performance:",
			'providerKey: "supplier-performance"',
			"supplierPerformance: true",
			"Period purchases · current payables aged at",
			'["purchase_analysis", "supplier_performance"].includes(this.reportType)',
		):
			self.assertIn(token, component)
		self.assertIn('key: "supplier-performance"', bundle)
		self.assertIn('pageMethod: "retailedge.supplier_performance.get_supplier_performance"', bundle)
		self.assertIn('"target": "supplier-performance"', report_center)
		self.assertIn('"supplier-performance": ReportCapabilitySpec', capabilities)
		self.assertIn('if key == "supplier-performance"', actions)
		self.assertIn('"supplier-performance": frozenset', sorting)
		self.assertIn('"retailedge.supplier_performance.get_supplier_performance"', hooks)
		self.assertIn("def get_supplier_performance(", operating)
		self.assertIn("_constrain_report_filters(filters)", operating)
