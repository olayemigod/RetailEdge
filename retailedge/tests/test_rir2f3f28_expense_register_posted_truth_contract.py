from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import business_expense_register as consolidated
from retailedge import expense_register


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/expense_register/ExpenseRegisterReport.vue"
DOC = ROOT.parent / "docs/rir2f3f28_expense_register_posted_truth.md"


def test_consolidated_default_excludes_unposted_cashier_expenses():
	source = inspect.getsource(expense_register)
	assert '"include_unposted_cashier_expenses": 0' in source


def test_cashier_rows_require_posted_ledger_by_default():
	source = inspect.getsource(consolidated)
	assert "if not include_unposted_cashier_expenses:" in source
	assert '"COALESCE(ce.ledger_status, \'\') = \'Posted\'"' in source
	assert '"COALESCE(ce.posting_reference, \'\') <> \'\'"' in source


def test_explicit_unposted_filter_is_separate_from_status_filtering():
	source = inspect.getsource(consolidated)
	assert 'cint(filters.get("include_unposted_cashier_expenses") or 0)' in source
	assert 'if status and status != "Posted":' in source
	assert 'return "", []' in source


def test_summary_separates_posted_truth_from_unposted_operational_exposure():
	source = inspect.getsource(consolidated)
	assert "AS posted_expense_total" in source
	assert "AS unposted_cashier_total" in source
	assert '"label": _("Posted Expenses")' in source
	assert '"label": _("Unposted Cashier Exposure")' in source


def test_ui_requires_explicit_opt_in_for_unposted_cashier_rows():
	source = COMPONENT.read_text(encoding="utf-8")
	assert "Include unposted Cashier Expenses" in source
	assert 'include_unposted_cashier_expenses: 0' in source
	assert ':true-value="1"' in source
	assert ':false-value="0"' in source


def test_reporting_contract_does_not_change_operational_calculation_policy():
	doc = DOC.read_text(encoding="utf-8")
	assert "does not change Cashier Expense workflow or posting" in doc
	assert "operational calculations may still include unposted Cashier Expenses" in doc
	assert "Posted accounting expense remains the financial reporting truth" in doc
