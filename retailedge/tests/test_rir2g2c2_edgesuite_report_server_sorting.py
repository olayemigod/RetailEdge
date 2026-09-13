from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from retailedge.report_sorting import REPORT_SORT_FIELDS, build_report_order_by, normalise_report_sort, sort_materialized_rows

ROOT = Path(__file__).resolve().parents[1]

BUNDLES = (
	"cash_flow_outlook.bundle.js", "cash_movement.bundle.js", "cash_shift_verification.bundle.js",
	"customer_receivables.bundle.js", "daily_sales_audit.bundle.js", "expense_register.bundle.js",
	"expense_review.bundle.js", "purchase_reporting.bundle.js", "sales_reporting.bundle.js",
	"stock_accounting_integrity.bundle.js", "stock_position.bundle.js",
)
VIEWS = (
	"cash_flow_outlook/CashFlowOutlookReport.vue", "cash_movement/CashMovementReport.vue",
	"cash_shift_verification/CashShiftVerificationReport.vue", "customer_receivables/CustomerReceivablesReport.vue",
	"daily_sales_audit/DailySalesAuditReport.vue", "expense_register/ExpenseRegisterReport.vue",
	"expense_review/ExpenseReviewReport.vue", "purchase_reporting/PurchaseReportingReport.vue",
	"sales_reporting/SalesReportingReport.vue", "stock_accounting_integrity/StockAccountingIntegrityReport.vue",
	"stock_position/StockPositionReport.vue",
)


class TestRIR2G2C2EdgeReportServerSorting(TestCase):
	def test_report_sort_registry_is_explicit(self):
		self.assertEqual(len(REPORT_SORT_FIELDS), 13)

	def test_invalid_sort_is_rejected(self):
		self.assertIsNone(normalise_report_sort({"field": "drop table", "direction": "asc"}, "stock-position"))
		self.assertIsNone(normalise_report_sort({"field": "actual_qty", "direction": "sideways"}, "stock-position"))
		self.assertIsNone(normalise_report_sort("not-json", "stock-position"))

	def test_materialized_sort_is_stable_typed_and_empty_last(self):
		rows = [
			{"item_code": "A", "actual_qty": 10},
			{"item_code": "B", "actual_qty": None},
			{"item_code": "C", "actual_qty": 2},
			{"item_code": "D", "actual_qty": 10},
		]
		sorted_rows, normalized = sort_materialized_rows(rows, {"field": "actual_qty", "direction": "desc"}, "stock-position")
		self.assertEqual(normalized, {"field": "actual_qty", "direction": "desc"})
		self.assertEqual([row["item_code"] for row in sorted_rows], ["A", "D", "C", "B"])

	def test_query_order_uses_fixed_mapping_only(self):
		normalized, order_by = build_report_order_by(
			{"field": "amount", "direction": "asc"}, "expense-register", {"amount": "amount"},
			default_order="expense_date desc", tie_breakers=("creation DESC", "name DESC"),
		)
		self.assertEqual(normalized, {"field": "amount", "direction": "asc"})
		self.assertEqual(order_by, "amount ASC, creation DESC, name DESC")

	def test_all_provider_adapters_forward_sort(self):
		for relative in BUNDLES:
			source = (ROOT / "public/js" / relative).read_text(encoding="utf-8")
			self.assertIn("sort = null", source, relative)

	def test_all_edgesuite_report_consumers_bind_sort(self):
		for relative in VIEWS:
			source = (ROOT / "public/js" / relative).read_text(encoding="utf-8")
			self.assertIn(':sort="reportSort"', source, relative)
			self.assertIn('@sort-change="handleSortChange"', source, relative)
			self.assertIn("sort: this.reportSort", source, relative)
			self.assertIn("handleSortChange(sort)", source, relative)

	def test_purchase_verification_enrichment_is_not_sortable(self):
		source = (ROOT / "public/js/purchase_reporting.bundle.js").read_text(encoding="utf-8")
		self.assertIn("sortable: false", source)
