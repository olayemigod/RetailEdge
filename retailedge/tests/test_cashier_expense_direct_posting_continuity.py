from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from retailedge.cashier_expense_detail import _workflow_actions
from retailedge.cashier_expense_posting import get_effective_cashier_expense_posting_settings
from retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense import (
	RetailEdgeCashierExpense,
)

APP_ROOT = Path(__file__).resolve().parents[1]
SIMPLE_DIALOG = APP_ROOT / "public/js/retailedge_business_hub/SimpleCashierExpenseDialog.vue"
DETAIL_DIALOG = APP_ROOT / "public/js/expense_register/CashierExpenseDetailDialog.vue"
DETAIL_BACKEND = APP_ROOT / "cashier_expense_detail.py"


def _settings(mode: str) -> dict:
	return {
		"enabled": True,
		"posting_mode": mode,
		"posting_document_type": "Journal Entry",
		"require_approval_before_posting": mode == "Controlled Posting",
		"allow_rejected_posting": False,
		"remark_template": "RetailEdge Cashier Expense {expense_name} - {expense_category}",
		"default_payable_account": None,
		"posting_workflow_state": "",
		"posting_roles": set(),
		"posting_roles_configured": False,
	}


class CashierExpenseDirectPostingContinuityTests(unittest.TestCase):
	def test_draft_policy_tracks_current_setting_until_submit_boundary(self):
		doc = SimpleNamespace(docstatus=0, posting_mode_applied="Controlled Posting")

		settings = get_effective_cashier_expense_posting_settings(
			doc,
			settings=_settings("Direct Posting"),
		)

		self.assertEqual(settings["posting_mode"], "Direct Posting")
		self.assertFalse(settings["require_approval_before_posting"])
		self.assertEqual(doc.posting_mode_applied, "Direct Posting")

	def test_submitted_policy_remains_historical_after_global_change(self):
		doc = SimpleNamespace(docstatus=1, posting_mode_applied="Controlled Posting")

		settings = get_effective_cashier_expense_posting_settings(
			doc,
			settings=_settings("Direct Posting"),
		)

		self.assertEqual(settings["posting_mode"], "Controlled Posting")
		self.assertTrue(settings["require_approval_before_posting"])
		self.assertEqual(doc.posting_mode_applied, "Controlled Posting")

	@patch(
		"retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense.get_cashier_expense_posting_settings",
		return_value=_settings("Direct Posting"),
	)
	def test_before_submit_replaces_stale_draft_snapshot_with_current_mode(self, _mock_settings):
		doc = SimpleNamespace(
			docstatus=0,
			expense_status="Draft",
			cash_movement_status="Not Disbursed",
			posting_mode_applied="Controlled Posting",
			ledger_status="Not Applicable",
			set_posting_readiness_preview=Mock(),
		)

		RetailEdgeCashierExpense.before_submit(doc)

		self.assertEqual(doc.expense_status, "Submitted")
		self.assertEqual(doc.cash_movement_status, "Disbursed")
		self.assertEqual(doc.posting_mode_applied, "Direct Posting")
		self.assertEqual(doc.ledger_status, "Pending Ledger")

	@patch("retailedge.cashier_expense_detail.user_has_any_role", return_value=False)
	@patch("retailedge.cashier_expense_detail.get_cashier_expense_posting_permissions", return_value={"can_post": False})
	@patch("retailedge.cashier_expense_detail.frappe.has_permission", return_value=True)
	@patch("retailedge.cashier_expense_detail.user_is_reviewer", return_value=True)
	@patch("retailedge.cashier_expense_detail.frappe.get_roles", return_value=["RetailEdge Manager"])
	@patch("retailedge.cashier_expense_detail.get_cashier_expense_posting_settings", return_value=_settings("Direct Posting"))
	def test_direct_submitted_expense_does_not_offer_approval_actions(
		self,
		_mock_settings,
		_mock_roles,
		_mock_reviewer,
		_mock_permission,
		_mock_posting_permissions,
		_mock_refresh_roles,
	):
		expense = {
			"name": "RE-CE-TEST-DIRECT",
			"docstatus": 1,
			"expense_status": "Submitted",
			"ledger_status": "Pending Ledger",
			"posting_ready": 1,
			"posting_mode_applied": "Direct Posting",
			"posting_block_reason": None,
			"cashier": "cashier@example.com",
		}
		doc = SimpleNamespace(
			doctype="RetailEdge Cashier Expense",
			name=expense["name"],
			docstatus=1,
			posting_mode_applied="Direct Posting",
		)
		workflow_readiness = {"source": "retailedge", "available_actions": []}
		with patch("retailedge.cashier_expense_detail.frappe.session", SimpleNamespace(user="manager@example.com")):
			actions = _workflow_actions(expense, doc=doc, workflow_readiness=workflow_readiness)

		self.assertEqual(actions["posting_mode"], "Direct Posting")
		self.assertFalse(actions["can_approve"])
		self.assertFalse(actions["can_reject"])
		self.assertFalse(actions["can_reopen"])

	def test_guided_modal_keeps_draft_open_until_submit_action(self):
		source = SIMPLE_DIALOG.read_text(encoding="utf-8")
		save_start = source.index("async saveDraft()")
		submit_start = source.index("async submitDraft()", save_start)
		save_segment = source[save_start:submit_start]
		submit_segment = source[submit_start:source.index("formatAmount(value)", submit_start)]

		self.assertIn("this.draftResult = result || null", save_segment)
		self.assertNotIn('this.$emit("saved"', save_segment)
		self.assertIn('this.$emit("saved"', submit_segment)
		self.assertIn("v-if=\"draftSaved\"", source)
		self.assertIn('return this.postingMode === "Direct Posting" ? "Submit Expense" : "Submit for Review"', source)
		self.assertIn("retailedge.cashier_expense_detail.submit_cashier_expense_for_review", source)

	def test_detail_dialog_uses_effective_policy_for_badge_and_submit_wording(self):
		source = DETAIL_DIALOG.read_text(encoding="utf-8")
		self.assertIn("effectivePostingMode()", source)
		self.assertIn("submitActionLabel()", source)
		self.assertIn('{{ actionBusy ? "Working..." : submitActionLabel }}', source)
		self.assertIn('this.effectivePostingMode === "Direct Posting" ? "Submit Expense" : "Submit for Review"', source)
		self.assertIn('v-if="effectivePostingMode" class="workflow-mode"', source)

	def test_detail_backend_gates_review_actions_to_controlled_posting(self):
		source = DETAIL_BACKEND.read_text(encoding="utf-8")
		self.assertIn('controlled_posting = posting.get("posting_mode") == "Controlled Posting"', source)
		self.assertIn("and controlled_posting", source)
		self.assertIn("get_effective_cashier_expense_posting_settings", source)


if __name__ == "__main__":
	unittest.main()
