from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
REPORTING = APP_ROOT / "reporting_capabilities.py"
DASHBOARDS = APP_ROOT / "dashboard_capabilities.py"
STOCK_POSITION = APP_ROOT / "stock_position.py"
CUSTOMER_RECEIVABLES = APP_ROOT / "customer_receivables.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_report_and_dashboard_capability_gates_use_shared_assignment_aware_scope():
	reporting = _read(REPORTING)
	dashboards = _read(DASHBOARDS)
	assert "validate_report_scope" in reporting
	assert "get_operational_branch_scope" in dashboards
	assert "validate_operating_branch" in dashboards
	for source in (reporting, dashboards):
		assert "frappe.PermissionError" in source
		assert "ignore_permissions" not in source
	for legacy_contract in (
		"get_user_allowed_branches",
		"user_has_global_branch_access",
		"_company_branch_count",
		'frappe.db.count("Branch", filters={"company": company})',
	):
		assert legacy_contract not in dashboards


def test_scope_gates_keep_company_and_explicit_branch_permission_checks():
	reporting = _read(REPORTING)
	dashboards = _read(DASHBOARDS)
	assert "validate_report_scope(" in reporting
	assert 'frappe.has_permission("Company", "read", doc=company, user=user)' in dashboards
	assert "validate_operating_branch(company=company, branch=branch, user=user, throw=True)" in dashboards
	assert "ignore_permissions" not in reporting
	assert "ignore_permissions" not in dashboards


def test_stock_position_omitted_branch_already_resolves_only_permitted_warehouses():
	source = _read(STOCK_POSITION)
	assert "user_has_global_branch_access(user=user)" in source
	assert "_allowed_branch_warehouses(company, user=user)" in source
	assert '_("No permitted Warehouse scope could be resolved for Stock Position.")' in source
	assert "frappe.PermissionError" in source


def test_customer_receivables_keeps_explicit_branch_validation_and_permission_aware_query():
	source = _read(CUSTOMER_RECEIVABLES)
	assert "get_operational_branch_scope(filters.company, user=user)" in source
	assert "validate_operating_branch(company=company, branch=branch, user=user, throw=True)" in source
	assert 'frappe.has_permission("Sales Invoice", "read")' in source
	assert 'frappe.get_list(\n\t\t"Sales Invoice"' in source
	assert "ignore_permissions" not in source
