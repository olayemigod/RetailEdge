from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from retailedge.bank_candidate_engine import (
	OUTCOME_ACCOUNTING_EVENT_MISSING,
	OUTCOME_ACCOUNTING_EVENT_NOT_ELIGIBLE,
	OUTCOME_BANKING_SETUP_BLOCKED,
	OUTCOME_CANDIDATE_REVIEW_BLOCKED,
	OUTCOME_CANDIDATES_FOUND,
	_candidate_search_outcome,
)


APP_ROOT = Path(__file__).resolve().parents[1]
OUTCOME_ASSET = APP_ROOT / "public/js/bank_candidate_outcome_notifications.js"
PAGE_LOADER = APP_ROOT / "retailedge/page/bank_matching_reconciliation/bank_matching_reconciliation.js"


class BankCandidateOutcomeNotificationTests(unittest.TestCase):
	def test_blocked_banking_setup_takes_precedence(self):
		result = _candidate_search_outcome(
			{"direction": "Inflow", "amount": 620000},
			[],
			{
				"readiness": "Blocked",
				"issues": [
					{
						"code": "missing_bank_account",
						"message": "Bank Account is required.",
					}
				],
			},
		)
		self.assertEqual(result["code"], OUTCOME_BANKING_SETUP_BLOCKED)
		self.assertEqual(result["action"], "banking_readiness")
		self.assertIn("Bank Account is required", result["message"])

	@patch("retailedge.bank_candidate_engine._has_nearby_submitted_accounting_event", return_value=False)
	def test_valid_setup_without_accounting_event_is_distinct(self, nearby_event):
		result = _candidate_search_outcome(
			{"direction": "Inflow", "amount": 620000},
			[],
			{"readiness": "Ready"},
		)
		self.assertEqual(result["code"], OUTCOME_ACCOUNTING_EVENT_MISSING)
		self.assertIn("Create or import", result["message"])
		nearby_event.assert_called_once()

	@patch("retailedge.bank_candidate_engine._has_nearby_submitted_accounting_event", return_value=True)
	def test_nearby_accounting_event_that_failed_safety_is_distinct(self, nearby_event):
		result = _candidate_search_outcome(
			{"direction": "Outflow", "amount": 185000},
			[],
			{"readiness": "Warning"},
		)
		self.assertEqual(result["code"], OUTCOME_ACCOUNTING_EVENT_NOT_ELIGIBLE)
		self.assertIn("failed bank-account, reference, direction, or eligibility", result["message"])
		nearby_event.assert_called_once()

	def test_found_but_non_reviewable_evidence_is_distinct(self):
		result = _candidate_search_outcome(
			{"direction": "Inflow", "amount": 1000},
			[{"document_type": "Sales Invoice", "document_name": "SI-1", "review_supported": 0}],
			{"readiness": "Ready"},
		)
		self.assertEqual(result["code"], OUTCOME_CANDIDATE_REVIEW_BLOCKED)

	def test_safe_candidates_keep_normal_candidate_dialog_flow(self):
		result = _candidate_search_outcome(
			{"direction": "Inflow", "amount": 1000},
			[{"document_type": "Payment Entry", "document_name": "PE-1", "review_supported": 1}],
			{"readiness": "Ready"},
		)
		self.assertEqual(result["code"], OUTCOME_CANDIDATES_FOUND)

	def test_notification_asset_is_valid_and_page_scoped(self):
		completed = subprocess.run(
			["node", "--check", str(OUTCOME_ASSET)],
			capture_output=True,
			text=True,
			check=False,
		)
		self.assertEqual(completed.returncode, 0, completed.stderr)
		asset = OUTCOME_ASSET.read_text()
		self.assertIn('const PAGE_NAME = "bank-matching-reconciliation"', asset)
		self.assertIn("get_direction_aware_bank_candidates", asset)
		self.assertIn("candidate_review_blocked", asset)
		self.assertIn("Open Banking Readiness", asset)
		self.assertIn("suppressGenericNoCandidateOnce", asset)
		self.assertIn("isBankMatchingPage()", asset)

	def test_page_loader_loads_outcome_adapter_before_workspace(self):
		loader = PAGE_LOADER.read_text()
		self.assertIn("bank_candidate_outcome_notifications.js", loader)
		self.assertLess(
			loader.index("frappe.require(OUTCOME_ASSET)"),
			loader.index("frappe.require(ASSET)"),
		)


if __name__ == "__main__":
	unittest.main()
