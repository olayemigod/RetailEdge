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

	def test_website_controller_redirects_guest_and_uses_neutral_title(self):
		source = (APP_ROOT / "www" / "customer_portal.py").read_text()
		self.assertIn('redirect_location = "/login?redirect-to=/customer_portal"', source)
		self.assertIn('context.title = "Customer Portal"', source)
		self.assertNotIn("RetailEdge", source)
		self.assertNotIn("ProcessEdge", source)

	def test_portal_ui_is_edgesuite_ready_and_product_neutral(self):
		template = (APP_ROOT / "www" / "customer_portal.html").read_text()
		self.assertIn('data-edge-suite-ready="true"', template)
		self.assertIn("--edge-portal-surface:var(--edge-color-surface", template)
		self.assertIn("--edge-portal-accent:var(--edge-color-primary", template)
		self.assertIn("Customer Portal", template)
		self.assertIn("Outstanding", template)
		self.assertIn("Secure document access", template)
		self.assertNotIn("RetailEdge", template)
		self.assertNotIn("ProcessEdge", template)
		self.assertNotIn("Powered by", template)


if __name__ == "__main__":
	import unittest
	unittest.main()
