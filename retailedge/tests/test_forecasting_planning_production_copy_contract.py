from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLANNING = ROOT / "planning_intelligence.py"
EXPENSE_BUDGET = ROOT / "expense_budget.py"


def test_branch_planning_unavailable_copy_is_actionable_without_weakening_fail_closed_scope():
	text = PLANNING.read_text(encoding="utf-8")

	assert "Accounting expense forecast is company-level until Branch is mapped to a valid ERPNext accounting dimension or Cost Center." not in text
	assert "Accounting profitability forecast is company-level until Branch is mapped to a valid ERPNext accounting dimension or Cost Center." not in text
	assert "Branch-level expense forecasting is unavailable until this Branch has valid accounting attribution. Use Company-wide scope or complete Branch accounting setup." in text
	assert "Branch-level profitability forecasting is unavailable until this Branch has valid accounting attribution. Use Company-wide scope or complete Branch accounting setup." in text

	expense_block = text.split("def _expense_domain", 1)[1].split("def _profitability_domain", 1)[0]
	profit_block = text.split("def _profitability_domain", 1)[1].split("def _inventory_domain", 1)[0]
	assert "if filters.branch:" in expense_block
	assert "frappe.throw(" in expense_block
	assert "if filters.branch:" in profit_block
	assert "frappe.throw(" in profit_block


def test_budget_unavailable_copy_is_customer_safe_and_submitted_budget_truth_is_preserved():
	planning = PLANNING.read_text(encoding="utf-8")
	budget = EXPENSE_BUDGET.read_text(encoding="utf-8")

	assert "ERPNext Budget reference is not available for this scope." not in planning
	assert "Budget comparison is not available for this scope." in planning
	assert "ERPNext Budget is unavailable on this site." not in budget
	assert "Your current permissions do not allow ERPNext Budget insight." not in budget
	assert "No submitted ERPNext Budget matched the mapped expense accounts/cost centres for this period." not in budget
	assert "Budget comparison is unavailable on this site." in budget
	assert "Your current permissions do not allow budget comparison." in budget
	assert "No submitted budget matches the mapped expense accounts and cost centres for this period." in budget
	assert '"docstatus": 1' in budget
	assert '"budget_against": "Cost Center"' in budget
	assert '"account": ["in", accounts]' in budget
	assert '"cost_center": ["in", cost_centers]' in budget


def test_budget_comparison_remains_read_only_copy():
	budget = EXPENSE_BUDGET.read_text(encoding="utf-8")

	assert "Budget comparison is read-only here and does not change budget controls or approval settings." in budget
	assert "This is read-only planning metadata. It never creates, mutates, submits, or enforces a Budget." in budget
