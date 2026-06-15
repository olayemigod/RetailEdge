# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch
import os

class TestEdgePayReadiness(FrappeTestCase):
	def setUp(self):
		super(TestEdgePayReadiness, self).setUp()
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		super(TestEdgePayReadiness, self).tearDown()

	def test_readiness_checklist_report_executes_read_only(self):
		from retailedge.retailedge.report.retailedge_edgepay_readiness_checklist.retailedge_edgepay_readiness_checklist import execute
		
		# Get count before
		hl_count = frappe.db.count("RetailEdge EdgePay Handoff Log")
		ev_count = frappe.db.count("RetailEdge EdgePay Payment Evidence")
		
		columns, data, message, chart, report_summary = execute()
		
		self.assertTrue(len(columns) > 0)
		self.assertTrue(len(data) > 0)
		
		# Assert no DB mutations occurred
		self.assertEqual(frappe.db.count("RetailEdge EdgePay Handoff Log"), hl_count)
		self.assertEqual(frappe.db.count("RetailEdge EdgePay Payment Evidence"), ev_count)

	def test_readiness_summary_contains_no_secrets_or_raw_keys(self):
		from retailedge.services.edgepay_readiness_checklist import get_edgepay_retail_readiness_summary
		
		# Create mock provider with secret key values
		frappe.db.delete("EdgePay Provider", "Test Monnify Provider")
		prov = frappe.get_doc({
			"doctype": "EdgePay Provider",
			"provider_name": "Test Monnify Provider",
			"provider_code": "monnify",
			"provider_type": "Monnify",
			"enabled": 1,
			"api_key": "super-secret-api-key-123",
			"secret_key": "super-secret-key-456",
			"contract_code": "contract-123"
		})
		prov.insert(ignore_permissions=True)
		
		# Set as default in EdgePay Settings
		settings = frappe.get_single("EdgePay Settings")
		settings.default_provider = "Test Monnify Provider"
		settings.save()
		
		summary = get_edgepay_retail_readiness_summary()
		
		provider_summary = summary.get("provider", {})
		self.assertEqual(provider_summary.get("name"), "Test Monnify Provider")
		self.assertTrue(provider_summary.get("api_key_present"))
		self.assertTrue(provider_summary.get("secret_key_present"))
		
		# Crucial Safety Check: Ensure actual key values are NOT leaked in output summary dict
		summary_str = str(summary)
		self.assertNotIn("super-secret-api-key-123", summary_str)
		self.assertNotIn("super-secret-key-456", summary_str)
		
		# Cleanup
		frappe.db.delete("EdgePay Provider", "Test Monnify Provider")
		settings.default_provider = None
		settings.save()
		frappe.db.commit()

	def test_guest_access_is_blocked_on_sensitive_endpoints(self):
		frappe.set_user("Guest")
		
		sensitive_apis = [
			"retailedge.api.get_edgepay_bank_match_confirmation_preflight",
			"retailedge.api.confirm_edgepay_bank_match_review",
			"retailedge.api.get_edgepay_retail_readiness_summary"
		]
		
		for api in sensitive_apis:
			# Verify calling as Guest triggers PermissionError or raises traceback
			with self.assertRaises(frappe.PermissionError):
				frappe.call(api, evidence_name="EPE-MOCK-123")

	def test_live_calls_disabled_by_default(self):
		# Default config check: verify allow_external_http_calls is 0 (safer)
		settings = frappe.get_single("EdgePay Settings")
		self.assertFalse(settings.allow_external_http_calls)

	def test_no_auto_operations_occur_from_reporting_and_readiness(self):
		# Verify that calling execute on reports does not mutate docstatus or submit documents
		from retailedge.retailedge.report.retailedge_edgepay_reconciliation_readiness.retailedge_edgepay_reconciliation_readiness import execute as execute_readiness
		from retailedge.retailedge.report.retailedge_edgepay_readiness_checklist.retailedge_edgepay_readiness_checklist import execute as execute_checklist
		
		pe_count = frappe.db.count("Payment Entry", {"docstatus": 1})
		review_count = frappe.db.count("RetailEdge Bank Transaction Match", {"decision_status": "Confirmed"})
		
		execute_readiness()
		execute_checklist()
		
		self.assertEqual(frappe.db.count("Payment Entry", {"docstatus": 1}), pe_count)
		self.assertEqual(frappe.db.count("RetailEdge Bank Transaction Match", {"decision_status": "Confirmed"}), review_count)

	def test_pilot_checklist_document_exists_and_covers_safety(self):
		# Verify document path exists
		doc_path = frappe.get_app_path("retailedge", "..", "docs", "edgepay_retailedge_sandbox_pilot_checklist.md")
		self.assertTrue(os.path.exists(doc_path))
		
		# Read and ensure credential safety keywords exist
		with open(doc_path, "r", encoding="utf-8") as f:
			content = f.read()
			self.assertIn("Do NOT commit credentials", content)
			self.assertIn("environment variables", content)
			self.assertIn("Secret Key", content)
			self.assertIn("sandbox", content.lower())

	def test_standalone_imports_guard_checked(self):
		# Check that edgepayv1 does not import product modules like retailedge or erpnext directly
		import sys
		import re
		
		edgepay_path = frappe.get_app_path("edgepayv1")
		for root, dirs, files in os.walk(edgepay_path):
			for file in files:
				if file.endswith(".py"):
					with open(os.path.join(root, file), "r", encoding="utf-8") as f:
						code = f.read()
						# Scan for forbidden imports of retailedge, erpnext
						forbidden = re.findall(r"import\s+(retailedge|erpnext|pos_next|vetedge|coreedge)", code)
						self.assertFalse(forbidden, f"Standalone violation: forbidden import of {forbidden} found in file {file}.")

	def test_readiness_checklist_includes_rollout_monitor_report(self):
		from retailedge.services.edgepay_readiness_checklist import get_edgepay_retail_readiness_summary
		summary = get_edgepay_retail_readiness_summary()
		self.assertIn("rollout_monitor_report_exists", summary.get("reports", {}))
