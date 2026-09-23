from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "retailedge"
PROVIDER = APP / "financial_dashboard.py"
OWNER_UI = APP / "public/js/owner_dashboard/OwnerDashboard.vue"
NAV = APP / "edgesuite_ui.py"
FILES = APP / "dashboard_files.py"
PAGE_JS = APP / "retailedge/page/owner_dashboard/owner_dashboard.js"
PAGE_JSON = APP / "retailedge/page/owner_dashboard/owner_dashboard.json"


def test_financial_dashboard_keeps_owner_route_and_capability_key():
    provider = PROVIDER.read_text()
    ui = OWNER_UI.read_text()
    assert 'DASHBOARD_KEY = "owner-dashboard"' in provider
    assert 'const DASHBOARD_KEY = "owner-dashboard"' in ui
    assert 'activeRoute="/app/owner-dashboard"' in ui
    assert '"name": "owner-dashboard"' in PAGE_JSON.read_text()
    assert '"page_name": "owner-dashboard"' in PAGE_JSON.read_text()
    assert "Financial Dashboard" in PAGE_JS.read_text()
    assert '"title": "Financial Dashboard"' in PAGE_JSON.read_text()


def test_financial_dashboard_uses_shared_signature_component_and_single_smart_date():
    ui = OWNER_UI.read_text()
    assert "EdgeFinancialDashboard" in ui
    assert "EdgeSmartDateRange" not in ui
    assert "From Date" not in ui
    assert "To Date" not in ui
    assert '@date-resolved="onSmartDateResolved"' in ui


def test_provider_uses_existing_financial_authorities_and_schema_v1():
    provider = PROVIDER.read_text()
    for expected in (
        "SCHEMA_VERSION = 1",
        "get_sales_by_item_export",
        "get_sales_invoice_register",
        "get_payment_settlement_analysis_export",
        "get_expense_register",
        "get_customer_receivables",
        "get_supplier_payables",
        "get_stock_position",
        "get_profitability_summary",
        "_get_liquid_position",
        "has_unrestricted_report_scope",
    ):
        assert expected in provider


def test_provider_does_not_relabel_tax_inclusive_invoiced_total_as_net_sales():
    provider = PROVIDER.read_text()
    assert '_summary_value(sales, "Net Sales")' in provider
    assert 'net_sales_basis' in provider
    assert "base_net_amount" in provider
    assert '_summary_value(invoices, "Net Invoiced")' in provider
    assert "Average Sales Invoice Value" in provider


def test_payment_entry_receipts_are_explicitly_partial_until_full_settlement_coverage():
    provider = PROVIDER.read_text()
    assert "Customer Receipts — Payment Entries" in provider
    assert '"customer_receipts_coverage": "Payment Entry customer Receive payments only;' in provider
    assert '"invoice_cohort_collection": "withheld until complete allocation/credit/write-off coverage is accepted"' in provider
    assert '"availability": "unavailable"' in provider
    assert "POS settlements, credits, write-offs and reversals" in provider


def test_current_balances_do_not_inherit_period_dates():
    provider = PROVIDER.read_text()
    assert 'current_filters = {"company": company, "branch": branch}' in provider
    assert 'if basis == "current":' in provider
    assert 'clean.pop("from_date", None)' in provider
    assert 'clean.pop("to_date", None)' in provider


def test_restricted_values_are_removed_from_metric_payload():
    provider = PROVIDER.read_text()
    assert '"value": value if availability in {"available", "partial"} else None' in provider
    assert '"availability": "restricted"' in provider
    assert "Stock valuation is hidden by the current cost-visibility policy." in provider


def test_financial_actions_use_fresh_destination_handoff_and_request_identity_guard():
    ui = OWNER_UI.read_text()
    for expected in (
        "window.__retailedgeBusinessHubRouteHandoff",
        "retailedge_business_hub_handoff: 1",
        "const requestId = ++this.requestId",
        "if (requestId !== this.requestId) return;",
        "responseContext.company",
        "responseContext.branch",
        "responseContext.from_date",
        "responseContext.to_date",
    ):
        assert expected in ui


def test_dashboard_export_and_navigation_are_switched_to_financial_dashboard():
    files = FILES.read_text()
    nav = NAV.read_text()
    assert "build_financial_dashboard_export_dataset" in files
    assert '"owner-dashboard": lambda filters, _all_filtered: build_financial_dashboard_export_dataset(filters)' in files
    assert '{"label": "Financial Dashboard", "target_type": "Page", "target": "owner-dashboard"' in nav


def test_financial_dashboard_contains_no_accounting_mutation():
    provider = PROVIDER.read_text()
    for forbidden in (
        ".save(",
        ".submit(",
        ".cancel(",
        "db.set_value",
        "frappe.delete_doc",
        "make_gl_entries",
    ):
        assert forbidden not in provider
