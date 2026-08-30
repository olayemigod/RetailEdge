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
		self.assertIn("retailedge.payment_application.apply_customer_advances", component)
		self.assertIn("retailedge.payment_application.create_sales_invoice_payment_draft", component)
		self.assertIn("retailedge.guided_payment.search_simple_payment_options", component)
		self.assertIn("Payment Reconciliation", component)
		self.assertIn("Drafts do not reduce outstanding until submitted", component)
		self.assertNotIn("openApplyDialog", component)
		self.assertNotIn("GL Entry", component)

	def test_sales_invoice_routes_guarded_settlement_to_edgesuite_page(self):
		source = (APP_ROOT / "public" / "js" / "sales_documents.js").read_text()

		self.assertIn("function openMixedSettlement(frm)", source)
		self.assertIn("frappe.route_options = { sales_invoice: frm.doc.name }", source)
		self.assertIn('frappe.set_route("payment-management")', source)
		self.assertIn('frm.doc.docstatus !== 1', source)
		self.assertIn('Number(frm.doc.outstanding_amount || 0) <= 0', source)
		self.assertIn('frm.add_custom_button(__("Settle Customer Invoice")', source)
		self.assertIn('__("Payments")', source)
		self.assertNotIn("frappe.ui.Dialog", source)
		self.assertNotIn("APPLY_ADVANCE_METHOD", source)

	def test_payment_management_is_promoted_without_removing_payment_entry(self):
		source = (APP_ROOT / "master_experience.py").read_text()

		self.assertIn('"target": "payment-management"', source)
		self.assertIn('"target": "RetailEdge Customer Advance Register"', source)
		self.assertIn("def _promote_payment_management", source)
		self.assertIn("def _can_open_report", source)
		self.assertIn('group.get("key") != "money"', source)
		self.assertIn('item.get("target") == "Payment Entry"', source)
		self.assertIn("_promote_payment_management(navigation_groups)", source)
		self.assertIn('feature_flags["advanced_payment_management"] = "erpnext_native_reconciliation"', source)
		self.assertIn('feature_flags["customer_advance_reporting"] = "current_open_receipts"', source)

	def test_customer_advance_register_is_bounded_and_payment_entry_backed(self):
		report_dir = APP_ROOT / "retailedge" / "report" / "retailedge_customer_advance_register"
		report_json = (report_dir / "retailedge_customer_advance_register.json").read_text()
		report_py = (report_dir / "retailedge_customer_advance_register.py").read_text()

		self.assertIn('"report_type": "Script Report"', report_json)
		self.assertIn('"ref_doctype": "Payment Entry"', report_json)
		self.assertIn("MAX_ROWS = 2000", report_py)
		self.assertIn('"unallocated_amount": [">", 0]', report_py)
		self.assertIn('"payment_type": "Receive"', report_py)
		self.assertIn('"party_type": "Customer"', report_py)
		self.assertIn('"allocated_amount": max(received - available, 0)', report_py)
		self.assertIn("validate_user_branch_access", report_py)
