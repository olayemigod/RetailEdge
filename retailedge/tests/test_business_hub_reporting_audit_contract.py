from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _roles(page_name: str) -> set[str]:
	page = ROOT / "retailedge" / "page" / page_name.replace("-", "_") / f'{page_name.replace("-", "_")}.json'
	payload = json.loads(page.read_text(encoding="utf-8"))
	return {row["role"] for row in payload.get("roles") or []}


def test_reporting_capability_registry_matches_approved_page_view_roles():
	source = (ROOT / "reporting_capabilities.py").read_text(encoding="utf-8")
	for role in ("Accounts Manager", "Accounts User"):
		assert role in _roles("sales-invoice-register")
		assert role in _roles("sales-by-item")
	assert '_ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES' in source
	assert {"RetailEdge Cashier", "RetailEdgeCashier"}.issubset(_roles("expense-register"))
	assert '_CASHIER_ROLES = {"RetailEdge Cashier", "RetailEdgeCashier"}' in source
	assert 'view_roles=_roles(_MANAGER_ROLES, _BRANCH_MANAGER_ROLES, _ACCOUNTS_MANAGER_ROLES, _ACCOUNTS_USER_ROLES, _CASHIER_ROLES)' in source


def test_server_read_paths_enforce_report_role_family_without_replacing_branch_scope():
	capabilities = (ROOT / "reporting_capabilities.py").read_text(encoding="utf-8")
	assert "def require_report_view_access(" in capabilities
	assert '"authorization_model": "report_role_and_document_permission"' in capabilities
	helper = capabilities.split("def require_report_view_access(", 1)[1].split("def get_report_capabilities(", 1)[0]
	assert "validate_report_scope(" not in helper

	contracts = {
		"sales_reporting.py": 'require_report_view_access("sales-invoice-register")',
		"purchase_reporting.py": 'require_report_view_access("purchase-register")',
		"customer_receivables.py": 'require_report_view_access("customer-receivables")',
		"stock_position.py": 'require_report_view_access("stock-position")',
		"expense_register.py": 'require_report_view_access("expense-register")',
		"cash_shift_verification_read_scope.py": 'require_report_view_access("cash-shift-verification")',
		"expense_review.py": 'require_report_view_access("expense-review")',
	}
	for relative, token in contracts.items():
		source = (ROOT / relative).read_text(encoding="utf-8")
		assert token in source
		assert "ignore_permissions=True" not in source


def test_business_hub_destinations_remain_edgesuite_owned():
	contracts = {
		"public/js/sales_reporting/SalesReportingReport.vue": "EdgeReportShell",
		"public/js/purchase_reporting/PurchaseReportingReport.vue": "EdgeReportShell",
		"public/js/cash_movement/CashMovementReport.vue": "EdgeReportShell",
		"public/js/expense_register/ExpenseRegisterReport.vue": "EdgeReportShell",
		"public/js/expense_review/ExpenseReviewReport.vue": "EdgeReportShell",
		"public/js/cash_shift_verification/CashShiftVerificationReport.vue": "EdgeReportShell",
		"public/js/customer_receivables/CustomerReceivablesReport.vue": "EdgeReportShell",
		"public/js/stock_position/StockPositionReport.vue": "EdgeReportShell",
		"public/js/profitability_intelligence/ProfitabilityIntelligence.vue": "EdgeDashboardShell",
		"public/js/bank_matching_edgesuite_workspace.js": 'getComponent("EdgeAppShell")',
	}
	for relative, shell in contracts.items():
		source = (ROOT / relative).read_text(encoding="utf-8")
		assert "EdgeAppShell" in source
		assert shell in source


def test_report_context_and_option_search_rpcs_use_same_role_gate():
	contracts = {
		"sales_reporting.py": ('get_sales_reporting_context', 'search_sales_reporting_options', 'require_report_view_access("sales-invoice-register")'),
		"purchase_reporting.py": ('get_purchase_reporting_context', 'search_purchase_reporting_options', 'require_report_view_access("purchase-register")'),
		"customer_receivables.py": ('get_customer_receivables_context', 'search_customer_receivables_options', 'require_report_view_access("customer-receivables")'),
		"stock_position.py": ('get_stock_position_context', 'search_stock_position_options', 'require_report_view_access("stock-position")'),
	}
	for relative, (context_name, search_name, gate) in contracts.items():
		source = (ROOT / relative).read_text(encoding="utf-8")
		context = source.split(f"def {context_name}", 1)[1].split("@frappe.whitelist()", 1)[0]
		search = source.split(f"def {search_name}", 1)[1]
		assert gate in context
		assert gate in search


def test_banking_operational_roles_match_page_access_and_exclude_auditor_mutation():
	matching = (ROOT / "bank_transaction_matching.py").read_text(encoding="utf-8")
	summary = (ROOT / "bank_exception_summary.py").read_text(encoding="utf-8")
	page_roles = _roles("bank-matching-reconciliation")
	assert "RetailEdge Auditor" not in page_roles
	role_block = matching.split("BANK_TRANSACTION_MATCHING_ROLES =", 1)[1].split("}", 1)[0]
	assert "RetailEdge Auditor" not in role_block
	assert "RetailEdgeAuditor" not in role_block
	assert "assert_can_access_bank_transaction_matching()" in summary
