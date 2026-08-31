from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestPurchaseCycleVerificationUIContract(TestCase):
	def test_purchase_register_reuses_existing_edgesuite_provider_and_page(self):
		bundle = (APP_ROOT / "public" / "js" / "purchase_reporting.bundle.js").read_text()
		component = (APP_ROOT / "public" / "js" / "purchase_reporting" / "PurchaseReportingReport.vue").read_text()

		self.assertIn('retailedge.purchase_cycle_verification.get_purchase_cycle_verification', bundle)
		self.assertIn('config.key === "purchase-register"', bundle)
		self.assertIn("verification_status", bundle)
		self.assertIn("po_links", bundle)
		self.assertIn("receipt_links", bundle)
		self.assertIn("review_flags", bundle)
		self.assertIn("review_reason", bundle)
		self.assertIn("verification_policy", bundle)
		self.assertIn("PurchaseReportingReport", bundle)
		self.assertIn("window.EdgeSuiteUI", component)
		self.assertIn("EdgeAppShell", component)
		self.assertIn("EdgeReportShell", component)
		self.assertNotIn("frappe.ui.Dialog", bundle)
		self.assertNotIn("frappe.prompt", bundle)

	def test_supplier_payables_is_not_routed_through_purchase_verification(self):
		bundle = (APP_ROOT / "public" / "js" / "purchase_reporting.bundle.js").read_text()

		self.assertIn('key: "supplier-payables"', bundle)
		self.assertIn('config.key === "purchase-register" ? await enrichPurchaseRegister(rawResult) : rawResult', bundle)

	def test_purchase_verification_stays_advisory(self):
		source = (APP_ROOT / "purchase_cycle_verification.py").read_text()
		bundle = (APP_ROOT / "public" / "js" / "purchase_reporting.bundle.js").read_text()

		for text in (source, bundle):
			self.assertNotIn("Payment Order", text)
			self.assertNotIn("Journal Entry", text)
			self.assertNotIn("Stock Ledger Entry", text)
		self.assertNotIn("block_payment", source)
		self.assertNotIn("approval_status", source)


if __name__ == "__main__":
	import unittest

	unittest.main()
