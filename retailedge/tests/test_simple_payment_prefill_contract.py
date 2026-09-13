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
		self.assertIn("reference_name: referenceName", component)
		self.assertIn("party: this.values.party", component)
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
