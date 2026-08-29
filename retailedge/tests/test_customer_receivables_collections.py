from __future__ import annotations

from pathlib import Path
from unittest import TestCase

APP_ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = APP_ROOT / "receivables_collections.py"
RECEIVABLES = APP_ROOT / "customer_receivables.py"
COMPONENT = APP_ROOT / "public" / "js" / "customer_receivables" / "CustomerReceivablesReport.vue"


class TestCustomerReceivablesCollections(TestCase):
	def setUp(self):
		self.collections = COLLECTIONS.read_text(encoding="utf-8")
		self.receivables = RECEIVABLES.read_text(encoding="utf-8")
		self.component = COMPONENT.read_text(encoding="utf-8")

	def test_collections_enrichment_uses_native_permission_filtered_documents(self):
		self.assertIn('frappe.has_permission(doctype, "read")', self.collections)
		self.assertIn('frappe.get_list(\n\t\t"Payment Request"', self.collections)
		self.assertIn('frappe.get_list(\n\t\t"Dunning"', self.collections)
		self.assertIn('"company": company', self.collections)
		self.assertIn('doc.check_permission("read")', self.collections)
		self.assertNotIn("ignore_permissions", self.collections)
		self.assertNotIn("frappe.get_all", self.collections)

	def test_collections_enrichment_is_bounded_and_read_only(self):
		self.assertIn("MAX_COLLECTION_ROWS = 2000", self.collections)
		self.assertIn("limit=MAX_COLLECTION_ROWS", self.collections)
		self.assertIn('"read_only_enrichment": True', self.collections)
		for forbidden in (
			'frappe.new_doc("Payment Request")',
			'frappe.new_doc("Dunning")',
			".submit()",
			".insert(",
			"frappe.db.commit",
			"frappe.db.set_value",
		):
			self.assertNotIn(forbidden, self.collections)

	def test_dunning_ready_requires_overdue_native_create_permission_and_no_active_dunning(self):
		self.assertIn('frappe.has_permission("Dunning", "create")', self.collections)
		self.assertIn('ACTIVE_DUNNING_STATUSES = {"Draft", "Unresolved"}', self.collections)
		self.assertIn("overdue and not dunning and dunning_create_allowed", self.collections)
		self.assertIn('return "Dunning Ready"', self.collections)
		self.assertIn('payment.get("sales_invoice")', self.collections)

	def test_payment_request_state_uses_native_invoice_reference_and_active_statuses(self):
		self.assertIn('"reference_doctype": "Sales Invoice"', self.collections)
		self.assertIn('"reference_name": ["in", invoice_names]', self.collections)
		self.assertIn('"docstatus": 1', self.collections)
		self.assertIn("ACTIVE_PAYMENT_REQUEST_STATUSES", self.collections)
		self.assertIn('return f"Payment {payment_request.get(\'status\') or \'Requested\'}"', self.collections)

	def test_receivables_accounting_truth_is_preserved_and_only_enriched(self):
		self.assertIn("enrich_receivable_rows(rows, company=filters.company)", self.receivables)
		self.assertIn('"outstanding_amount"', self.receivables)
		self.assertIn('"docstatus": 1', self.receivables)
		self.assertIn('"is_return": 0', self.receivables)
		self.assertIn('"balance_basis": "current_outstanding"', self.receivables)
		self.assertIn('"label": _("Payment Requests")', self.receivables)
		self.assertIn('"label": _("Dunning Ready")', self.receivables)
		self.assertIn('"fieldname": "payment_request"', self.receivables)
		self.assertIn('"fieldname": "dunning"', self.receivables)
		self.assertIn('"fieldname": "collection_status"', self.receivables)
		self.assertNotIn("ignore_permissions", self.receivables)

	def test_edgesuite_report_opens_only_existing_native_collection_documents(self):
		self.assertIn('["invoice", "customer", "payment_request", "dunning"]', self.component)
		self.assertIn('frappe.set_route("Form", "Payment Request", value)', self.component)
		self.assertIn('frappe.set_route("Form", "Dunning", value)', self.component)
		self.assertIn("Collections status is read-only", self.component)
		self.assertIn("Dunning Ready does not create or submit a Dunning", self.component)
		self.assertNotIn('frappe.new_doc("Dunning")', self.component)
		self.assertNotIn('frappe.new_doc("Payment Request")', self.component)


if __name__ == "__main__":
	import unittest

	unittest.main()
