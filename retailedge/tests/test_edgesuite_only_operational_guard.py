from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class EdgeSuiteOnlyOperationalGuardTests(unittest.TestCase):
	def setUp(self):
		self.guard = (
			APP_ROOT / "public" / "js" / "retailedge_edgesuite_only_operational_guard.bundle.js"
		).read_text()
		self.selling_page = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "professional_selling"
			/ "professional_selling.js"
		).read_text()
		self.payment_page = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "payment_management"
			/ "payment_management.js"
		).read_text()

	def test_guard_is_boot_mode_driven_and_does_not_change_permissions(self):
		self.assertIn('const ACCESS_BOOT_KEY = "edgesuite_ui_access"', self.guard)
		self.assertIn('const RESTRICTED_MODE = "edgesuite_only"', self.guard)
		self.assertIn("window.frappe?.boot?.[ACCESS_BOOT_KEY]?.mode === RESTRICTED_MODE", self.guard)
		self.assertNotIn("desk_access", self.guard)
		self.assertNotIn("ignore_permissions", self.guard)
		self.assertNotIn("frappe.client.set_value", self.guard)

	def test_guard_is_active_only_on_the_current_configured_page(self):
		self.assertIn("const current = currentPageRoute();", self.guard)
		self.assertIn("current === config.pageRoute", self.guard)
		self.assertNotIn("return Boolean(config.rootSelector && document.querySelector(config.rootSelector))", self.guard)
		self.assertIn("if (!restricted()) return [];", self.guard)

	def test_guard_blocks_only_configured_native_form_list_and_app_paths(self):
		self.assertIn('family !== "form" && family !== "list"', self.guard)
		self.assertIn("config.nativeDoctypes.some", self.guard)
		self.assertIn("config.nativePathSlugs.some", self.guard)
		self.assertIn("return originalOpen(url, ...args);", self.guard)
		self.assertIn("return originalSetRoute(...args);", self.guard)

	def test_automatic_post_save_native_redirects_are_blocked_without_noise(self):
		self.assertIn("Boolean(window.event?.isTrusted)", self.guard)
		self.assertIn("if (!shouldShowBlockedNotice()) return;", self.guard)
		self.assertIn("return null;", self.guard)
		self.assertIn("return false;", self.guard)

	def test_presentation_guard_does_not_churn_or_destroy_prior_control_state(self):
		self.assertIn("const configs = activeConfigs();", self.guard)
		self.assertIn("if (!configs.length) {", self.guard)
		self.assertIn("restoreMarkedControls();", self.guard)
		self.assertIn("data-retailedge-native-was-hidden", self.guard)
		self.assertIn("data-retailedge-native-was-disabled", self.guard)
		self.assertIn("{ childList: true, subtree: true }", self.guard)
		self.assertNotIn("attributes: true", self.guard)

	def test_guard_is_compiled_as_a_frappe_lazy_load_bundle(self):
		asset = 'retailedge_edgesuite_only_operational_guard.bundle.js'
		self.assertIn(f'RESTRICTED_GUARD_ASSET = "{asset}"', self.selling_page)
		self.assertIn(f'RESTRICTED_GUARD_ASSET = "{asset}"', self.payment_page)

	def test_professional_selling_loads_and_configures_guard_before_bundle(self):
		guard_index = self.selling_page.index("await requireAsync(RESTRICTED_GUARD_ASSET)")
		bundle_index = self.selling_page.index("await requireAsync(SELLING_ASSET)")
		self.assertLess(guard_index, bundle_index)
		self.assertIn('pageRoute: PAGE_ROUTE', self.selling_page)
		self.assertIn('rootSelector: ".retailedge-professional-selling-root"', self.selling_page)
		for doctype in ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice"):
			self.assertIn(f'"{doctype}"', self.selling_page)
		self.assertIn('hiddenButtonLabels: ["View Records", "Open Full Form"]', self.selling_page)
		self.assertIn('neutralizeSelectors: [".recent-row"]', self.selling_page)

	def test_payment_management_loads_and_configures_guard_before_bundle(self):
		guard_index = self.payment_page.index("await requireAsync(RESTRICTED_GUARD_ASSET)")
		bundle_index = self.payment_page.index("await requireAsync(PAYMENT_ASSET)")
		self.assertLess(guard_index, bundle_index)
		self.assertIn('pageRoute: PAGE_ROUTE', self.payment_page)
		self.assertIn('rootSelector: ".retailedge-payment-management-root"', self.payment_page)
		for doctype in ("Payment Entry", "Sales Invoice", "Payment Reconciliation"):
			self.assertIn(f'"{doctype}"', self.payment_page)
		self.assertIn('hiddenButtonLabels: ["Payment Entries", "Open Draft Payment"]', self.payment_page)
		self.assertIn('neutralizeSelectors: [".link-button"]', self.payment_page)

	def test_page_show_reapplies_guard_without_rewriting_business_logic(self):
		self.assertGreaterEqual(self.selling_page.count("installRestrictedOperationalGuard();"), 2)
		self.assertGreaterEqual(self.payment_page.count("installRestrictedOperationalGuard();"), 2)
		self.assertNotIn("create_professional_quotation_draft", self.selling_page)
		self.assertNotIn("create_customer_advance_draft", self.payment_page)


if __name__ == "__main__":
	unittest.main()
