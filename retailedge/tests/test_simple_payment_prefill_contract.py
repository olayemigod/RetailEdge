from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestSimplePaymentPrefillContract(TestCase):
	def test_prefilled_invoice_is_revalidated_before_default_allocation(self):
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePaymentDialog.vue"
		).read_text()

		self.assertIn('initialContext: { type: Object, default: () => ({}) }', component)
		self.assertIn("applyInitialContext", component)
		self.assertIn(
			'const REFERENCE_METHOD = "retailedge.guided_payment.get_simple_payment_reference_details"',
			component,
		)
		self.assertIn("const details = await callMethod(REFERENCE_METHOD", component)
		self.assertIn("details.outstanding_amount", component)
		self.assertIn("const requestedReferenceNames =", component)
		self.assertIn("const referenceNames = requestedReferenceNames.slice(0, maxReferences)", component)
		self.assertIn("for (const name of referenceNames)", component)
		self.assertIn("reference_name: name", component)
		self.assertIn("party: this.values.party", component)
		self.assertNotIn("initial.outstanding_amount", component)
		self.assertNotIn("initial.allocated_amount", component)

	def test_prefill_supports_sales_invoice_receipt_and_sales_order_advance(self):
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePaymentDialog.vue"
		).read_text()
		self.assertIn('["receive-customer-payment", "receive-sales-order-payment"].includes(this.intent)', component)
		self.assertIn("const referenceName = cleanPrefill(initial.reference_name)", component)
		self.assertIn("referenceName ? [referenceName, ...initialReferences] : initialReferences", component)
		self.assertIn("reference_name: name", component)
		self.assertIn("one Sales Order advance", component)

	def test_quick_payment_caps_one_reference_while_supplier_payables_can_use_managed_multi_reference(self):
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePaymentDialog.vue"
		).read_text()

		self.assertIn("Number(this.formContext.limits?.max_references || 1)", component)
		self.assertIn("Quick Payment supports one payable reference.", component)
		self.assertIn("validateStandardCustomerDraft()", component)
		self.assertIn("Quick Receive Customer Payment supports one Sales Invoice or Sales Order reference.", component)
		self.assertIn("managed: this.allowMultiReferenceSupplierPayment ? 1 : 0", component)

	def test_supplier_payables_can_prefill_multiple_revalidated_references_without_trusting_report_amounts(self):
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePaymentDialog.vue"
		).read_text()

		self.assertIn("allowMultiReferenceSupplierPayment", component)
		self.assertIn("Array.isArray(initial.references)", component)
		self.assertIn("for (const name of referenceNames)", component)
		self.assertIn("details.outstanding_amount", component)
		self.assertIn("resolved.reduce", component)
		self.assertIn("Supplier settlement must contain between 1 and", component)
		self.assertNotIn("initial.outstanding_amount", component)
		self.assertNotIn("initial.allocated_amount", component)

	def test_prefill_preserves_existing_draft_payment_service_and_stale_value_clearing(self):
		component = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePaymentDialog.vue"
		).read_text()

		self.assertIn(
			'const CREATE_METHOD = "retailedge.guided_payment.create_simple_payment_draft"',
			component,
		)
		self.assertIn("const result = await callMethod(CREATE_METHOD", component)
		self.assertIn("setParty(next)", component)
		self.assertIn("setBranch(next)", component)
		self.assertGreaterEqual(component.count("this.values.references = [emptyReference()]"), 2)
		self.assertIn("EdgeModal", component)
		self.assertIn("EdgeLinkField", component)
		self.assertIn("EdgeChildTable", component)
		self.assertIn("window.EdgeSuiteUI", component)
		self.assertNotIn("window.EdgeUI", component)
		self.assertNotIn("frappe.ui.Dialog", component)
		self.assertNotIn("frappe.prompt", component)
		self.assertNotIn("frappe.msgprint", component)
		self.assertNotIn("frappe.show_alert", component)
		self.assertNotIn("frappe.db.commit", component)
		self.assertNotIn("frappe.db.set_value", component)
		self.assertNotIn('frappe.new_doc("GL Entry")', component)
		self.assertNotIn('frappe.new_doc("Payment Ledger Entry")', component)


if __name__ == "__main__":
	import unittest

	unittest.main()
