from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from retailedge.cashier_expense_accounting import (
	_post_cashier_expense_to_accounts,
	attempt_direct_cashier_expense_posting,
)
from retailedge.cashier_expense_posting import (
	build_cashier_expense_posting_preview,
	get_effective_cashier_expense_posting_settings,
)


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


def _expense(*, mode: str, status: str = "Submitted"):
	return SimpleNamespace(
		doctype="RetailEdge Cashier Expense",
		name="RE-CE-TEST-0001",
		docstatus=1,
		expense_status=status,
		ledger_status="Pending Ledger" if status == "Pending Ledger" else "Not Applicable",
		posting_mode_applied=mode,
		posting_reference=None,
		company="Demo Company",
		expense_date="2026-10-01",
		amount=100,
		expense_account="Expense - DEMO",
		payment_account="Cash - DEMO",
		cost_center=None,
		expense_category="General",
		branch="Main",
	)


class CashierExpensePostingPolicySnapshotTests(unittest.TestCase):
	def test_effective_settings_preserve_captured_controlled_mode(self):
		settings = get_effective_cashier_expense_posting_settings(
			_expense(mode="Controlled Posting"),
			settings=_settings("Direct Posting"),
		)
		self.assertEqual(settings["posting_mode"], "Controlled Posting")
		self.assertTrue(settings["require_approval_before_posting"])

	def test_effective_settings_preserve_captured_direct_mode(self):
		settings = get_effective_cashier_expense_posting_settings(
			_expense(mode="Direct Posting"),
			settings=_settings("Controlled Posting"),
		)
		self.assertEqual(settings["posting_mode"], "Direct Posting")
		self.assertFalse(settings["require_approval_before_posting"])

	@patch("retailedge.cashier_expense_posting._validate_credit_account", return_value=[])
	@patch("retailedge.cashier_expense_posting._validate_debit_account", return_value=[])
	@patch("retailedge.cashier_expense_posting._get_active_workflow", return_value=None)
	@patch(
		"retailedge.cashier_expense_posting.get_cashier_expense_posting_settings",
		return_value=_settings("Direct Posting"),
	)
	def test_controlled_submitted_record_stays_blocked_after_global_switch_to_direct(
		self,
		_mock_settings,
		_mock_workflow,
		_mock_debit,
		_mock_credit,
	):
		preview = build_cashier_expense_posting_preview(
			_expense(mode="Controlled Posting", status="Submitted")
		)
		self.assertFalse(preview["posting_ready"])
		self.assertEqual(preview["posting_mode"], "Controlled Posting")
		self.assertIn("Controlled Posting requires approval", preview["posting_block_reason"])

	@patch("retailedge.cashier_expense_posting._validate_credit_account", return_value=[])
	@patch("retailedge.cashier_expense_posting._validate_debit_account", return_value=[])
	@patch("retailedge.cashier_expense_posting._get_active_workflow", return_value=None)
	@patch(
		"retailedge.cashier_expense_posting.get_cashier_expense_posting_settings",
		return_value=_settings("Direct Posting"),
	)
	def test_controlled_pending_ledger_record_stays_ready_after_global_switch_to_direct(
		self,
		_mock_settings,
		_mock_workflow,
		_mock_debit,
		_mock_credit,
	):
		preview = build_cashier_expense_posting_preview(
			_expense(mode="Controlled Posting", status="Pending Ledger")
		)
		self.assertTrue(preview["posting_ready"])
		self.assertEqual(preview["posting_mode"], "Controlled Posting")

	@patch("retailedge.cashier_expense_posting._validate_credit_account", return_value=[])
	@patch("retailedge.cashier_expense_posting._validate_debit_account", return_value=[])
	@patch("retailedge.cashier_expense_posting._get_active_workflow", return_value=None)
	@patch(
		"retailedge.cashier_expense_posting.get_cashier_expense_posting_settings",
		return_value=_settings("Controlled Posting"),
	)
	def test_direct_submitted_record_does_not_gain_approval_after_global_switch_to_controlled(
		self,
		_mock_settings,
		_mock_workflow,
		_mock_debit,
		_mock_credit,
	):
		preview = build_cashier_expense_posting_preview(
			_expense(mode="Direct Posting", status="Submitted")
		)
		self.assertTrue(preview["posting_ready"])
		self.assertEqual(preview["posting_mode"], "Direct Posting")

	@patch("retailedge.cashier_expense_accounting.build_cashier_expense_posting_preview")
	@patch(
		"retailedge.cashier_expense_accounting.get_effective_cashier_expense_posting_settings",
		return_value=_settings("Controlled Posting"),
	)
	def test_automatic_direct_post_does_not_run_for_captured_controlled_record(
		self,
		_mock_settings,
		mock_preview,
	):
		result = attempt_direct_cashier_expense_posting(
			_expense(mode="Controlled Posting", status="Pending Ledger")
		)
		self.assertEqual(result, {"attempted": False, "posted": False})
		mock_preview.assert_not_called()

	@patch("retailedge.cashier_expense_accounting.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense_accounting.frappe.db.set_value")
	@patch("retailedge.cashier_expense_accounting._get_active_workflow", return_value=None)
	@patch("retailedge.cashier_expense_accounting._build_journal_entry")
	@patch("retailedge.cashier_expense_accounting.build_cashier_expense_posting_preview")
	@patch("retailedge.cashier_expense_accounting._assert_posting_access")
	@patch(
		"retailedge.cashier_expense_accounting.get_effective_cashier_expense_posting_settings",
		return_value=_settings("Controlled Posting"),
	)
	@patch("retailedge.cashier_expense_accounting._posting_reference_state")
	@patch("retailedge.cashier_expense_accounting._lock_cashier_expense")
	@patch("retailedge.cashier_expense_accounting.frappe.get_doc")
	def test_post_action_log_uses_captured_mode(
		self,
		mock_get_doc,
		_mock_lock,
		mock_reference_state,
		_mock_effective_settings,
		_mock_access,
		mock_preview,
		mock_build_journal,
		_mock_workflow,
		_mock_set_value,
		mock_log,
	):
		doc = _expense(mode="Controlled Posting", status="Pending Ledger")
		posted_doc = _expense(mode="Controlled Posting", status="Posted")
		posted_doc.ledger_status = "Posted"
		mock_get_doc.side_effect = [doc, posted_doc]
		mock_reference_state.return_value = {
			"exists": False,
			"submitted": False,
			"name": "",
			"type": "",
		}
		mock_preview.return_value = {
			"posting_ready": True,
			"posting_document_type": "Journal Entry",
			"posting_mode": "Controlled Posting",
			"debit_account": "Expense - DEMO",
			"credit_account": "Cash - DEMO",
			"remarks": "RetailEdge Cashier Expense RE-CE-TEST-0001 - General",
			"cost_center": None,
		}
		journal = Mock()
		journal.name = "ACC-JV-TEST-0001"
		journal.docstatus = 0
		journal.has_permission.return_value = True

		def _submit():
			journal.docstatus = 1

		journal.submit.side_effect = _submit
		mock_build_journal.return_value = journal

		_post_cashier_expense_to_accounts(doc.name, automatic=False)

		context = mock_log.call_args.kwargs["context"]
		self.assertEqual(context["posting_mode"], "Controlled Posting")


if __name__ == "__main__":
	unittest.main()
