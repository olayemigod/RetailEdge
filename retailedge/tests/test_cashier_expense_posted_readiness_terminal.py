from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from retailedge.cashier_expense_posting import (
	build_cashier_expense_posting_preview,
	refresh_cashier_expense_posting_readiness,
	refresh_pending_cashier_expense_posting_readiness,
)


def _settings() -> dict:
	return {
		"enabled": True,
		"posting_mode": "Direct Posting",
		"posting_document_type": "Journal Entry",
		"require_approval_before_posting": False,
		"allow_rejected_posting": False,
		"remark_template": "RetailEdge Cashier Expense {expense_name} - {expense_category}",
		"default_payable_account": None,
		"posting_workflow_state": "",
		"posting_roles": set(),
		"posting_roles_configured": False,
	}


def _expense(*, posting_reference: str | None):
	return SimpleNamespace(
		doctype="RetailEdge Cashier Expense",
		name="RE-CE-TEST-POSTED",
		docstatus=1,
		expense_status="Posted",
		ledger_status="Posted",
		posting_mode_applied="Direct Posting",
		posting_reference=posting_reference,
		company="Demo Company",
		expense_date="2026-10-08",
		amount=1500,
		expense_account="Expense - DEMO",
		payment_account="Cash - DEMO",
		cost_center="Main - DEMO",
		expense_category="General",
	)


class CashierExpensePostedReadinessTerminalTests(unittest.TestCase):
	@patch("retailedge.cashier_expense_posting._validate_credit_account", return_value=[])
	@patch("retailedge.cashier_expense_posting._validate_debit_account", return_value=[])
	@patch("retailedge.cashier_expense_posting._get_active_workflow", return_value=None)
	@patch("retailedge.cashier_expense_posting.get_cashier_expense_posting_settings", return_value=_settings())
	def test_fully_posted_expense_is_terminal_not_blocked(
		self,
		_mock_settings,
		_mock_workflow,
		_mock_debit,
		_mock_credit,
	):
		preview = build_cashier_expense_posting_preview(
			_expense(posting_reference="ACC-JV-2026-00010")
		)

		self.assertTrue(preview["posting_complete"])
		self.assertFalse(preview["posting_ready"])
		self.assertIsNone(preview["posting_block_reason"])
		self.assertNotIn("Block Reason:", preview["posting_preview"])

	@patch("retailedge.cashier_expense_posting._validate_credit_account", return_value=[])
	@patch("retailedge.cashier_expense_posting._validate_debit_account", return_value=[])
	@patch("retailedge.cashier_expense_posting._get_active_workflow", return_value=None)
	@patch("retailedge.cashier_expense_posting.get_cashier_expense_posting_settings", return_value=_settings())
	def test_posted_status_without_reference_remains_an_inconsistency(
		self,
		_mock_settings,
		_mock_workflow,
		_mock_debit,
		_mock_credit,
	):
		preview = build_cashier_expense_posting_preview(_expense(posting_reference=None))

		self.assertFalse(preview["posting_complete"])
		self.assertFalse(preview["posting_ready"])
		self.assertIn("already marked as Posted", preview["posting_block_reason"])

	@patch("retailedge.cashier_expense_posting.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense_posting.frappe.db.set_value")
	@patch("retailedge.cashier_expense_posting.get_cashier_expense_posting_preview")
	def test_refresh_clears_stale_blocker_for_completed_posting(
		self,
		mock_preview,
		mock_set_value,
		_mock_log,
	):
		mock_preview.return_value = {
			"posting_ready": False,
			"posting_complete": True,
			"posting_block_reason": None,
			"posting_document_type": "Journal Entry",
			"debit_account": "Expense - DEMO",
			"credit_account": "Cash - DEMO",
			"cost_center": "Main - DEMO",
			"posting_preview": "Posting Ready: No",
		}

		refresh_cashier_expense_posting_readiness("RE-CE-TEST-POSTED", log_action=False)

		values = mock_set_value.call_args.args[2]
		self.assertEqual(values["posting_ready"], 0)
		self.assertIsNone(values["posting_block_reason"])
		self.assertIsNone(values["user_message"])

	@patch("retailedge.cashier_expense_posting.refresh_cashier_expense_posting_readiness")
	@patch("retailedge.cashier_expense_posting.frappe.get_all")
	@patch("retailedge.cashier_expense_posting._assert_refresh_access")
	def test_batch_refresh_does_not_count_completed_postings_as_blocked(
		self,
		_mock_access,
		mock_get_all,
		mock_refresh,
	):
		mock_get_all.return_value = [
			SimpleNamespace(name="RE-CE-POSTED"),
			SimpleNamespace(name="RE-CE-BLOCKED"),
			SimpleNamespace(name="RE-CE-READY"),
		]
		mock_refresh.side_effect = [
			{"posting_complete": True, "posting_ready": False},
			{"posting_complete": False, "posting_ready": False},
			{"posting_complete": False, "posting_ready": True},
		]

		result = refresh_pending_cashier_expense_posting_readiness()

		self.assertEqual(result, {"updated_count": 1, "blocked_count": 1})


if __name__ == "__main__":
	unittest.main()
