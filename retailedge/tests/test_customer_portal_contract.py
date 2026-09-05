from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestCustomerPortalContract(unittest.TestCase):
	def test_portal_service_derives_customer_identity_before_permission_bypass(self):
		source = (APP_ROOT / "customer_portal.py").read_text(encoding="utf-8")
		self.assertIn('get_parents_for_user("Customer")', source)
		self.assertIn('if "Customer" not in frappe.get_roles(frappe.session.user)', source)
		self.assertIn('filters.update({"quotation_to": "Customer", "party_name": ["in", customers]})', source)
		self.assertIn('filters["customer"] = ["in", customers]', source)
		self.assertIn("merged = _customer_filter(doctype, customers)", source)
		self.assertIn("strictly server-derived from Portal User -> Customer links", source)
		self.assertIn("ignore_permissions=True", source)
		self.assertNotIn('frappe.form_dict.get("customer")', source)

	def test_portal_service_uses_only_customer_owned_erpnext_documents_and_read_only_payment_history(self):
		source = (APP_ROOT / "customer_portal.py").read_text(encoding="utf-8")
		for doctype in ("Quotation", "Sales Order", "Sales Invoice", "Delivery Note", "Project"):
			self.assertIn(doctype, source)
		self.assertIn('"party_type": "Customer"', source)
		self.assertIn('"party": ["in", customers]', source)
		self.assertIn('"docstatus": 1', source)
		self.assertIn("outstanding_amount", source)
		self.assertIn("due_date", source)
		self.assertIn("is_return", source)
		self.assertIn("Payment Entry", source)
		self.assertIn('"payment_history_read_only": True', source)
		self.assertIn('"cross_customer_selection": False', source)
		self.assertNotIn("frappe.new_doc(\"Payment Entry\")", source)
		self.assertNotIn("GL Entry", source)
		self.assertNotIn("Stock Ledger Entry", source)

	def test_portal_download_accepts_only_document_identity_and_rechecks_website_access(self):
		source = (APP_ROOT / "customer_portal_download.py").read_text(encoding="utf-8")
		self.assertIn("PORTAL_DOWNLOAD_DOCTYPES", source)
		self.assertIn("def download_customer_document_pdf(doctype: str, name: str):", source)
		self.assertIn("_assert_customer_portal_user()", source)
		self.assertIn("has_website_permission(doc, \"read\", frappe.session.user)", source)
		self.assertIn("print_format = _portal_print_format(doc.doctype)", source)
		self.assertIn("frappe.get_print(", source)
		self.assertIn("as_pdf=True", source)
		self.assertIn('response.type = "download"', source)
		self.assertNotIn("def download_customer_document_pdf(doctype: str, name: str, print_format", source)
		self.assertNotIn('frappe.form_dict.get("customer")', source)
		self.assertNotIn("/public/files", source)

	def test_portal_print_format_is_server_selected_and_restricted_to_standard_or_managed_output(self):
		source = (APP_ROOT / "customer_portal_download.py").read_text(encoding="utf-8")
		self.assertIn("get_preferred_print_format(doctype)", source)
		self.assertIn('return "Standard"', source)
		self.assertIn('str(row.get("module") or "") == "RetailEdge"', source)
		self.assertIn("MANAGED_MARKER", source)
		self.assertIn("cint(row.get(\"disabled\"))", source)
		self.assertNotIn("frappe.form_dict.get(\"print_format\")", source)

	def test_portal_page_requires_login_and_uses_configured_company_identity(self):
		source = (APP_ROOT / "www" / "customer_portal.py").read_text(encoding="utf-8")
		self.assertIn('redirect_location = "/login?redirect-to=/customer_portal"', source)
		self.assertIn('context.title = "Customer Portal"', source)
		self.assertIn('frappe.defaults.get_global_default("default_company")', source)
		self.assertIn("context.company_name = company_name", source)
		self.assertIn("get_customer_advance_summary(portal.get(\"customer_names\") or [])", source)
		self.assertIn('portal.setdefault("routes", {})["account_statement"]', source)
		self.assertNotIn("RetailEdge", source)
		self.assertNotIn("ProcessEdge", source)

	def test_portal_menu_setup_is_additive_customer_only_and_migrated(self):
		source = (APP_ROOT / "customer_portal_setup.py").read_text(encoding="utf-8")
		patches = (APP_ROOT / "patches.txt").read_text(encoding="utf-8")
		self.assertIn('CUSTOMER_PORTAL_ROUTE = "/customer_portal"', source)
		self.assertIn('"role": "Customer"', source)
		self.assertIn('settings.append(\n\t\t"menu"', source)
		self.assertIn('next((item for item in (settings.get("menu") or [])', source)
		self.assertNotIn('settings.set("menu"', source)
		self.assertIn("retailedge.patches.install_customer_portal_menu", patches)

	def test_portal_ui_is_edgesuite_ready_financially_explicit_and_product_neutral(self):
		template = (APP_ROOT / "www" / "customer_portal.html").read_text(encoding="utf-8")
		self.assertIn('data-edge-suite-ready="true"', template)
		self.assertIn("--edge-portal-surface:var(--edge-color-surface", template)
		self.assertIn("--edge-portal-accent:var(--edge-color-primary", template)
		self.assertIn('{{ company_name or "Customer Portal" }}', template)
		self.assertIn("Outstanding", template)
		self.assertIn("Overdue", template)
		self.assertIn("Overdue since", template)
		self.assertIn("Payments Received", template)
		self.assertIn("edge-portal-row-static", template)
		self.assertIn("{{ portal.payment_summary.scope_note }}", template)
		self.assertIn('row.payment_action_label or "Pay Invoice"', template)
		self.assertIn("Invoice payment actions are revalidated on the server", template)
		self.assertIn("Available advances are read-only ERPNext payment balances and are not a wallet", template)
		self.assertIn("Available advances remain ERPNext unallocated Payment Entry amounts", template)
		self.assertIn("Advances & Statements", template)
		self.assertIn("Download PDF", template)
		self.assertIn("Document pages and PDF downloads use ERPNext customer website permissions", template)
		self.assertNotIn("RetailEdge", template)
		self.assertNotIn("ProcessEdge", template)
		self.assertNotIn("Powered by", template)


if __name__ == "__main__":
	unittest.main()
