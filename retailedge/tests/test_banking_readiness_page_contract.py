from __future__ import annotations

from pathlib import Path

from frappe.tests import IntegrationTestCase


class BankingReadinessPageContractTests(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        app_root = Path(__file__).resolve().parents[1]
        cls.readiness_js = (
            app_root
            / "retailedge"
            / "page"
            / "banking_readiness"
            / "banking_readiness.js"
        ).read_text()
        cls.matching_js = (
            app_root
            / "retailedge"
            / "page"
            / "bank_matching_reconciliation"
            / "bank_matching_reconciliation.js"
        ).read_text()

    def test_readiness_page_uses_edgesuite_runtime(self):
        self.assertIn("EdgeSuiteUI", self.readiness_js)
        self.assertIn('getComponent("EdgePageLayout")', self.readiness_js)
        self.assertIn('getComponent("EdgeStatusBadge")', self.readiness_js)

    def test_readiness_page_has_no_raw_html_template_injection(self):
        forbidden = (
            "<table",
            "<tr",
            "<td",
            "<div",
            "<button",
            "<a ",
            'fieldtype: "HTML"',
            "innerHTML",
        )
        for token in forbidden:
            self.assertNotIn(token, self.readiness_js)

    def test_native_bank_account_opens_new_tab(self):
        self.assertIn('"_blank"', self.readiness_js)
        self.assertIn('"noopener,noreferrer"', self.readiness_js)
        self.assertIn("/app/bank-account/", self.readiness_js)

    def test_banking_pages_link_to_each_other(self):
        self.assertIn('frappe.set_route("bank-matching-reconciliation")', self.readiness_js)
        self.assertIn('frappe.set_route("banking-readiness")', self.matching_js)

    def test_readiness_page_calls_permission_aware_backend(self):
        self.assertIn(
            "retailedge.banking_readiness.get_banking_readiness",
            self.readiness_js,
        )
