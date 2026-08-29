from __future__ import annotations

import ast
from pathlib import Path
from unittest import TestCase

APP_ROOT = Path(__file__).resolve().parents[1]


class TestCustomerPortalPayment(TestCase):
	def setUp(self):
		self.service = (APP_ROOT / "customer_portal_payment.py").read_text(encoding="utf-8")
		self.portal = (APP_ROOT / "customer_portal.py").read_text(encoding="utf-8")
		self.template = (APP_ROOT / "www" / "customer_portal.html").read_text(encoding="utf-8")

	def test_browser_endpoint_accepts_only_invoice_name(self):
		tree = ast.parse(self.service)
		request_fn = next(
			node
			for node in tree.body
			if isinstance(node, ast.FunctionDef) and node.name == "request_invoice_payment"
		)
		self.assertEqual([arg.arg for arg in request_fn.args.args], ["invoice_name"])
		for forbidden in (
			"customer:",
			"company:",
			"amount:",
			"payment_gateway",
			"payment_gateway_account:",
		):
			self.assertNotIn(forbidden, ast.get_source_segment(self.service, request_fn) or "")

	def test_server_rederives_customer_and_rechecks_website_permission(self):
		self.assertIn("_assert_customer_portal_user()", self.service)
		self.assertIn("invoice.customer not in customers", self.service)
		self.assertIn('has_website_permission(invoice, "read", frappe.session.user)', self.service)
		self.assertIn("invoice.docstatus != 1 or invoice.is_return", self.service)
		self.assertIn("flt(invoice.outstanding_amount) <= 0", self.service)
		self.assertNotIn("frappe.form_dict", self.service)

	def test_payment_request_creation_is_serialized_and_idempotent(self):
		self.assertIn("for update", self.service)
		self.assertIn("invoice.reload()", self.service)
		self.assertIn('"reference_doctype": "Sales Invoice"', self.service)
		self.assertIn('"reference_name": invoice.name', self.service)
		self.assertIn('"docstatus": 1', self.service)
		self.assertIn("REUSABLE_PAYMENT_REQUEST_STATUSES", self.service)
		self.assertIn("reused=True", self.service)
		self.assertIn("reused=False", self.service)

	def test_native_erpnext_gateway_and_amount_authority_are_used(self):
		self.assertIn("get_gateway_details(frappe._dict(company=invoice.company))", self.service)
		self.assertIn('gateway.get("payment_account")', self.service)
		self.assertIn(
			'str(gateway.get("payment_channel") or "").strip() == "Phone"',
			self.service,
		)
		self.assertIn("get_amount(invoice, gateway.get(\"payment_account\"))", self.service)
		self.assertIn('"payment_request_type": "Inward"', self.service)
		self.assertIn('"party": invoice.customer', self.service)
		self.assertIn('"company": invoice.company', self.service)
		self.assertIn('"mute_email": 1', self.service)
		self.assertIn("payment_request.flags.ignore_permissions = True", self.service)
		self.assertIn("payment_request.submit()", self.service)

	def test_portal_does_not_post_accounting_documents_or_ledgers(self):
		combined = self.service + "\n" + self.portal + "\n" + self.template
		self.assertNotIn('frappe.new_doc("Payment Entry")', combined)
		self.assertNotIn('frappe.get_doc("GL Entry"', combined)
		self.assertNotIn('frappe.get_doc("Stock Ledger Entry"', combined)
		self.assertNotIn('frappe.db.set_value("GL Entry"', combined)
		self.assertNotIn('frappe.db.set_value("Stock Ledger Entry"', combined)
		self.assertIn('"payment_entry_created_by_portal": False', self.portal)

	def test_portal_payment_state_is_customer_invoice_derived(self):
		self.assertIn("def _payment_request_states(invoice_names", self.portal)
		self.assertIn('"reference_name": ["in", invoice_names]', self.portal)
		self.assertIn('doctype == "Sales Invoice"', self.portal)
		self.assertIn('int(getattr(row, "docstatus", 0) or 0) == 1', self.portal)
		self.assertIn('not int(getattr(row, "is_return", 0) or 0)', self.portal)
		self.assertIn("outstanding > 0", self.portal)
		self.assertIn('"payment_request_native_erpnext": True', self.portal)
		self.assertIn('"payment_gateway_browser_selectable": False', self.portal)

	def test_portal_action_is_post_only_and_sends_no_payment_authority_fields(self):
		self.assertIn('class="edge-portal-pay"', self.template)
		self.assertIn('data-invoice-name="{{ row.name }}"', self.template)
		self.assertIn(
			'method: "retailedge.customer_portal_payment.request_invoice_payment"',
			self.template,
		)
		self.assertIn('type: "POST"', self.template)
		self.assertIn("args: { invoice_name: invoiceName }", self.template)
		self.assertNotIn("customer: customer", self.template)
		self.assertNotIn("amount: amount", self.template)
		self.assertNotIn("payment_gateway:", self.template)
		self.assertIn("Pay Invoice", self.template)
		self.assertIn("Continue Payment", self.portal)

	def test_customer_facing_payment_copy_remains_product_neutral(self):
		for source in (self.service, self.template):
			self.assertNotIn("RetailEdge", source)
			self.assertNotIn("ProcessEdge", source)
			self.assertNotIn("Powered by", source)
