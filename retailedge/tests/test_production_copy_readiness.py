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
		self.assertIn('.replace(/^r\\d+[_\\s-]+/i, "")', text)
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

	def test_company_profile_uses_business_language(self):
		text = source("public/js/company_profile/CompanyProfile.vue")

		for phrase in (
			"ERPNext country",
			"Advanced ERPNext setup",
			"Open Company in ERPNext",
			"Advanced ERPNext access",
		):
			self.assertNotIn(phrase, text)
		self.assertIn("Open Advanced Company Settings", text)

	def test_reports_centre_descriptions_use_business_language(self):
		text = source("report_center.py")

		for phrase in (
			"Review R8 transactional contribution",
			"existing R12 sales forecast",
			"Review ERPNext",
			"Open ERPNext",
			"ERPNext accounting statements",
			"Native Desk users",
			"governed ERPNext purchasing workflow",
			"ERPNext General Ledger truth",
		):
			self.assertNotIn(phrase, text)
		self.assertIn("Accounting statements and ledgers for authorised advanced-access users.", text)

	def test_payment_history_hides_platform_and_migration_wording(self):
		backend = source("payment_history.py")
		frontend = source("public/js/payment_management/PaymentHistoryPanel.vue")

		for phrase in (
			"Run the site migration",
			"Advanced ERPNext review",
			"source_of_truth\": \"ERPNext Payment Entry",
		):
			self.assertNotIn(phrase, backend)
		for phrase in (
			"permission-visible ERPNext Payment Entries",
			"Advanced ERPNext access",
			"Advanced: ERPNext",
			"Review the ERPNext Payment Entry",
			"saved ERPNext Payment Entry",
			"ERPNext will post the authoritative accounting entry",
			"Payment submitted through ERPNext",
		):
			self.assertNotIn(phrase, frontend)
		self.assertIn("Open Advanced Payment", frontend)

	def test_shared_selling_workflows_use_business_facing_errors(self):
		selling = source("standard_selling_completion.py")
		delivery = source("professional_delivery.py")
		sales_order = source("professional_sales_order.py")

		for phrase in (
			"Advanced ERPNext review",
			"standard EdgeSuite completion",
			"available workflow action in EdgeSuite",
			"No active Frappe Workflow",
			"ERPNext did not submit",
		):
			self.assertNotIn(phrase, selling)
		for phrase in (
			"Use Advanced ERPNext review",
			"ERPNext could not prepare a Delivery Note",
			"ERPNext returned a non-draft Delivery Note mapping",
		):
			self.assertNotIn(phrase, delivery)
		for phrase in (
			"Use Advanced ERPNext review",
			"ERPNext could not prepare a Sales Order",
			"ERPNext returned a non-draft Sales Order mapping",
		):
			self.assertNotIn(phrase, sales_order)

	def test_customer_payment_backend_uses_business_facing_blockers(self):
		text = source("standard_customer_payment_submit.py")

		for phrase in (
			"Advanced ERPNext review",
			"standard EdgeSuite submission",
			"available workflow action in EdgeSuite",
			"Run the site migration",
			"standard EdgeSuite workflow path",
			"ERPNext did not submit Payment Entry",
		):
			self.assertNotIn(phrase, text)
		self.assertIn("Payments allocated to multiple documents require advanced review.", text)
		self.assertIn("Branch support for Payment Entry is not available yet.", text)
		self.assertIn("controlled by active approval workflow", text)

	def test_supplier_payment_backend_uses_business_facing_blockers(self):
		text = source("standard_supplier_payment_submit.py")

		for phrase in (
			"Advanced ERPNext review",
			"standard EdgeSuite submission",
			"available workflow action in EdgeSuite",
			"Run the site migration",
			"standard EdgeSuite workflow path",
			"ERPNext did not submit Payment Entry",
		):
			self.assertNotIn(phrase, text)
		self.assertIn("Supplier advances require advanced review.", text)
		self.assertIn("Branch support for Payment Entry is not available yet.", text)
		self.assertIn("controlled by active approval workflow", text)


if __name__ == "__main__":
	unittest.main()
