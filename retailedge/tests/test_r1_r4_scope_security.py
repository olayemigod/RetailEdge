from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPORTING = APP_ROOT / "reporting_capabilities.py"
DASHBOARDS = APP_ROOT / "dashboard_capabilities.py"
STOCK_POSITION = APP_ROOT / "stock_position.py"
CUSTOMER_RECEIVABLES = APP_ROOT / "customer_receivables.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_report_and_dashboard_capability_gates_fail_closed_for_unresolved_multi_branch_scope():
	for path in (REPORTING, DASHBOARDS):
		source = _read(path)
		for expected in (
			"get_user_allowed_branches",
			"user_has_global_branch_access",
			"_company_branch_count(company) <= 1",
			'frappe.db.count("Branch", filters={"company": company})',
			'_("Your Branch access is not configured for this multi-branch Company.")',
			"frappe.PermissionError",
		):
			assert expected in source


def test_scope_gates_keep_company_and_explicit_branch_permission_checks():
	for path in (REPORTING, DASHBOARDS):
		source = _read(path)
		assert 'frappe.has_permission("Company", "read", doc=company, user=user)' in source
		assert "validate_user_branch_access(branch, user=user, company=company or None, throw=True)" in source
		assert "ignore_permissions" not in source


def test_stock_position_omitted_branch_already_resolves_only_permitted_warehouses():
	source = _read(STOCK_POSITION)
	assert "user_has_global_branch_access(user=user)" in source
	assert "_allowed_branch_warehouses(company, user=user)" in source
	assert '_("No permitted Warehouse scope could be resolved for Stock Position.")' in source
	assert "frappe.PermissionError" in source


def test_customer_receivables_keeps_explicit_branch_validation_and_permission_aware_query():
	source = _read(CUSTOMER_RECEIVABLES)
	assert "validate_user_branch_access(branch, user=user, company=filters.company, throw=True)" in source
	assert 'frappe.has_permission("Sales Invoice", "read")' in source
	assert 'frappe.get_list(\n\t\t"Sales Invoice"' in source
	assert "ignore_permissions" not in source
