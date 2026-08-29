from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from retailedge.customer_portal_collaboration import quotation_response_allowed

APP_ROOT = Path(__file__).resolve().parents[1]
SERVICE = APP_ROOT / "customer_portal_collaboration.py"
PORTAL = APP_ROOT / "customer_portal.py"
HTML = APP_ROOT / "www" / "customer_portal.html"
DOCTYPE = (
	APP_ROOT
	/ "retailedge"
	/ "doctype"
	/ "customer_portal_activity"
	/ "customer_portal_activity.json"
)
DOCTYPE_PY = DOCTYPE.with_name("customer_portal_activity.py")


class TestCustomerPortalCollaboration(TestCase):
	def setUp(self):
		self.service = SERVICE.read_text(encoding="utf-8")
		self.portal = PORTAL.read_text(encoding="utf-8")
		self.html = HTML.read_text(encoding="utf-8")
		self.doctype = json.loads(DOCTYPE.read_text(encoding="utf-8"))
		self.doctype_py = DOCTYPE_PY.read_text(encoding="utf-8")

	def test_customer_activity_doctype_is_neutral_append_only_and_not_customer_writable(self):
		self.assertEqual(self.doctype["name"], "Customer Portal Activity")
		self.assertNotIn("RetailEdge", self.doctype["name"])
		roles = {row["role"] for row in self.doctype["permissions"]}
		self.assertNotIn("Customer", roles)
		for permission in self.doctype["permissions"]:
			self.assertFalse(permission.get("create"))
			self.assertFalse(permission.get("write"))
			self.assertFalse(permission.get("delete"))
		self.assertIn("Customer portal activity records are immutable.", self.doctype_py)
		self.assertIn("customer_portal_activity_api_write", self.doctype_py)

	def test_service_rederives_customer_and_checks_native_website_ownership(self):
		self.assertIn("_assert_customer_portal_user", self.service)
		self.assertIn('quotation.quotation_to != "Customer"', self.service)
		self.assertIn("quotation.party_name not in customers", self.service)
		self.assertIn('has_website_permission(quotation, "read", frappe.session.user)', self.service)
		self.assertIn("quotation.docstatus != 1", self.service)
		self.assertIn('"customer": quotation.party_name', self.service)
		self.assertIn('"company": quotation.company', self.service)
		self.assertIn('"portal_user": frappe.session.user', self.service)

	def test_response_eligibility_follows_native_quotation_state_and_expiry(self):
		self.assertIn('QUOTATION_RESPONSE_STATUSES = {"Open", "Replied"}', self.service)
		self.assertTrue(
			quotation_response_allowed(SimpleNamespace(docstatus=1, status="Open", valid_till=None))
		)
		self.assertTrue(
			quotation_response_allowed(SimpleNamespace(docstatus=1, status="Replied", valid_till=None))
		)
		self.assertFalse(
			quotation_response_allowed(SimpleNamespace(docstatus=1, status="Ordered", valid_till=None))
		)
		self.assertFalse(
			quotation_response_allowed(SimpleNamespace(docstatus=0, status="Draft", valid_till=None))
		)

	def test_service_serializes_but_never_mutates_submitted_quotation(self):
		self.assertIn("select name from `tabQuotation` where name=%s for update", self.service)
		self.assertIn('frappe.new_doc("Customer Portal Activity")', self.service)
		self.assertIn("activity.insert(ignore_permissions=True)", self.service)
		self.assertIn('"quotation_mutated": False', self.service)
		for forbidden in (
			'frappe.new_doc("Comment")',
			'frappe.new_doc("Communication")',
			"quotation.save(",
			"quotation.db_set(",
			'frappe.db.set_value("Quotation"',
			"update `tabQuotation`",
			"frappe.db.commit",
		):
			self.assertNotIn(forbidden, self.service)

	def test_duplicate_identical_response_reuses_latest_activity(self):
		self.assertIn("_latest_response(quotation.name, quotation.party_name)", self.service)
		self.assertIn("existing.activity_type == activity_type", self.service)
		self.assertIn('str(existing.message or "") == cleaned_message', self.service)
		self.assertIn("_activity_result(existing, reused=True)", self.service)

	def test_portal_exposes_server_derived_response_state_and_only_minimal_browser_arguments(self):
		self.assertIn("get_quotation_activity_states", self.portal)
		self.assertIn('"quotation_response": quotation_state.get("response", "")', self.portal)
		self.assertIn('"quotation_submitted_document_mutated": False', self.portal)
		self.assertIn('data-activity-type="Accepted"', self.html)
		self.assertIn('data-activity-type="Declined"', self.html)
		self.assertIn('data-activity-type="Message"', self.html)
		self.assertIn(
			'method: "retailedge.customer_portal_collaboration.record_quotation_activity"',
			self.html,
		)
		call = self.html.split(
			'method: "retailedge.customer_portal_collaboration.record_quotation_activity"', 1
		)[1].split("}).then", 1)[0]
		self.assertIn("quotation_name: quotationName", call)
		self.assertIn("activity_type: activityType", call)
		self.assertIn("message: message.value", call)
		self.assertNotIn("customer:", call)
		self.assertNotIn("company:", call)
		self.assertIn('type: "POST"', call)

	def test_customer_facing_copy_explains_separate_non_mutating_response(self):
		self.assertIn("do not alter the submitted quotation", self.html)
		self.assertIn("without changing the submitted quotation", self.html)
		self.assertNotIn("Powered by RetailEdge", self.html)
		self.assertNotIn("Powered by ProcessEdge", self.html)


if __name__ == "__main__":
	import unittest

	unittest.main()
