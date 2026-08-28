from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestAdvancedPaymentUIContract(TestCase):
	def test_payment_management_page_is_standard_edgesuite_page(self):
		page_dir = APP_ROOT / "retailedge" / "page" / "payment_management"
		page_json = (page_dir / "payment_management.json").read_text()
		page_js = (page_dir / "payment_management.js").read_text()

		self.assertIn('"page_name": "payment-management"', page_json)
		self.assertIn('"standard": "Yes"', page_json)
		self.assertIn('"role": "Accounts User"', page_json)
		self.assertIn('"role": "Accounts Manager"', page_json)
		self.assertIn('"role": "Sales Manager"', page_json)
		self.assertIn('const EDGEUI_ASSET = "edgeui.bundle.js"', page_js)
		self.assertIn('const PAYMENT_ASSET = "payment_management.bundle.js"', page_js)
		self.assertIn("window.mountPaymentManagementPage", page_js)

	def test_payment_management_bundle_uses_native_payment_endpoints(self):
		bundle = (APP_ROOT / "public" / "js" / "payment_management.bundle.js").read_text()
		component = (APP_ROOT / "public" / "js" / "payment_management" / "PaymentManagement.vue").read_text()

		self.assertIn("PaymentManagement", bundle)
		self.assertIn("retailedge.advanced_payments.get_customer_advance_context", component)
		self.assertIn("retailedge.advanced_payments.create_customer_advance_draft", component)
		self.assertIn("retailedge.advanced_payments.get_sales_invoice_advance_context", component)
		self.assertIn("retailedge.payment_application.apply_customer_advance", component)
		self.assertIn("Payment Reconciliation", component)
		self.assertNotIn("GL Entry", component)

	def test_sales_invoice_exposes_guarded_apply_advance_action(self):
		source = (APP_ROOT / "public" / "js" / "sales_documents.js").read_text()

		self.assertIn('ADVANCE_CONTEXT_METHOD = "retailedge.advanced_payments.get_sales_invoice_advance_context"', source)
		self.assertIn('APPLY_ADVANCE_METHOD = "retailedge.payment_application.apply_customer_advance"', source)
		self.assertIn('frm.doc.docstatus !== 1', source)
		self.assertIn('Number(frm.doc.outstanding_amount || 0) <= 0', source)
		self.assertIn('frm.add_custom_button(__("Apply Customer Advance")', source)
		self.assertIn('__("Payments")', source)
		self.assertIn("await frm.reload_doc()", source)

	def test_payment_management_is_promoted_without_removing_payment_entry(self):
		source = (APP_ROOT / "master_experience.py").read_text()

		self.assertIn('"target": "payment-management"', source)
		self.assertIn("def _promote_payment_management", source)
		self.assertIn('group.get("key") != "money"', source)
		self.assertIn('item.get("target") == "Payment Entry"', source)
		self.assertIn("_promote_payment_management(navigation_groups)", source)
		self.assertIn('feature_flags["advanced_payment_management"] = "erpnext_native_reconciliation"', source)
