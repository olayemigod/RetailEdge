from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.services.edgepay_readiness_checklist import get_edgepay_retail_readiness_summary


class TestEdgePayReadiness(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_readiness_checklist_report_executes_read_only(self):
		from retailedge.retailedge.report.retailedge_edgepay_readiness_checklist.retailedge_edgepay_readiness_checklist import (
			execute,
		)

		handoff_count = frappe.db.count("RetailEdge EdgePay Handoff Log")
		evidence_count = frappe.db.count("RetailEdge EdgePay Payment Evidence")

		columns, data, message, chart, report_summary = execute()

		self.assertTrue(columns)
		self.assertTrue(data)
		self.assertIsNone(message)
		self.assertIsNone(chart)
		self.assertTrue(report_summary)
		self.assertEqual(frappe.db.count("RetailEdge EdgePay Handoff Log"), handoff_count)
		self.assertEqual(frappe.db.count("RetailEdge EdgePay Payment Evidence"), evidence_count)

	def test_readiness_summary_uses_remote_service_config_only(self):
		with patch.dict(
			frappe.conf,
			{
				"edgepay_service_url": "https://edgepay.example.com",
				"edgepay_service_api_key": "service-key",
				"edgepay_service_api_secret": "service-secret",
				"edgepay_service_bearer_token": "",
			},
			clear=False,
		):
			summary = get_edgepay_retail_readiness_summary()

		service = summary["service"]
		self.assertTrue(service["configured"])
		self.assertTrue(service["url_configured"])
		self.assertTrue(service["authentication_configured"])
		self.assertEqual(service["authentication_mode"], "Frappe API Token")
		self.assertFalse(service["local_edgepay_app_required"])
		self.assertTrue(service["provider_configuration_owned_by_edgepay"])
		self.assertNotIn("service-key", str(summary))
		self.assertNotIn("service-secret", str(summary))
		self.assertNotIn("provider", summary)

	def test_unconfigured_service_is_reported_without_breaking_retailedge(self):
		with patch.dict(
			frappe.conf,
			{
				"edgepay_service_url": "",
				"edgepay_service_api_key": "",
				"edgepay_service_api_secret": "",
				"edgepay_service_bearer_token": "",
			},
			clear=False,
		):
			summary = get_edgepay_retail_readiness_summary()

		self.assertFalse(summary["service"]["configured"])
		self.assertFalse(summary["service"]["local_edgepay_app_required"])
		self.assertTrue(summary["doctypes"]["evidence_doctype_exists"])

	def test_guest_access_is_blocked_on_sensitive_endpoints(self):
		frappe.set_user("Guest")
		for api in (
			"retailedge.api.get_edgepay_bank_match_confirmation_preflight",
			"retailedge.api.confirm_edgepay_bank_match_review",
			"retailedge.api.get_edgepay_retail_readiness_summary",
		):
			with self.assertRaises(frappe.PermissionError):
				frappe.call(api, evidence_name="EPE-MOCK-123")

	def test_reporting_and_readiness_do_not_post_accounting(self):
		from retailedge.retailedge.report.retailedge_edgepay_readiness_checklist.retailedge_edgepay_readiness_checklist import (
			execute as execute_checklist,
		)
		from retailedge.retailedge.report.retailedge_edgepay_reconciliation_readiness.retailedge_edgepay_reconciliation_readiness import (
			execute as execute_readiness,
		)

		payment_entry_count = frappe.db.count("Payment Entry", {"docstatus": 1})
		review_count = frappe.db.count("RetailEdge Bank Transaction Match", {"decision_status": "Confirmed"})

		execute_readiness()
		execute_checklist()

		self.assertEqual(frappe.db.count("Payment Entry", {"docstatus": 1}), payment_entry_count)
		self.assertEqual(
			frappe.db.count("RetailEdge Bank Transaction Match", {"decision_status": "Confirmed"}),
			review_count,
		)

	def test_retailedge_has_no_local_edgepay_package_dependency(self):
		app_root = Path(__file__).resolve().parents[1]
		violations = []
		for path in app_root.rglob("*.py"):
			relative_path = path.relative_to(app_root)
			if "tests" in relative_path.parts:
				continue
			content = path.read_text(encoding="utf-8")
			if "from edgepayv1" in content or "import edgepayv1" in content:
				violations.append(str(relative_path))
		self.assertEqual(violations, [])

	def test_readiness_checklist_includes_rollout_monitor_report(self):
		summary = get_edgepay_retail_readiness_summary()
		self.assertIn("rollout_monitor_report_exists", summary.get("reports", {}))
