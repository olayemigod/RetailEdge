from __future__ import annotations

from pathlib import Path
from unittest import TestCase

APP_ROOT = Path(__file__).resolve().parents[1]


class TestCustomerPortalContract(TestCase):
	def test_backend_derives_customer_from_erpnext_portal_user_links(self):
		source = (APP_ROOT / "customer_portal.py").read_text()
		self.assertIn('get_parents_for_user("Customer")', source)
		self.assertIn('"Customer" not in frappe.get_roles(frappe.session.user)', source)
		self.assertIn('frappe.session.user == "Guest"', source)
		self.assertIn("is_website_user()", source)
		self.assertIn("MAX_PORTAL_ROWS = 200", source)
		self.assertIn('"customer_filter_server_derived": True', source)
		self.assertIn('"cross_customer_selection": False', source)
		self.assertNotIn("customer: str", source)
		self.assertNotIn("customer=None", source)

	def test_customer_filtered_ignore_permissions_is_not_browser_controlled(self):
		source = (APP_ROOT / "customer_portal.py").read_text()
		self.assertIn("def _customer_filter", source)
		self.assertIn('filters["customer"] = ["in", customers]', source)
		self.assertIn('filters.update({"quotation_to": "Customer", "party_name": ["in", customers]})', source)
		self.assertIn("ignore_permissions=True", source)
		self.assertIn("Portal User -> Customer links", source)
		self.assertNotIn("frappe.form_dict", source)

	def test_portal_covers_core_customer_commercial_documents(self):
		source = (APP_ROOT / "customer_portal.py").read_text()
		for doctype in ("Quotation", "Sales Order", "Sales Invoice", "Delivery Note", "Project"):
			self.assertIn(f'"doctype": "{doctype}"', source)
		self.assertIn("outstanding_amount", source)
		self.assertIn("grand_total", source)
		self.assertIn("percent_complete", source)

	def test_overdue_receivables_use_sales_invoice_due_date_and_outstanding_truth(self):
		source = (APP_ROOT / "customer_portal.py").read_text()
		self.assertIn('fields=["name", "grand_total", "outstanding_amount", "currency", "status", "due_date"]', source)
		self.assertIn("flt(row.outstanding_amount) > 0", source)
		self.assertIn("getdate(row.due_date) < today_date", source)
		self.assertIn('"overdue_count": len(overdue_rows)', source)
		self.assertIn('"overdue_amount": sum(flt(row.outstanding_amount) for row in overdue_rows)', source)
		self.assertIn("Submitted Sales Invoice due date plus positive outstanding amount", source)

	def test_payment_history_is_customer_scoped_submitted_and_read_only(self):
		source = (APP_ROOT / "customer_portal.py").read_text()
		self.assertIn('"Payment Entry"', source)
		self.assertIn('"docstatus": 1', source)
		self.assertIn('"payment_type": "Receive"', source)
		self.assertIn('"party_type": "Customer"', source)
		self.assertIn('"party": ["in", customers]', source)
		self.assertIn('"payment_history_read_only": True', source)
		self.assertIn("not a wallet balance", source)
		self.assertNotIn("frappe.new_doc(\"Payment Entry\")", source)
		self.assertNotIn("submit()", source)

	def test_portal_pdf_download_uses_website_permission_and_server_selected_format(self):
		source = (APP_ROOT / "customer_portal_download.py").read_text()
		for doctype in ("Quotation", "Sales Order", "Sales Invoice", "Delivery Note"):
			self.assertIn(f'"{doctype}"', source)
		self.assertIn('has_website_permission(doc, "read", frappe.session.user)', source)
		self.assertIn("_assert_customer_portal_user()", source)
		self.assertIn("get_preferred_print_format(doctype)", source)
		self.assertIn("MANAGED_MARKER", source)
		self.assertIn('return "Standard"', source)
		self.assertIn("frappe.get_print(", source)
		self.assertIn("as_pdf=True", source)
		self.assertIn('frappe.local.response.type = "download"', source)
		self.assertNotIn("customer: str", source)
		self.assertNotIn("print_format: str", source)
		self.assertNotIn("ignore_permissions=True", source)

	def test_portal_download_urls_are_server_generated_and_not_available_for_projects(self):
		source = (APP_ROOT / "customer_portal.py").read_text()
		self.assertIn('PORTAL_DOWNLOAD_DOCTYPES = {"Quotation", "Sales Order", "Sales Invoice", "Delivery Note"}', source)
		self.assertIn("def _portal_download_url", source)
		self.assertIn("customer_portal_download.download_customer_document_pdf", source)
		self.assertIn('"download_url": _portal_download_url(doctype, row.name)', source)
		self.assertIn('"portal_pdf_uses_website_permission": True', source)
		self.assertIn('"portal_pdf_print_format_browser_selectable": False', source)

	def test_website_controller_redirects_guest_and_uses_configured_company_identity(self):
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
		self.assertIn("Payment history is read-only", template)
		self.assertIn("Download PDF", template)
		self.assertIn("Document pages and PDF downloads use ERPNext customer website permissions", template)
		self.assertNotIn("RetailEdge", template)
		self.assertNotIn("ProcessEdge", template)
		self.assertNotIn("Powered by", template)


if __name__ == "__main__":
	import unittest
	unittest.main()
