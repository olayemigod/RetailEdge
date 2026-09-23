from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SMART_DATE_SURFACES = (
    "public/js/sales_reporting/SalesReportingReport.vue",
    "public/js/branch_performance_dashboard/BranchPerformanceDashboard.vue",
    "public/js/purchase_reporting/PurchaseReportingReport.vue",
    "public/js/expense_register/ExpenseRegisterReport.vue",
    "public/js/cash_movement/CashMovementReport.vue",
    "public/js/profitability_intelligence/ProfitabilityIntelligence.vue",
    "public/js/cash_shift_verification/CashShiftVerificationReport.vue",
    "public/js/daily_sales_audit/DailySalesAuditReport.vue",
    "public/js/expense_review/ExpenseReviewReport.vue",
    "public/js/payment_settlement_analysis/PaymentSettlementAnalysis.vue",
    "public/js/sales_quality_intelligence/SalesQualityIntelligence.vue",
    "public/js/expense_dashboard/ExpenseDashboard.vue",
    "public/js/sales_dashboard/SalesDashboard.vue",
    "public/js/salesperson_performance_dashboard/SalespersonPerformanceDashboardV2.vue",
    "public/js/stock_movement_history/StockMovementHistory.vue",
)

COMPANY_BRANCH_UI_SURFACES = (
    "public/js/sales_reporting/SalesReportingReport.vue",
    "public/js/branch_performance_dashboard/BranchPerformanceDashboard.vue",
    "public/js/purchase_reporting/PurchaseReportingReport.vue",
    "public/js/expense_register/ExpenseRegisterReport.vue",
    "public/js/cash_movement/CashMovementReport.vue",
    "public/js/profitability_intelligence/ProfitabilityIntelligence.vue",
    "public/js/cash_shift_verification/CashShiftVerificationReport.vue",
    "public/js/daily_sales_audit/DailySalesAuditReport.vue",
    "public/js/expense_review/ExpenseReviewReport.vue",
    "public/js/payment_settlement_analysis/PaymentSettlementAnalysis.vue",
    "public/js/sales_quality_intelligence/SalesQualityIntelligence.vue",
    "public/js/salesperson_performance_dashboard/SalespersonPerformanceDashboardV2.vue",
    "public/js/stock_movement_history/StockMovementHistory.vue",
)

COMPANY_BRANCH_BACKENDS = (
    "stock_movement_filters.py",
    "branch_performance_dashboard.py",
    "expense_register.py",
    "cash_movement.py",
    "payment_settlement_analysis.py",
    "salesperson_performance_dashboard.py",
)


def test_period_report_surfaces_use_one_smart_date_control():
    for relative in SMART_DATE_SURFACES:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "EdgeSmartDateRange" in text, relative
        assert "onSmartDateResolved" in text, relative
        assert 'v-model="filters.from_date"' not in text, relative
        assert 'v-model="filters.to_date"' not in text, relative
        assert 'v-model="filters.date_range_preset"' not in text, relative


def test_smart_date_resolves_to_exact_backend_dates_only():
    for relative in SMART_DATE_SURFACES:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "this.filters.from_date = value.from_date" in text, relative
        assert "this.filters.to_date = value.to_date" in text, relative


def test_company_change_clears_branch_on_report_surfaces():
    for relative in COMPANY_BRANCH_UI_SURFACES:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "onCompanySelected" in text, relative
        assert 'this.filters.branch = ""' in text, relative


def test_report_branch_options_use_retailedge_company_branch_authority():
    shared = (ROOT / "stock_movement_filters.py").read_text(encoding="utf-8")
    assert "get_allowed_operating_branches" in shared
    assert '["Branch", "name", "in", allowed]' in shared

    for relative in COMPANY_BRANCH_BACKENDS:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "get_allowed_operating_branches" in text, relative


def test_branch_performance_revalidates_selected_company_branch_on_backend():
    text = (ROOT / "branch_performance_dashboard.py").read_text(encoding="utf-8")
    assert "validate_operating_branch(" in text
    assert "company=filters.get(\"company\")" in text
    assert "branch=filters.get(\"branch\")" in text


def test_cash_movement_revalidates_requested_branch_on_backend():
    text = (ROOT / "cash_movement.py").read_text(encoding="utf-8")
    block = text.split("def _resolve_branch_scope", 1)[1].split("def _empty_branch_scope", 1)[0]
    assert "validate_operating_branch(" in block
    assert "company=company" in block
    assert "branch=requested_branch" in block
