from __future__ import annotations

from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]


class TestProductionCopyContract(unittest.TestCase):
    """Keep internal release/platform terminology out of cleaned MVP surfaces."""

    def _read(self, relative_path: str) -> str:
        return (APP_ROOT / relative_path).read_text(encoding="utf-8")

    def test_action_centre_does_not_humanise_internal_release_keys(self):
        source = self._read("public/js/action_center/ActionCenter.vue")

        self.assertIn('r11_customer_opportunity: "Customer Opportunity"', source)
        self.assertIn('r11_sales_quality: "Sales Quality"', source)
        self.assertIn('r12_planning: "Forecasting & Planning"', source)
        self.assertIn('.replace(/^r\\d+[_\\s-]+/i, "")', source)
        self.assertIn('.filter(Boolean).join(" · ")', source)
        self.assertNotIn("R11 Customer Opportunity", source)
        self.assertNotIn("Advanced Native Desk", source)

    def test_cleaned_intelligence_pages_hide_release_and_platform_copy(self):
        paths = (
            "public/js/customer_sales_intelligence/CustomerSalesIntelligence.vue",
            "public/js/customer_opportunity_intelligence/CustomerOpportunityIntelligence.vue",
            "public/js/sales_quality_intelligence/SalesQualityIntelligence.vue",
            "public/js/inventory_intelligence/InventoryIntelligenceCentre.vue",
            "public/js/forecasting_planning/ForecastingPlanning.vue",
        )
        forbidden = (
            "R8 transactional",
            "R12 does not",
            "ERPNext actuals",
            "ERPNext Budget reference",
            "ERPNext receivable exposure",
            "Native Desk access is required",
            "EdgeSuite create navigation is unavailable",
        )

        for path in paths:
            source = self._read(path)
            for phrase in forbidden:
                self.assertNotIn(phrase, source, f"{phrase!r} leaked into {path}")

    def test_company_profile_uses_business_language(self):
        source = self._read("public/js/company_profile/CompanyProfile.vue")

        for phrase in (
            "ERPNext country",
            "Advanced ERPNext setup",
            "Open Company in ERPNext",
            "Advanced ERPNext access",
        ):
            self.assertNotIn(phrase, source)

        self.assertIn("Open Advanced Company Settings", source)
        self.assertIn("Advanced company setup", source)

    def test_reconciliation_confirmation_uses_business_language(self):
        source = self._read("public/js/bank_reconciliation_confirmation.js")

        self.assertIn('primary_action_label: __("Reconcile Match")', source)
        self.assertNotIn('primary_action_label: __("Reconcile Through ERPNext")', source)
        self.assertNotIn("through ERPNext Bank Reconciliation", source)

    def test_settings_customer_copy_hides_internal_platform_names(self):
        source = self._read("retailedge/page/retail_settings/retail_settings.py")

        self.assertIn('.replace("CoreEdge", "Platform")', source)
        self.assertNotIn("Default Price List from ERPNext User Permissions.", source)
        self.assertNotIn("Default Selling Price List from ERPNext Selling Settings.", source)
        self.assertNotIn("Default Buying Price List from ERPNext Buying Settings.", source)


if __name__ == "__main__":
    unittest.main()
