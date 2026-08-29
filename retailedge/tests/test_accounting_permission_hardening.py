from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestAccountingPermissionHardening(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_recent_selling_documents_are_operating_context_scoped(self):
		source = self.read("professional_selling.py")
		self.assertIn("def _operating_document_filters", source)
		self.assertIn("get_first_existing_field(doctype, BRANCH_FIELD_CANDIDATES)", source)
		self.assertIn("validate_user_branch_access(", source)
		self.assertIn("filters = _operating_document_filters(doctype, company=company, branch=branch)", source)
		self.assertIn("frappe.get_list(\n\t\tdoctype,\n\t\tfilters=filters,", source)

	def test_sales_invoice_recent_list_and_source_search_are_context_scoped(self):
		source = self.read("professional_sales_invoice.py")
		self.assertIn("_operating_document_filters", source)
		self.assertIn('filters = _operating_document_filters("Sales Invoice", company=company, branch=branch)', source)
		self.assertIn("company, branch, _warehouse = _validate_context(values)", source)
		self.assertIn('filters.update(_operating_document_filters(config["doctype"], company=company, branch=branch))', source)
		self.assertIn("_validate_source_context(source, source_label=source_doctype)", source)

	def test_advance_discovery_never_silently_spans_companies(self):
		source = self.read("advanced_payments.py")
		self.assertIn("def _resolve_advance_scope", source)
		self.assertIn("get_operating_context()", source)
		self.assertIn('frappe.defaults.get_user_default("Company")', source)
		self.assertIn('frappe.throw(_("Choose an Operating Company before viewing customer advances."))', source)
		self.assertIn('"company": company,', source)
		self.assertIn("company, branch = _resolve_advance_scope(company, branch)", source)
		self.assertIn("validate_user_branch_access(", source)

	def test_payment_and_invoice_branches_are_independently_authorized_before_reconciliation(self):
		source = self.read("payment_application.py")
		self.assertIn("invoice_branch = _invoice_branch(invoice)", source)
		self.assertIn("payment_branch = _payment_branch(payment)", source)
		self.assertIn("if invoice_branch:", source)
		self.assertIn("if payment_branch:", source)
		self.assertIn("company=payment.company", source)
		self.assertIn("reconciliation.reconcile()", source)

	def test_guided_payment_uses_shared_branch_fields_and_authorizes_reference_branch(self):
		source = self.read("guided_payment.py")
		self.assertIn("BRANCH_FIELD_CANDIDATES", source)
		self.assertIn("get_first_existing_field", source)
		self.assertIn('branch_field = get_first_existing_field(config["reference_doctype"], BRANCH_FIELD_CANDIDATES)', source)
		self.assertIn("filters[branch_field] = branch", source)
		self.assertIn("reference_branch = row.get(branch_field) if branch_field else None", source)
		self.assertIn("validate_user_branch_access(reference_branch", source)
		self.assertIn("payment_branch_field = get_first_existing_field(PAYMENT_ENTRY_DOCTYPE, BRANCH_FIELD_CANDIDATES)", source)
		self.assertIn("doc.set(payment_branch_field, branch)", source)
		self.assertNotIn("same RetailEdge Branch", source)

	def test_project_spend_routes_require_company_and_permission_aware_cost_center(self):
		source = self.read("project_expense_routing.py")
		self.assertIn('_assert_read("Company", doc.company)', source)
		self.assertIn('if cost_center and not _can_read("Cost Center", cost_center):', source)
		self.assertIn('cost_center = ""', source)
		self.assertIn("frappe.has_permission(doctype, \"create\")", source)
		self.assertIn("Purchasing, stock, Budget and accounting controls remain authoritative", source)
		self.assertNotIn("RetailEdge does not maintain a generic project expense", source)

	def test_guided_accounting_paths_do_not_directly_write_submitted_accounting_truth(self):
		for relative in (
			"professional_sales_invoice.py",
			"advanced_payments.py",
			"payment_application.py",
			"project_receipts.py",
			"guided_payment.py",
			"project_expense_routing.py",
		):
			source = self.read(relative)
			for forbidden in (
				'frappe.db.set_value("Sales Invoice"',
				'frappe.db.set_value("GL Entry"',
				'frappe.db.set_value("Stock Ledger Entry"',
				'frappe.new_doc("GL Entry")',
				'frappe.new_doc("Stock Ledger Entry")',
			):
				self.assertNotIn(forbidden, source, msg=f"{relative} contains unsafe accounting write {forbidden}")

	def test_runtime_errors_and_policies_do_not_expose_product_branding(self):
		conversion = self.read("quotation_invoice_conversion.py")
		project_receipts = self.read("project_receipts.py")
		advanced = self.read("advanced_payments.py")
		guided_payment = self.read("guided_payment.py")
		project_operations = self.read("project_operations.py")
		project_routing = self.read("project_expense_routing.py")
		visible_sources = conversion + project_receipts + advanced + guided_payment + project_operations + project_routing
		for visible_error in (
			"RetailEdge direct Quotation to Sales Invoice tracking",
			"RetailEdge could not complete",
			"RetailEdge could not find",
			"RetailEdge direct-invoice conversion reservation",
			"RetailEdge Payment Entry branch attribution",
			"same RetailEdge Branch",
			"no RetailEdge project wallet",
			"RetailEdge does not maintain a generic project expense",
		):
			self.assertNotIn(visible_error, visible_sources)
		# Stable internal identities remain intentionally unchanged.
		self.assertIn('CONVERSION_DOCTYPE = "RetailEdge Quotation Invoice Conversion"', conversion)


if __name__ == "__main__":
	unittest.main()
