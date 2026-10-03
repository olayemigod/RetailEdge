from __future__ import annotations

import unittest
from unittest.mock import patch

from frappe import _dict

from retailedge.cashier_expense_branch_reconciliation import (
	_classify_row,
	_repair_row,
)


class TestCashierExpenseBranchReconciliation(unittest.TestCase):
	def _row(self, **overrides):
		row = _dict(
			name="RE-CE-2026-0011",
			company="RetailEdge Consulting",
			branch="Lagos Island",
			pos_profile="Ketu POS Profile",
			linked_pos_opening_shift="POSA-OS-26-0000003",
			expense_status="Posted",
			ledger_status="Posted",
			posting_reference_type="Journal Entry",
			posting_reference="ACC-JV-2026-00003",
			docstatus=1,
		)
		row.update(overrides)
		return row

	@patch("retailedge.cashier_expense_branch_reconciliation.frappe.db.get_value")
	@patch("retailedge.cashier_expense_branch_reconciliation.frappe.get_all")
	def test_proven_blank_profile_wildcard_mismatch_is_repairable(self, mock_get_all, mock_get_value):
		mock_get_all.side_effect = [
			[_dict(name="Ketu", branch="Ketu", default_pos_profile="Ketu POS Profile")],
			[_dict(name="Lagos Island", branch="Lagos Island", default_pos_profile=None)],
		]
		mock_get_value.return_value = "Ketu POS Profile"

		result = _classify_row(self._row())

		self.assertEqual(result["status"], "repairable")
		self.assertEqual(result["target_branch"], "Ketu")

	@patch("retailedge.cashier_expense_branch_reconciliation.frappe.get_all")
	def test_exact_current_branch_is_left_unchanged(self, mock_get_all):
		mock_get_all.return_value = [
			_dict(name="Ketu", branch="Ketu", default_pos_profile="Ketu POS Profile")
		]

		result = _classify_row(self._row(branch="Ketu"))

		self.assertEqual(result["status"], "already_correct")
		self.assertEqual(result["target_branch"], "Ketu")

	@patch("retailedge.cashier_expense_branch_reconciliation.frappe.get_all")
	def test_multiple_exact_pos_profile_mappings_fail_closed(self, mock_get_all):
		mock_get_all.return_value = [
			_dict(name="Ketu", branch="Ketu", default_pos_profile="Ketu POS Profile"),
			_dict(name="Other", branch="Other", default_pos_profile="Ketu POS Profile"),
		]

		result = _classify_row(self._row())

		self.assertEqual(result["status"], "ambiguous")
		self.assertIsNone(result["target_branch"])

	@patch("retailedge.cashier_expense_branch_reconciliation.frappe.get_all")
	def test_current_branch_with_explicit_different_profile_is_not_auto_repaired(self, mock_get_all):
		mock_get_all.side_effect = [
			[_dict(name="Ketu", branch="Ketu", default_pos_profile="Ketu POS Profile")],
			[_dict(name="Lagos Island", branch="Lagos Island", default_pos_profile="Island POS")],
		]

		result = _classify_row(self._row())

		self.assertEqual(result["status"], "skipped")
		self.assertEqual(result["target_branch"], "Ketu")

	@patch("retailedge.cashier_expense_branch_reconciliation.frappe.db.get_value")
	@patch("retailedge.cashier_expense_branch_reconciliation.frappe.get_all")
	def test_opening_shift_profile_mismatch_fails_closed(self, mock_get_all, mock_get_value):
		mock_get_all.side_effect = [
			[_dict(name="Ketu", branch="Ketu", default_pos_profile="Ketu POS Profile")],
			[_dict(name="Lagos Island", branch="Lagos Island", default_pos_profile=None)],
		]
		mock_get_value.return_value = "Another POS Profile"

		result = _classify_row(self._row())

		self.assertEqual(result["status"], "ambiguous")
		self.assertEqual(result["target_branch"], "Ketu")

	@patch("retailedge.cashier_expense_branch_reconciliation.append_cashier_expense_action_log")
	@patch("retailedge.cashier_expense_branch_reconciliation.frappe.db.set_value")
	def test_repair_changes_only_expense_branch_and_logs_evidence(self, mock_set_value, mock_log):
		row = self._row()
		classification = {
			"status": "repairable",
			"target_branch": "Ketu",
			"reason": "Historical blank POS-profile wildcard attribution is proven.",
		}

		_repair_row(row, classification)

		mock_set_value.assert_called_once_with(
			"RetailEdge Cashier Expense",
			"RE-CE-2026-0011",
			"branch",
			"Ketu",
			update_modified=False,
		)
		mock_log.assert_called_once()
		kwargs = mock_log.call_args.kwargs
		self.assertEqual(kwargs["action"], "Branch Attribution Reconciled")
		self.assertEqual(kwargs["context"]["old_branch"], "Lagos Island")
		self.assertEqual(kwargs["context"]["new_branch"], "Ketu")
		self.assertEqual(kwargs["context"]["posting_reference"], "ACC-JV-2026-00003")


if __name__ == "__main__":
	unittest.main()
