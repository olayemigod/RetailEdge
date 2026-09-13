import json

import frappe
from frappe.tests.utils import FrappeTestCase

from retailedge.tests.utils.fixture_cleanup import collect_fixture_names, delete_fixture_records
from retailedge.workspace_home import HOME_WORKSPACE_ITEMS


class TestEdgePayReporting(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self._cleanup_test_fixtures()
		frappe.db.commit()

	def tearDown(self):
		self._cleanup_test_fixtures()
		frappe.db.commit()
		super().tearDown()

	def _cleanup_test_fixtures(self):
		evidence_names = collect_fixture_names("RetailEdge EdgePay Payment Evidence", prefixes=("EPE-REP-",))
		handoff_log_names = collect_fixture_names(
			"RetailEdge EdgePay Handoff Log", filters=({"edgepay_event": "EV-REP-123"},)
		)
		delete_fixture_records("RetailEdge EdgePay Payment Evidence", evidence_names)
		delete_fixture_records("RetailEdge EdgePay Handoff Log", handoff_log_names)

	def create_evidence(
		self,
		name,
		review_status="Pending Review",
		posting_status="Not Prepared",
		submission_status="Not Submitted",
		reconciliation_status="Not Ready",
		amount=1500.0,
	):
		doc = frappe.get_doc(
			{
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
				"idempotency_key": name + "-idemp",
			}
		)
		doc.flags.name_set = True
		return doc.insert(ignore_permissions=True, ignore_links=True)

	def test_payment_evidence_summary_report_executes_correctly(self):
		# Create test evidence
		doc = self.create_evidence("EPE-REP-001", review_status="Pending Review")
		self.create_evidence("EPE-REP-002", review_status="Reviewed", posting_status="Draft Created")
		self.create_evidence(
			"EPE-REP-003",
			review_status="Reviewed",
			submission_status="Submitted",
			reconciliation_status="Ready",
		)
		self.create_evidence("EPE-REP-004", review_status="Reviewed", reconciliation_status="Blocked")

		from frappe.utils import getdate

		created_date = getdate(doc.creation).strftime("%Y-%m-%d")

		# Import execute method of report
		from retailedge.retailedge.report.retailedge_edgepay_payment_evidence_summary.retailedge_edgepay_payment_evidence_summary import (
			execute,
			get_report_summary,
		)

		columns, data, _message, _chart, _report_summary = execute(
			filters={"from_date": created_date, "to_date": created_date}
		)

		# Ensure columns exist
		self.assertTrue(len(columns) > 0)
		fixture_rows = [row for row in data if row.get("evidence", "").startswith("EPE-REP-")]
		self.assertEqual(len(fixture_rows), 4)

		# Verify report summary counts
		summary_dict = {item["label"]: item["value"] for item in get_report_summary(fixture_rows)}
		self.assertEqual(summary_dict.get("Total Evidence"), 4)
		self.assertEqual(summary_dict.get("Pending Review"), 1)
		self.assertEqual(summary_dict.get("Reviewed / Ready"), 3)
		self.assertEqual(summary_dict.get("Submitted PE"), 1)
		self.assertEqual(summary_dict.get("Blocked / Exception"), 1)

	def test_lifecycle_status_report_executes_correctly(self):
		doc = self.create_evidence(
			"EPE-REP-010",
			review_status="Reviewed",
			submission_status="Submitted",
			reconciliation_status="Matched",
		)

		from frappe.utils import getdate

		created_date = getdate(doc.creation).strftime("%Y-%m-%d")

		from retailedge.retailedge.report.retailedge_edgepay_lifecycle_status.retailedge_edgepay_lifecycle_status import (
			execute,
			get_report_summary,
		)

		columns, data, _message, _chart, _report_summary = execute(
			filters={"from_date": created_date, "to_date": created_date}
		)

		self.assertTrue(len(columns) > 0)
		fixture_rows = [row for row in data if row.get("evidence", "").startswith("EPE-REP-")]
		self.assertEqual(len(fixture_rows), 1)

		summary_dict = {item["label"]: item["value"] for item in get_report_summary(fixture_rows)}
		self.assertEqual(summary_dict.get("Total Requests"), 1)
		self.assertEqual(summary_dict.get("Evidence Reviewed"), 1)
		self.assertEqual(summary_dict.get("Payment Entries Submitted"), 1)
		self.assertEqual(summary_dict.get("Reconciliation Confirmed"), 1)

	def test_edgepay_reporting_is_not_exposed_in_business_workspace(self):
		"""Legacy EdgePay reporting stays available without surfacing EdgePay in RetailEdge navigation."""
		edgepay_labels = {
			"EdgePay Handoff Log",
			"EdgePay Payment Evidence",
			"EdgePay Reconciliation Readiness",
			"EdgePay Evidence Summary",
			"EdgePay Lifecycle Status",
			"EdgePay Rollout Monitor",
		}

		exposed_items = [item.label for item in HOME_WORKSPACE_ITEMS if item.label in edgepay_labels]
		self.assertEqual(exposed_items, [])

	def test_rollout_monitor_report_executes_correctly(self):
		from retailedge.retailedge.report.retailedge_edgepay_rollout_monitor.retailedge_edgepay_rollout_monitor import (
			execute,
		)

		columns, data, _message, _chart, report_summary = execute(filters={"stale_days": 3})

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

		from retailedge.retailedge.report.retailedge_edgepay_lifecycle_status.retailedge_edgepay_lifecycle_status import (
			execute as execute_lifecycle,
		)
		from retailedge.retailedge.report.retailedge_edgepay_payment_evidence_summary.retailedge_edgepay_payment_evidence_summary import (
			execute as execute_summary,
		)
		from retailedge.retailedge.report.retailedge_edgepay_rollout_monitor.retailedge_edgepay_rollout_monitor import (
			execute as execute_monitor,
		)

		execute_summary()
		execute_lifecycle()
		execute_monitor()

		self.assertEqual(frappe.db.count("RetailEdge EdgePay Payment Evidence"), ev_count_before)
		self.assertEqual(frappe.db.count("RetailEdge EdgePay Handoff Log"), hl_count_before)
