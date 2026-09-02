from __future__ import annotations

from pathlib import Path
from unittest import TestCase

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_UPDATES = APP_ROOT / "customer_project_updates.py"
PORTAL = APP_ROOT / "customer_portal.py"
HOOKS = APP_ROOT / "hooks.py"
PAGE = APP_ROOT / "www" / "customer_project_updates.py"
PAGE_HTML = APP_ROOT / "www" / "customer_project_updates.html"
PORTAL_HTML = APP_ROOT / "www" / "customer_portal.html"


class TestCustomerProjectUpdates(TestCase):
	def setUp(self):
		self.project_updates = PROJECT_UPDATES.read_text(encoding="utf-8")
		self.portal = PORTAL.read_text(encoding="utf-8")
		self.hooks = HOOKS.read_text(encoding="utf-8")
		self.page = PAGE.read_text(encoding="utf-8")
		self.page_html = PAGE_HTML.read_text(encoding="utf-8")
		self.portal_html = PORTAL_HTML.read_text(encoding="utf-8")

	def test_publication_metadata_extends_native_project_update_with_neutral_labels(self):
		self.assertIn('PROJECT_UPDATE_DOCTYPE = "Project Update"', self.project_updates)
		self.assertIn('PROJECT_DOCTYPE = "Project"', self.project_updates)
		self.assertIn('"label": "Customer Portal Publication"', self.project_updates)
		self.assertIn('"label": "Publish to Customer Portal"', self.project_updates)
		self.assertIn('"label": "Customer Update"', self.project_updates)
		self.assertIn('"label": "Published On"', self.project_updates)
		self.assertIn('"label": "Published By"', self.project_updates)
		self.assertIn("create_custom_fields(custom_fields, ignore_validate=True, update=True)", self.project_updates)
		self.assertNotIn('"label": "RetailEdge', self.project_updates)
		self.assertNotIn('"label": "ProcessEdge', self.project_updates)

	def test_publication_requires_readable_customer_linked_project_and_clean_summary(self):
		self.assertIn('frappe.has_permission(PROJECT_DOCTYPE, "read", doc=project_name)', self.project_updates)
		self.assertIn('["customer", "company"]', self.project_updates)
		self.assertIn("not project.customer", self.project_updates)
		self.assertIn("Only Projects linked to a Customer can be published", self.project_updates)
		self.assertIn("_clean_customer_summary(doc.get(SUMMARY_FIELD))", self.project_updates)
		self.assertIn("strip_html(str(value or \"\"))", self.project_updates)
		self.assertIn("MAX_CUSTOMER_UPDATE_LENGTH = 2000", self.project_updates)
		self.assertIn("doc.set(PUBLISHED_ON_FIELD, now_datetime())", self.project_updates)
		self.assertIn("doc.set(PUBLISHED_BY_FIELD, frappe.session.user)", self.project_updates)

	def test_portal_ownership_is_server_derived_from_logged_in_customer(self):
		self.assertIn("from retailedge.customer_portal import _assert_customer_portal_user", self.project_updates)
		self.assertIn("customers = _assert_customer_portal_user()", self.project_updates)
		self.assertIn('filters: dict[str, Any] = {"customer": ["in", customers]}', self.project_updates)
		self.assertIn("This Project is not linked to your customer account.", self.project_updates)
		self.assertIn('frappe.form_dict.get("project")', self.page)
		self.assertNotIn('frappe.form_dict.get("customer")', self.page)
		self.assertNotIn('frappe.form_dict.get("company")', self.page)

	def test_only_submitted_explicitly_published_native_updates_are_read(self):
		published_reader = self.project_updates.split("def _published_update_rows", 1)[1].split(
			"def get_customer_project_update_states", 1
		)[0]
		self.assertIn('"docstatus": 1', published_reader)
		self.assertIn("PUBLISH_FIELD: 1", published_reader)
		self.assertIn('"project": ["in", project_names]', published_reader)
		self.assertIn("limit_page_length=max(1, min(", published_reader)
		self.assertNotIn('"users"', published_reader)
		self.assertNotIn('"notes"', published_reader)
		self.assertNotIn("total_costing_amount", published_reader)
		self.assertNotIn("total_purchase_cost", published_reader)
		self.assertNotIn("gross_margin", published_reader)

	def test_customer_read_path_is_bounded_and_does_not_mutate_native_documents(self):
		read_path = self.project_updates.split("def _owned_projects", 1)[1]
		self.assertIn("MAX_PROJECT_UPDATE_ROWS = 200", self.project_updates)
		self.assertIn("limit_page_length=MAX_PROJECT_UPDATE_ROWS", read_path)
		for forbidden in (
			"frappe.new_doc(",
			".insert(",
			".submit()",
			".save(",
			".db_set(",
			"frappe.db.set_value",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, read_path)
		self.assertIn('"read_only": True', self.project_updates)
		self.assertIn('"internal_project_update_users_exposed": False', self.project_updates)
		self.assertIn('"project_costing_exposed": False', self.project_updates)

	def test_company_identity_comes_from_owned_projects_not_global_site_default(self):
		self.assertIn("companies = sorted({str(row.company", self.project_updates)
		self.assertIn('"company_name": companies[0] if len(companies) == 1 else ""', self.project_updates)
		self.assertIn('context.company_name = str(updates.get("company_name") or "").strip()', self.page)
		self.assertNotIn("get_global_default", self.page)
		self.assertIn('{{ company_name or "Customer Portal" }}', self.page_html)

	def test_hooks_install_and_validate_publication_without_overriding_erpnext(self):
		self.assertIn(
			'"retailedge.customer_project_updates.ensure_customer_project_update_custom_fields"',
			self.hooks,
		)
		self.assertIn('"Project Update": {', self.hooks)
		self.assertIn(
			'"validate": "retailedge.customer_project_updates.validate_customer_project_update_publication"',
			self.hooks,
		)
		self.assertNotIn('"erpnext.projects.doctype.project.project.', self.hooks)
		self.assertNotIn('"erpnext.projects.doctype.project_update.project_update.', self.hooks)

	def test_existing_customer_portal_enriches_native_projects_with_published_state(self):
		self.assertIn("get_customer_project_update_states", self.portal)
		self.assertIn('if doctype == "Project"', self.portal)
		self.assertIn('"project_update_count"', self.portal)
		self.assertIn('"latest_project_update"', self.portal)
		self.assertIn('"project_updates_url"', self.portal)
		self.assertIn('"project_updates": "/customer_project_updates"', self.portal)
		self.assertIn("Project Updates", self.portal_html)
		self.assertIn("latest_project_update", self.portal_html)

	def test_customer_facing_project_update_pages_are_product_neutral_and_explicit(self):
		for source in (self.page, self.page_html):
			self.assertNotIn("RetailEdge", source)
			self.assertNotIn("ProcessEdge", source)
			self.assertNotIn("Powered by", source)
		self.assertIn("explicitly published", self.page_html)
		self.assertIn("submitted Project Updates explicitly marked for customer publication", self.page_html)
		self.assertIn("Internal project replies, tasks, notes, costing and accounting information are not shown", self.page_html)


if __name__ == "__main__":
	import unittest

	unittest.main()
