from __future__ import annotations

import unittest
from pathlib import Path

import frappe

from retailedge.retailedge.report.retailedge_bank_match_reconciliation_readiness import (
	retailedge_bank_match_reconciliation_readiness as readiness_report,
)
from retailedge.retailedge.report.retailedge_reconciliation_handoff import (
	retailedge_reconciliation_handoff as handoff_report,
)
from retailedge.retailedge.report.retailedge_unmatched_bank_payment_events import (
	retailedge_unmatched_bank_payment_events as payment_event_report,
)


class TestRetailEdgeReconciliationOversightEdgeUI(unittest.TestCase):
	def app_path(self, *parts: str) -> Path:
		return Path(frappe.get_app_path("retailedge", *parts))

	def test_oversight_reports_attach_to_shared_adapter_and_preserve_filters(self):
		paths = {
			"RetailEdge Bank Match Reconciliation Readiness": self.app_path(
				"retailedge",
				"report",
				"retailedge_bank_match_reconciliation_readiness",
				"retailedge_bank_match_reconciliation_readiness.js",
			),
			"RetailEdge Reconciliation Handoff": self.app_path(
				"retailedge",
				"report",
				"retailedge_reconciliation_handoff",
				"retailedge_reconciliation_handoff.js",
			),
			"RetailEdge Unmatched Bank Payment Events": self.app_path(
				"retailedge",
				"report",
				"retailedge_unmatched_bank_payment_events",
				"retailedge_unmatched_bank_payment_events.js",
			),
		}
		for report_name, path in paths.items():
			content = path.read_text()
			self.assertIn(f'attachRetailEdgeReportEdgeUI(report, "{report_name}"', content)
			self.assertIn(f'retailedgeReportEdgeUI?.refresh(report, "{report_name}")', content)
			self.assertIn("filters:", content)
			self.assertIn('frappe.require("/assets/retailedge/js/retailedge_report_edgeui.js"', content)

	def test_readiness_metadata_prioritises_exceptions_account_gaps_and_ageing(self):
		rows = [
			{
				"reconciliation_readiness_status": "Exception",
				"account_resolution_status": "Unresolved",
				"resolved_bank_account": "",
				"resolved_payment_account": "",
				"days_since_confirmation": 5,
			},
			{
				"reconciliation_readiness_status": "Needs Review",
				"account_resolution_status": "Resolved",
				"resolved_bank_account": "Bank - PE",
				"resolved_payment_account": "Collection - PE",
				"days_since_confirmation": 1,
			},
		]
		metadata = readiness_report.get_edgesuite_metadata({}, rows)
		self.assertEqual(metadata["row_count"], 2)
		self.assertEqual(metadata["status"]["tone"], "danger")
		titles = {item["title"] for item in metadata["recommendations"]}
		self.assertIn("Resolve reconciliation exceptions", titles)
		self.assertIn("Complete review before handoff", titles)
		self.assertIn("Resolve account context", titles)
		self.assertIn("Escalate aged confirmed matches", titles)

	def test_handoff_metadata_surfaces_blockers_candidate_gaps_and_priority(self):
		rows = [
			{
				"handoff_status": "Exception / Manual Investigation Required",
				"handoff_priority": "High",
				"blocking_reason": "Account evidence incomplete",
				"candidate_doctype": "",
				"candidate_name": "",
			},
			{
				"handoff_status": "Ready for ERPNext Reconciliation",
				"handoff_priority": "Normal",
				"candidate_doctype": "Payment Entry",
				"candidate_name": "ACC-PAY-1",
			},
		]
		metadata = handoff_report.get_edgesuite_metadata(
			{},
			rows,
			{"ready": 1, "needs_review": 1, "exception": 1},
		)
		self.assertEqual(metadata["row_count"], 2)
		self.assertEqual(metadata["status"]["tone"], "danger")
		titles = {item["title"] for item in metadata["recommendations"]}
		self.assertIn("Investigate manual exceptions", titles)
		self.assertIn("Complete pre-reconciliation review", titles)
		self.assertIn("Resolve handoff blockers", titles)
		self.assertIn("Complete candidate evidence", titles)
		self.assertIn("Escalate high-priority handoffs", titles)

	def test_unmatched_payment_event_metadata_surfaces_context_reference_and_ageing(self):
		rows = [
			{
				"payment_event_type": "Payment Entry",
				"payment_account": "",
				"resolved_canonical_account": "",
				"candidate_bank_transaction": "",
				"reason_exception": "Canonical account missing",
				"reference_no": "",
				"payment_row_reference": "",
				"days_outstanding": 9,
			},
			{
				"payment_event_type": "Invoice Payment Row",
				"payment_account": "Collection - PE",
				"resolved_canonical_account": "Collection - PE",
				"candidate_bank_transaction": "ACC-BTN-1",
				"days_outstanding": 1,
			},
		]
		metadata = payment_event_report.get_edgesuite_metadata({}, rows)
		self.assertEqual(metadata["row_count"], 2)
		self.assertEqual(metadata["status"]["tone"], "danger")
		titles = {item["title"] for item in metadata["recommendations"]}
		self.assertIn("Resolve payment-account context", titles)
		self.assertIn("Investigate events without bank candidates", titles)
		self.assertIn("Escalate aged unmatched payment events", titles)
		self.assertIn("Resolve payment-event exceptions", titles)
		self.assertIn("Complete payment references", titles)

	def test_reconciliation_oversight_phase_contains_no_write_or_reconciliation_actions(self):
		paths = [
			self.app_path(
				"retailedge",
				"report",
				"retailedge_bank_match_reconciliation_readiness",
				"retailedge_bank_match_reconciliation_readiness.py",
			),
			self.app_path(
				"retailedge",
				"report",
				"retailedge_bank_match_reconciliation_readiness",
				"retailedge_bank_match_reconciliation_readiness.js",
			),
			self.app_path(
				"retailedge",
				"report",
				"retailedge_reconciliation_handoff",
				"retailedge_reconciliation_handoff.py",
			),
			self.app_path(
				"retailedge",
				"report",
				"retailedge_reconciliation_handoff",
				"retailedge_reconciliation_handoff.js",
			),
			self.app_path(
				"retailedge",
				"report",
				"retailedge_unmatched_bank_payment_events",
				"retailedge_unmatched_bank_payment_events.py",
			),
			self.app_path(
				"retailedge",
				"report",
				"retailedge_unmatched_bank_payment_events",
				"retailedge_unmatched_bank_payment_events.js",
			),
		]
		combined = "\n".join(path.read_text().lower() for path in paths)
		for forbidden in (
			"doc.save(",
			"doc.submit(",
			"frappe.client.save",
			"frappe.db.set_value",
			"frappe.delete_doc",
			"make_payment_entry",
			"make_journal_entry",
			"reconcile_vouchers",
			"create_review",
			"confirm_match",
		):
			self.assertNotIn(forbidden, combined)
