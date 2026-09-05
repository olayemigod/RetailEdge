from __future__ import annotations

from pathlib import Path
from unittest import TestCase

APP_ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = APP_ROOT / "receivables_collections.py"
ACTIONS = APP_ROOT / "receivables_actions.py"
RECEIVABLES = APP_ROOT / "customer_receivables.py"
COMPONENT = APP_ROOT / "public" / "js" / "customer_receivables" / "CustomerReceivablesReport.vue"


class TestCustomerReceivablesCollections(TestCase):
	def setUp(self):
		self.collections = COLLECTIONS.read_text(encoding="utf-8")
		self.actions = ACTIONS.read_text(encoding="utf-8")
		self.receivables = RECEIVABLES.read_text(encoding="utf-8")
		self.component = COMPONENT.read_text(encoding="utf-8")

	def test_collections_enrichment_uses_native_permission_filtered_documents(self):
		self.assertIn('frappe.has_permission(doctype, "read")', self.collections)
		self.assertIn('frappe.get_list(\n\t\t"Payment Request"', self.collections)
		self.assertIn('frappe.get_list(\n\t\t"Dunning"', self.collections)
		self.assertIn('"company": company', self.collections)
		self.assertNotIn('frappe.get_all(\n\t\t"Dunning"', self.collections)
		self.assertNotIn("ignore_permissions", self.collections)

	def test_dunning_lookup_and_readiness_use_native_child_sources(self):
		self.assertIn('frappe.get_all(\n\t\t"Overdue Payment"', self.collections)
		self.assertIn('"parenttype": "Dunning"', self.collections)
		self.assertIn('"parentfield": "overdue_payments"', self.collections)
		self.assertIn('"sales_invoice": ["in", invoice_names]', self.collections)
		self.assertIn('"name": ["in", list(invoices_by_parent)]', self.collections)
		self.assertIn('frappe.get_all(\n\t\t"Payment Schedule"', self.collections)
		self.assertIn('float(row.outstanding or 0) > 0', self.collections)
		self.assertIn('getdate(row.due_date) < today_date', self.collections)
		self.assertIn("already-permitted invoice", self.collections)

	def test_collections_enrichment_is_bounded_and_only_exposes_draft_handoffs(self):
		self.assertIn("MAX_COLLECTION_ROWS = 2000", self.collections)
		self.assertGreaterEqual(self.collections.count("limit=MAX_COLLECTION_ROWS"), 4)
		self.assertIn('"read_only_enrichment": True', self.collections)
		self.assertIn('"draft_handoffs_only": True', self.collections)
		self.assertIn('"automatic_submit": False', self.collections)
		for forbidden in (
			'frappe.new_doc("Payment Request")',
			'frappe.new_doc("Dunning")',
			".submit()",
			".insert(",
			"frappe.db.commit",
			"frappe.db.set_value",
		):
			self.assertNotIn(forbidden, self.collections)

	def test_row_actions_require_native_create_permission_and_no_active_document(self):
		self.assertIn('_can_create_doctype("Payment Request")', self.collections)
		self.assertIn('_can_create_doctype("Dunning")', self.collections)
		self.assertIn('ACTIVE_DUNNING_STATUSES = {"Draft", "Unresolved"}', self.collections)
		self.assertIn('ACTIVE_PAYMENT_REQUEST_STATUSES = {"Draft", "Requested", "Initiated", "Partially Paid", "Failed"}', self.collections)
		self.assertIn("outstanding > 0 and not payment_request and payment_request_create_allowed", self.collections)
		self.assertIn("invoice in dunning_eligible and not dunning and dunning_create_allowed", self.collections)
		self.assertIn('_("Prepare Payment Request")', self.collections)
		self.assertIn('_("Prepare Dunning")', self.collections)

	def test_payment_request_state_uses_native_invoice_reference_and_includes_drafts(self):
		self.assertIn('"reference_doctype": "Sales Invoice"', self.collections)
		self.assertIn('"reference_name": ["in", invoice_names]', self.collections)
		self.assertIn('"docstatus": ["<", 2]', self.collections)
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
		self.assertNotIn("ignore_permissions", self.receivables)

	def test_collection_actions_revalidate_invoice_company_and_branch(self):
		self.assertIn('frappe.has_permission("Sales Invoice", "read", doc=invoice.name)', self.actions)
		self.assertIn('frappe.has_permission("Company", "read", doc=invoice.company)', self.actions)
		self.assertIn("validate_user_branch_access(", self.actions)
		self.assertIn("get_user_allowed_branches", self.actions)
		self.assertIn("user_has_global_branch_access", self.actions)
		self.assertIn("select name from `tabSales Invoice` where name=%s for update", self.actions)
		self.assertGreaterEqual(self.actions.count("_assert_invoice_scope(invoice)"), 2)

	def test_hidden_existing_native_records_block_duplicates_without_identifier_leak(self):
		self.assertIn("Existence detection is intentionally permissionless", self.actions)
		self.assertIn('frappe.get_all(\n\t\t"Payment Request"', self.actions)
		self.assertIn('frappe.get_all(\n\t\t"Dunning"', self.actions)
		self.assertIn('if not frappe.has_permission(doctype, "read", doc=row.name):', self.actions)
		self.assertIn('_visible_existing_or_block("Payment Request"', self.actions)
		self.assertIn('_visible_existing_or_block("Dunning"', self.actions)
		self.assertIn(
			"An active {0} already exists for this Sales Invoice but is not accessible to you.",
			self.actions,
		)
		self.assertNotIn("but is not accessible to you: {", self.actions)
		self.assertIn(
			'if not payment_request.is_new() and not frappe.has_permission(\n\t\t"Payment Request", "read", doc=payment_request.name',
			self.actions,
		)

	def test_payment_request_handoff_uses_native_constructor_and_stops_at_draft(self):
		self.assertIn("from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request", self.actions)
		self.assertIn('@frappe.whitelist(methods=["POST"])\ndef prepare_payment_request', self.actions)
		self.assertIn('frappe.has_permission("Payment Request", "create", throw=True)', self.actions)
		self.assertIn("existing = _active_payment_request(invoice.name)", self.actions)
		self.assertIn('dt="Sales Invoice"', self.actions)
		self.assertIn("submit_doc=0", self.actions)
		self.assertIn("mute_email=1", self.actions)
		self.assertIn("if payment_request.is_new():", self.actions)
		self.assertIn("payment_request.insert()", self.actions)
		self.assertIn("payment_request.docstatus != 0", self.actions)
		self.assertNotIn("payment_request.submit()", self.actions)

	def test_dunning_handoff_uses_native_mapper_and_native_schedule_eligibility(self):
		self.assertIn("from erpnext.accounts.doctype.sales_invoice.sales_invoice import create_dunning", self.actions)
		self.assertIn('@frappe.whitelist(methods=["POST"])\ndef prepare_dunning', self.actions)
		self.assertIn('frappe.has_permission("Dunning", "create", throw=True)', self.actions)
		self.assertIn("_has_overdue_payment_schedule(invoice)", self.actions)
		self.assertIn('flt(row.get("outstanding")) > 0', self.actions)
		self.assertIn("existing = _active_dunning(invoice.name, company=invoice.company)", self.actions)
		self.assertIn("create_dunning(invoice.name, ignore_permissions=False)", self.actions)
		self.assertIn("dunning.insert()", self.actions)
		self.assertIn("dunning.docstatus != 0", self.actions)
		self.assertNotIn("dunning.submit()", self.actions)

	def test_collection_actions_never_mutate_invoice_or_accounting_ledgers(self):
		for forbidden in (
			"invoice.save(",
			"invoice.db_set(",
			'frappe.db.set_value("Sales Invoice"',
			'frappe.new_doc("Payment Entry")',
			'frappe.new_doc("GL Entry")',
			'frappe.new_doc("Payment Ledger Entry")',
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, self.actions)

	def test_edgesuite_report_exposes_post_only_native_draft_handoffs(self):
		self.assertIn('function callPostMethod(method, args = {})', self.component)
		self.assertIn('type: "POST"', self.component)
		self.assertIn('fieldname: "payment_request_action"', self.component)
		self.assertIn('fieldname: "dunning_action"', self.component)
		self.assertIn('"retailedge.receivables_actions.prepare_payment_request"', self.component)
		self.assertIn('"retailedge.receivables_actions.prepare_dunning"', self.component)
		self.assertIn('frappe.set_route("Form", result.doctype, result.name)', self.component)
		self.assertIn("prepare native drafts only", self.component)
		self.assertIn("nothing is submitted automatically", self.component)
		self.assertNotIn('frappe.new_doc("Dunning")', self.component)
		self.assertNotIn('frappe.new_doc("Payment Request")', self.component)


if __name__ == "__main__":
	import unittest

	unittest.main()
