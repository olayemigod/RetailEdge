from __future__ import annotations

import ast
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestCustomerPortalContract(unittest.TestCase):
	def test_portal_service_derives_customer_identity_and_scopes_every_query(self):
		source = (APP_ROOT / "customer_portal.py").read_text()
		self.assertIn('get_parents_for_user("Customer")', source)
		self.assertIn('"customer": ("in", customer_names)', source)
		self.assertIn('"party": ("in", customer_names)', source)
		self.assertIn('"party_type": "Customer"', source)
		self.assertIn('"docstatus": 1', source)
		self.assertIn('"is_group": 0', source)
		self.assertNotIn("ignore_permissions", source)

	def test_portal_service_uses_website_permission_and_erpnext_documents(self):
		source = (APP_ROOT / "customer_portal.py").read_text()
		for doctype in ("Quotation", "Sales Order", "Sales Invoice", "Delivery Note", "Project"):
			self.assertIn(doctype, source)
		self.assertIn("has_website_permission", source)
		self.assertIn("outstanding_amount", source)
		self.assertIn("due_date", source)
		self.assertIn("is_return", source)
		self.assertIn("Payment Entry", source)
		self.assertNotIn("GL Entry", source)
		self.assertNotIn("Stock Ledger Entry", source)

	def test_portal_download_accepts_only_document_identity_and_rechecks_access(self):
		source = (APP_ROOT / "customer_portal_download.py").read_text()
		self.assertIn("ALLOWED_DOCTYPES", source)
		self.assertIn("def download_document_pdf(doctype: str, name: str)", source)
		self.assertIn("has_website_permission", source)
		self.assertIn("get_pdf", source)
		self.assertNotIn("customer:", source)
		self.assertNotIn("print_format:", source)
		self.assertNotIn("/public/files", source)

	def test_portal_page_requires_login_and_uses_company_identity(self):
		source = (APP_ROOT / "www" / "customer_portal.py").read_text()
		self.assertIn('redirect_location = "/login?redirect-to=/customer_portal"', source)
		self.assertIn('context.title = "Customer Portal"', source)
		self.assertIn('frappe.defaults.get_global_default("default_company")', source)
		self.assertIn("context.company_name = company_name", source)
		self.assertNotIn("RetailEdge", source)
		self.assertNotIn("ProcessEdge", source)

	def test_portal_menu_setup_is_additive_customer_only_and_migrated(self):
		source = (APP_ROOT / "customer_portal_setup.py").read_text()
		patches = (APP_ROOT / "patches.txt").read_text()
		self.assertIn('CUSTOMER_PORTAL_ROUTE = "/customer_portal"', source)
		self.assertIn('"role": "Customer"', source)
		self.assertIn('settings.append(\n\t\t"menu"', source)
		self.assertIn("next((item for item in (settings.get(\"menu\") or [])", source)
		self.assertNotIn("settings.set(\"menu\"", source)
		self.assertIn("retailedge.patches.install_customer_portal_menu", patches)

	def test_portal_ui_is_edgesuite_ready_and_product_neutral(self):
		template = (APP_ROOT / "www" / "customer_portal.html").read_text()
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
		self.assertIn("Download PDF", template)
		self.assertIn("Document pages and PDF downloads use ERPNext customer website permissions", template)
		self.assertNotIn("RetailEdge", template)
		self.assertNotIn("ProcessEdge", template)
		self.assertNotIn("Powered by", template)


if __name__ == "__main__":
	unittest.main()
