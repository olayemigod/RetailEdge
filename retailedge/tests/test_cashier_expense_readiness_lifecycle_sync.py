from __future__ import annotations

import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from retailedge.cashier_expense import (
	_refresh_posting_readiness_after_lifecycle_transition,
	approve_cashier_expense,
	reject_cashier_expense,
	reopen_cashier_expense,
	submit_cashier_expense,
)
from retailedge.cashier_expense_detail import (
	apply_cashier_expense_workflow_action,
	submit_cashier_expense_for_review,
)


class TestCashierExpenseReadinessLifecycleSync(unittest.TestCase):
	@patch("retailedge.cashier_expense_posting.refresh_cashier_expense_posting_readiness")
	def test_lifecycle_sync_refreshes_canonical_readiness_and_reloads_document(self, refresh):
		doc = SimpleNamespace(name="RE-CE-TEST-0001")
		doc.reload = unittest.mock.Mock()

		result = _refresh_posting_readiness_after_lifecycle_transition(doc)

		refresh.assert_called_once_with("RE-CE-TEST-0001")
		doc.reload.assert_called_once_with()
		self.assertIs(result, doc)

	def test_non_workflow_lifecycle_transitions_refresh_posting_readiness(self):
		for fn in (
			submit_cashier_expense,
			approve_cashier_expense,
			reject_cashier_expense,
			reopen_cashier_expense,
		):
			with self.subTest(function=fn.__name__):
				source = inspect.getsource(fn)
				self.assertIn("_refresh_posting_readiness_after_lifecycle_transition", source)

	def test_edgesuite_native_submit_refreshes_before_returning_detail(self):
		source = inspect.getsource(submit_cashier_expense_for_review)
		self.assertLess(source.index("doc.submit()"), source.index("refresh_cashier_expense_posting_readiness(doc.name)"))
		self.assertLess(source.index("refresh_cashier_expense_posting_readiness(doc.name)"), source.index("get_cashier_expense_detail(doc.name)"))

	def test_frappe_workflow_path_keeps_existing_readiness_refresh(self):
		source = inspect.getsource(apply_cashier_expense_workflow_action)
		self.assertIn("refresh_cashier_expense_posting_readiness(expense_name)", source)
		self.assertLess(
			source.index("apply_document_workflow_action("),
			source.index("refresh_cashier_expense_posting_readiness(expense_name)"),
		)
