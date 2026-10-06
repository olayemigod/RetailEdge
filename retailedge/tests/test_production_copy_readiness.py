from pathlib import Path
import unittest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
	return (PACKAGE_ROOT / path).read_text(encoding="utf-8")


class TestProductionCopyReadiness(unittest.TestCase):
	def test_action_center_maps_internal_sources_to_business_labels(self):
		text = source("public/js/action_center/ActionCenter.vue")

		self.assertIn('r11_customer_opportunity: "Customer Opportunity"', text)
		self.assertIn('r11_sales_quality: "Sales Quality"', text)
		self.assertIn('r11_customer_sales: "Customer & Sales"', text)
		self.assertIn('r12_planning: "Forecasting & Planning"', text)
		self.assertIn('{{ actionMetaLabel(item) }}', text)
		self.assertIn('.filter(Boolean).join(" · ")', text)
		self.assertNotIn('R11 Customer Opportunity', text)
		self.assertNotIn('Advanced Native Desk access is required for this workflow', text)

	def test_known_merchant_surfaces_do_not_reintroduce_internal_copy(self):
		forbidden = {
			"public/js/customer_sales_intelligence/CustomerSalesIntelligence.vue": (
				"from ERPNext sales truth",
				"current ERPNext receivable exposure",
				"R8 transactional cost contract",
				"Submitted ERPNext Sales Invoice",
			),
			"public/js/sales_quality_intelligence/SalesQualityIntelligence.vue": (
				"ERPNext accounting truth",
				"separately from ERPNext",
				"R8 transactional incoming-rate",
				"ERPNext Profit & Loss",
			),
			"public/js/customer_opportunity_intelligence/CustomerOpportunityIntelligence.vue": (
				"current ERPNext receivable exposure",
				"Submitted ERPNext Sales Invoice",
				"Current ERPNext outstanding exposure",
			),
			"public/js/forecasting_planning/ForecastingPlanning.vue": (
				"ERPNext actuals remain authoritative",
				"Native Desk access is required",
				"ERPNext Budget reference",
				"R12 does not create",
				"EdgeSuite create navigation is unavailable",
				"ERPNext GL / P&L",
				"Submitted ERPNext Budget",
			),
			"public/js/inventory_intelligence/InventoryIntelligenceCentre.vue": (
				"current ERPNext stock",
				"ERPNext Item Reorder configuration",
				"ERPNext Bin",
				"ERPNext Stock Ledger Entry",
			),
			"public/js/basket_affinity/BasketAffinity.vue": (
				"Submitted non-return ERPNext Sales Invoice",
			),
		}

		for path, phrases in forbidden.items():
			text = source(path)
			for phrase in phrases:
				with self.subTest(path=path, phrase=phrase):
					self.assertNotIn(phrase, text)

	def test_forecasting_sanitizes_runtime_reasons_and_errors(self):
		text = source("public/js/forecasting_planning/ForecastingPlanning.vue")

		self.assertIn("function customerFacingCopy(value, fallback = \"\")", text)
		self.assertIn("window.retailedge?.userErrorMessage?.(error, fallback)", text)
		self.assertIn("reason: customerFacingCopy(d.reason", text)
		self.assertIn("customerFacingCopy(meta.reason", text)
		self.assertIn("message(error, \"Unable to open the create form.\")", text)

	def test_settings_customer_copy_hides_platform_implementation_names(self):
		text = source("retailedge/page/retail_settings/retail_settings.py")

		self.assertIn('.replace("CoreEdge ", "Platform ")', text)
		self.assertIn('.replace("CoreEdge", "Platform")', text)
		self.assertNotIn('Default Price List from ERPNext User Permissions.', text)
		self.assertNotIn('Default Selling Price List from ERPNext Selling Settings.', text)
		self.assertNotIn('Default Buying Price List from ERPNext Buying Settings.', text)

	def test_reconciliation_confirmation_uses_business_wording(self):
		text = source("public/js/bank_reconciliation_confirmation.js")

		self.assertIn('primary_action_label: __("Reconcile Match")', text)
		self.assertNotIn('primary_action_label: __("Reconcile Through ERPNext")', text)
		self.assertNotIn("through ERPNext Bank Reconciliation", text)


if __name__ == "__main__":
	unittest.main()