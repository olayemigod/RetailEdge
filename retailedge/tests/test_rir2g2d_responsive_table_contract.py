from __future__ import annotations

import re
import unittest
from pathlib import Path

import edgesuite_ui
import frappe

APP_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_JS = APP_ROOT / "public" / "js"

LOCAL_OVERFLOW_WRAPPERS = {
	"branch_assignments/BranchAssignments.vue": "assignment-table-wrap",
	"branch_setup/BranchSetup.vue": "table-wrap",
	"business_expenses/BusinessExpenses.vue": "table-wrap",
	"customer_360/Customer360.vue": "customer-360-table-wrap",
	"forecasting_planning/ForecastingPlanning.vue": "table-wrap",
	"native_visual_workspaces/NativeERPNextWorkspace.vue": "native-control-table-wrap",
	"payment_management/PaymentHistoryPanel.vue": "table-wrap",
	"payment_management/PaymentManagement.vue": "table-wrap",
	"professional_purchasing/IncomingQualityInspection.vue": "quality-table-wrap",
	"professional_purchasing/ProfessionalPurchasing.vue": "table-wrap",
	"professional_purchasing/SupplierScorecardGovernance.vue": "period-table-wrap",
	"profitability_intelligence/ProfitabilityIntelligence.vue": "profit-table-wrap",
	"project_operations/ProjectOperations.vue": "table-wrap",
	"retailedge_setup/ExpenseCategoryManager.vue": "manager-table-wrap",
	"stock_movement_history/StockMovementHistory.vue": "movement-table-wrap",
	"supplier_document_review/SupplierDocumentReview.vue": "supplier-review-table-wrap",
}

FRAPPE_RESPONSIVE_WRAPPERS = {
	"professional_purchasing/ProfessionalPurchaseOrderSubmitOverlay.vue",
	"professional_purchasing/ProfessionalPurchaseReceiptHistoryOverlay.vue",
	"professional_purchasing/ProfessionalPurchaseReceiptPreviewOverlay.vue",
	"professional_purchasing/ProfessionalPurchaseReturnReviewOverlay.vue",
	"professional_purchasing/ProfessionalRfqHistoryOverlay.vue",
	"professional_purchasing/ProfessionalRfqPreviewOverlay.vue",
	"professional_purchasing/ProfessionalSupplierQuotationHistoryOverlay.vue",
	"professional_purchasing/ProfessionalSupplierQuotationPurchaseOrderOverlay.vue",
	"salesperson_performance_dashboard/SalespersonPerformanceDashboard.vue",
}

EXPECTED_RAW_TABLE_SURFACES = set(LOCAL_OVERFLOW_WRAPPERS) | FRAPPE_RESPONSIVE_WRAPPERS


def _vue_sources_with_raw_tables() -> dict[str, str]:
	result: dict[str, str] = {}
	for path in PUBLIC_JS.rglob("*.vue"):
		source = path.read_text(encoding="utf-8")
		if re.search(r"<table\b", source):
			result[path.relative_to(PUBLIC_JS).as_posix()] = source
	return result


def _class_occurrences(source: str, class_name: str) -> int:
	pattern = rf'class=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\']'
	return len(re.findall(pattern, source))


class TestRIR2G2DResponsiveTableContract(unittest.TestCase):
	def test_raw_table_inventory_is_explicit_and_complete(self):
		actual = set(_vue_sources_with_raw_tables())
		self.assertEqual(
			actual,
			EXPECTED_RAW_TABLE_SURFACES,
			"Every new raw Vue table must be explicitly classified for responsive containment.",
		)

	def test_component_local_wrappers_contain_every_raw_table_and_declare_overflow(self):
		sources = _vue_sources_with_raw_tables()
		for relative_path, wrapper in LOCAL_OVERFLOW_WRAPPERS.items():
			with self.subTest(path=relative_path, wrapper=wrapper):
				source = sources[relative_path]
				table_count = len(re.findall(r"<table\b", source))
				wrapper_count = _class_occurrences(source, wrapper)
				self.assertGreaterEqual(
					wrapper_count,
					table_count,
					f"{relative_path} must keep every raw table inside {wrapper}.",
				)
				overflow_pattern = (
					rf"\.{re.escape(wrapper)}\s*\{{[^}}]*"
					r"overflow(?:-x)?\s*:\s*auto\b"
				)
				self.assertRegex(
					source,
					re.compile(overflow_pattern, re.IGNORECASE | re.DOTALL),
					f"{relative_path} responsive wrapper must retain horizontal/automatic overflow.",
				)

	def test_frappe_table_responsive_surfaces_wrap_every_raw_table(self):
		sources = _vue_sources_with_raw_tables()
		for relative_path in FRAPPE_RESPONSIVE_WRAPPERS:
			with self.subTest(path=relative_path):
				source = sources[relative_path]
				table_count = len(re.findall(r"<table\b", source))
				wrapper_count = _class_occurrences(source, "table-responsive")
				self.assertGreaterEqual(
					wrapper_count,
					table_count,
					f"{relative_path} must keep every raw table inside table-responsive.",
				)

	def test_supported_frappe_runtime_keeps_table_responsive_horizontal_scroll(self):
		frappe_root = Path(frappe.__file__).resolve().parent
		bootstrap_css = (frappe_root / "public" / "css" / "bootstrap.css").read_text(encoding="utf-8")
		self.assertRegex(
			bootstrap_css,
			re.compile(r"\.table-responsive\s*\{[^}]*overflow-x\s*:\s*auto\b", re.DOTALL),
		)

	def test_governed_edgesuite_report_table_remains_responsive(self):
		edge_root = Path(edgesuite_ui.__file__).resolve().parent
		report_css = (edge_root / "public" / "css" / "edgeui_reporting_presentation.css").read_text(encoding="utf-8")
		self.assertRegex(
			report_css,
			re.compile(r"\.edge-report-table-wrap\s*\{[^}]*overflow\s*:\s*auto\b", re.DOTALL),
		)
		self.assertRegex(
			report_css,
			re.compile(r"\.edge-report-table\s*\{[^}]*min-width\s*:\s*max-content\b", re.DOTALL),
		)


if __name__ == "__main__":
	unittest.main()
