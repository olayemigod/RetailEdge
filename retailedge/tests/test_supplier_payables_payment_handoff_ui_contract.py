from __future__ import annotations

from pathlib import Path
from unittest import TestCase


APP_ROOT = Path(__file__).resolve().parents[1]


class TestSupplierPayablesPaymentHandoffUIContract(TestCase):
	def test_supplier_payables_reuses_governed_edgesuite_payment_dialog(self):
		component = (
			APP_ROOT / "public" / "js" / "purchase_reporting" / "PurchaseReportingReport.vue"
		).read_text()

		self.assertIn("window.EdgeSuiteUI", component)
		self.assertIn('import SimplePaymentDialog from "../retailedge_business_hub/SimplePaymentDialog.vue"', component)
		self.assertIn('v-if="reportType === \'supplier_payables\'"', component)
		self.assertIn('intent="pay-supplier"', component)
		self.assertIn(':initialContext="supplierPaymentContext"', component)
		self.assertIn('fieldname: "payment_action"', component)
		self.assertIn('payment_action: "Pay Supplier"', component)
		self.assertIn("openSupplierPayment(row)", component)
		self.assertIn('party: row.supplier', component)
		self.assertIn('reference_name: row.invoice', component)
		self.assertIn('company: this.filters.company || ""', component)
		self.assertIn('branch: row.branch || this.filters.branch || ""', component)
		self.assertIn("handleSupplierPaymentSaved", component)
		self.assertIn('frappe.set_route("Form", "Payment Entry", result.name)', component)

	def test_payment_action_is_local_to_supplier_payables_and_keeps_accounting_native(self):
		component = (
			APP_ROOT / "public" / "js" / "purchase_reporting" / "PurchaseReportingReport.vue"
		).read_text()

		self.assertIn('if (this.reportType === "supplier_payables")', component)
		self.assertIn('this.rows = this.reportType === "supplier_payables"', component)
		self.assertIn('purchase_register:', component)
		self.assertIn('supplier_payables:', component)
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
