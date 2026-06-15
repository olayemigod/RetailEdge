# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from retailedge.workspace_home import HOME_WORKSPACE_ITEMS, HOME_SECTIONS
import json

class TestEdgePayReporting(FrappeTestCase):
	def setUp(self):
		super(TestEdgePayReporting, self).setUp()
		# Clean setup
		frappe.db.delete("RetailEdge EdgePay Payment Evidence")
		frappe.db.delete("RetailEdge EdgePay Handoff Log")
		frappe.db.commit()

	def tearDown(self):
		frappe.db.delete("RetailEdge EdgePay Payment Evidence")
		frappe.db.delete("RetailEdge EdgePay Handoff Log")
		frappe.db.commit()
		super(TestEdgePayReporting, self).tearDown()

	def create_evidence(self, name, review_status="Pending Review", posting_status="Not Prepared", submission_status="Not Submitted", reconciliation_status="Not Ready", amount=1500.0):
		doc = frappe.get_doc({
			"doctype": "RetailEdge EdgePay Payment Evidence",
			"name": name,
			"edgepay_handoff_event": "EV-REP-123",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-REP-0001",
			"amount": amount,
			"currency": "NGN",
			"review_status": review_status,
			"posting_status": posting_status,
			"submission_status": submission_status,
			"reconciliation_status": reconciliation_status,
			"idempotency_key": name + "-idemp"
		})
		doc.flags.name_set = True
		return doc.insert(ignore_permissions=True, ignore_links=True)

	def test_payment_evidence_summary_report_executes_correctly(self):
		# Create test evidence
		self.create_evidence("EPE-REP-001", review_status="Pending Review")
		self.create_evidence("EPE-REP-002", review_status="Reviewed", posting_status="Draft Created")
		self.create_evidence("EPE-REP-003", review_status="Reviewed", submission_status="Submitted", reconciliation_status="Ready")
		self.create_evidence("EPE-REP-004", review_status="Reviewed", reconciliation_status="Blocked")

		# Import execute method of report
		from retailedge.retailedge.report.retailedge_edgepay_payment_evidence_summary.retailedge_edgepay_payment_evidence_summary import execute
		
		columns, data, message, chart, report_summary = execute(filters={
			"from_date": "2026-06-01",
			"to_date": "2026-06-30"
		})

		# Ensure columns exist
		self.assertTrue(len(columns) > 0)
		# Ensure records are found
		self.assertEqual(len(data), 4)

		# Verify report summary counts
		summary_dict = {item["label"]: item["value"] for item in report_summary}
		self.assertEqual(summary_dict.get("Total Evidence"), 4)
		self.assertEqual(summary_dict.get("Pending Review"), 1)
		self.assertEqual(summary_dict.get("Reviewed / Ready"), 3)
		self.assertEqual(summary_dict.get("Submitted PE"), 1)
		self.assertEqual(summary_dict.get("Blocked / Exception"), 1)

	def test_lifecycle_status_report_executes_correctly(self):
		self.create_evidence("EPE-REP-010", review_status="Reviewed", submission_status="Submitted", reconciliation_status="Matched")

		from retailedge.retailedge.report.retailedge_edgepay_lifecycle_status.retailedge_edgepay_lifecycle_status import execute
		
		columns, data, message, chart, report_summary = execute(filters={
			"from_date": "2026-06-01",
			"to_date": "2026-06-30"
		})

		self.assertTrue(len(columns) > 0)
		self.assertEqual(len(data), 1)

		summary_dict = {item["label"]: item["value"] for item in report_summary}
		self.assertEqual(summary_dict.get("Total Requests"), 1)
		self.assertEqual(summary_dict.get("Evidence Reviewed"), 1)
		self.assertEqual(summary_dict.get("Payment Entries Submitted"), 1)
		self.assertEqual(summary_dict.get("Reconciliation Confirmed"), 1)

	def test_workspace_definitions_are_valid(self):
		# Verify that new items in HOME_WORKSPACE_ITEMS point to valid targets
		new_labels = ["EdgePay Handoff Log", "EdgePay Payment Evidence", "EdgePay Reconciliation Readiness", "EdgePay Evidence Summary", "EdgePay Lifecycle Status", "EdgePay Rollout Monitor"]
		
		found_items = [item for item in HOME_WORKSPACE_ITEMS if item.label in new_labels]
		self.assertEqual(len(found_items), 6)

		for item in found_items:
			self.assertEqual(item.section, "EdgePay Review")
			if item.link_type == "DocType":
				self.assertTrue(frappe.db.exists("DocType", item.link_to), f"DocType {item.link_to} does not exist.")
			elif item.link_type == "Report":
				# Standard reports might not be imported yet in the database, but we verify target name
				self.assertTrue(item.link_to in ["RetailEdge EdgePay Reconciliation Readiness", "RetailEdge EdgePay Payment Evidence Summary", "RetailEdge EdgePay Lifecycle Status", "RetailEdge EdgePay Rollout Monitor"])

	def test_rollout_monitor_report_executes_correctly(self):
		from retailedge.retailedge.report.retailedge_edgepay_rollout_monitor.retailedge_edgepay_rollout_monitor import execute
		
		columns, data, message, chart, report_summary = execute(filters={"stale_days": 3})

		# Ensure columns exist
		self.assertTrue(len(columns) > 0)
		# Ensure 9 metric rows are returned
		self.assertEqual(len(data), 9)
		
		# Verify report summary structure
		self.assertTrue(len(report_summary) > 0)

	def test_reports_are_read_only_and_do_not_mutate(self):
		# Run execute on both reports and verify no new records are inserted in DB
		ev_count_before = frappe.db.count("RetailEdge EdgePay Payment Evidence")
		hl_count_before = frappe.db.count("RetailEdge EdgePay Handoff Log")

		from retailedge.retailedge.report.retailedge_edgepay_payment_evidence_summary.retailedge_edgepay_payment_evidence_summary import execute as execute_summary
		from retailedge.retailedge.report.retailedge_edgepay_lifecycle_status.retailedge_edgepay_lifecycle_status import execute as execute_lifecycle
		from retailedge.retailedge.report.retailedge_edgepay_rollout_monitor.retailedge_edgepay_rollout_monitor import execute as execute_monitor

		execute_summary()
		execute_lifecycle()
		execute_monitor()

		self.assertEqual(frappe.db.count("RetailEdge EdgePay Payment Evidence"), ev_count_before)
		self.assertEqual(frappe.db.count("RetailEdge EdgePay Handoff Log"), hl_count_before)
