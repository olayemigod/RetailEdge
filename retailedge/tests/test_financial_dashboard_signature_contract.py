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
    assert "base_net_total" in provider
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


def test_business_hub_and_financial_dashboard_share_tax_exclusive_net_sales_definition():
    sales = APP / "sales_reporting.py"
    owner = APP / "owner_dashboard.py"
    hub = APP / "business_hub_home.py"
    visuals = APP / "business_hub_visuals.py"

    sales_source = sales.read_text()
    assert '{"SUM": "base_net_total", "as": "net_total"}' in sales_source
    assert '{"SUM": "base_grand_total", "as": "grand_total"}' not in sales_source.split("def get_sales_visual_aggregates", 1)[1].split("@frappe.whitelist()", 1)[0]
    assert '"label": _("Net Sales")' in sales_source
    assert '"label": _("Net Invoiced")' in sales_source

    assert '("sales", "Net Sales", "Sales")' in owner.read_text()
    assert '("sales", "Net Sales", _("Sales"))' in hub.read_text()
    assert "Tax-exclusive Net Sales" in visuals.read_text()


def test_current_cash_balance_does_not_false_drill_into_period_cash_movement():
    provider = PROVIDER.read_text()
    cash_section = provider.split('"cash_bank"', 1)[1].split('"stock_value"', 1)[0]
    assert "action={}" in cash_section
    assert '_action("cash-movement", current_filters' not in cash_section
    assert "Use the supporting Cash Movement report for period inflows and outflows." in cash_section


def test_financial_dashboard_listens_to_both_retailedge_context_events():
    ui = OWNER_UI.read_text()
    assert 'document.addEventListener("edgesuite-context-changed", this.handleContextChanged);' in ui
    assert 'document.addEventListener("retailedge-operating-context-changed", this.handleContextChanged);' in ui
    assert 'document.removeEventListener("retailedge-operating-context-changed", this.handleContextChanged);' in ui


def test_financial_dashboard_reuses_authoritative_operating_context():
    provider = PROVIDER.read_text()
    assert "from retailedge.operating_context import get_effective_operating_context" in provider
    context_fn = provider.split("def get_financial_dashboard_context()", 1)[1].split("@frappe.whitelist()", 1)[0]
    assert "get_effective_operating_context()" in context_fn
    assert 'get_user_default("RetailEdge Branch")' not in context_fn
    assert 'get_user_default("Branch")' not in context_fn


def test_financial_dashboard_has_governed_comparison_preferences_and_previous_period_contract():
    provider = PROVIDER.read_text()
    ui = OWNER_UI.read_text()
    for expected in (
        'COMPARISON_MODES = {"Previous Period", "Off"}',
        'COMPOSITION_DIMENSIONS = {"Item Group", "Brand", "Branch"}',
        "def _financial_dashboard_preferences()",
        "def _attach_period_comparisons(",
        "def _period_comparison(",
        '"label": _("No comparable baseline")',
        '"comparison_mode": comparison_mode',
        '"comparison_modes": ["Previous Period", "Off"]',
    ):
        assert expected in provider
    assert '<template #comparison>' in ui
    assert 'label="Compare"' in ui
    assert 'onComparisonChanged()' in ui
    assert 'responseContext.comparison_mode' in ui


def test_financial_dashboard_comparison_only_publishes_matching_safe_period_metrics():
    provider = PROVIDER.read_text()
    comparison = provider.split("def _attach_period_comparisons(", 1)[1].split("def _period_comparison_value(", 1)[0]
    assert 'metric = by_id.get("net_sales")' in comparison
    assert "previous_sales" in comparison
    assert "get_sales_visual_aggregates(previous_filters)" in provider
    assert "previous_expenses" not in comparison
    assert "customer_receipts_payment_entries" not in comparison
    assert "sales_margin_contribution" not in comparison


def test_financial_dashboard_reuses_tax_exclusive_sales_visual_authority_for_trends_and_branch_composition():
    provider = PROVIDER.read_text()
    assert "get_sales_visual_aggregates" in provider
    assert "def _build_trends(" in provider
    assert "Daily tax-exclusive Net Sales using the same authority as the headline." in provider
    assert 'dimension == "Branch"' in provider
    assert 'fieldname = "brand" if dimension == "Brand" else "item_group"' in provider


def test_financial_dashboard_optional_sections_are_settings_only_not_permission_grants():
    provider = PROVIDER.read_text()
    assert 'preferences["show_collection"]' in provider
    assert 'preferences["show_financial_health"]' in provider
    assert 'preferences["show_outstanding"]' in provider
    assert "require_dashboard_action" in provider
    assert "has_unrestricted_report_scope" in provider


def test_previous_period_comparison_avoids_duplicate_wide_expense_scan():
    provider = PROVIDER.read_text()
    previous_block = provider.split("if comparison_mode == \"Previous Period\":", 1)[1].split("summary = _build_summary", 1)[0]
    assert "get_sales_visual_aggregates(previous_filters)" in previous_block
    assert "get_expense_register" not in previous_block
    assert "get_sales_by_item_export(previous_filters)" not in previous_block


def test_financial_dashboard_never_surfaces_raw_server_tracebacks():
    ui = OWNER_UI.read_text()
    assert "window.retailedge?.userErrorMessage?.(error, fallback)" in ui
    assert "error?.exc" not in ui
    assert "error?.exception" not in ui


def test_financial_dashboard_exposes_source_scan_evidence_without_new_silent_limits():
    provider = PROVIDER.read_text()
    assert "def _source_scan_metadata(" in provider
    assert '"source_scans": _source_scan_metadata({' in provider
    assert 'payload.get("scan")' in provider
    assert "MAX_FINANCIAL_DASHBOARD_ROWS" not in provider


def test_financial_dashboard_headline_sales_uses_bounded_visual_aggregate_not_item_detail_scan():
    provider = PROVIDER.read_text()
    current_block = provider.split("sales_visual = _safe_payload(", 1)[1].split("invoices = _safe_payload(", 1)[0]
    assert "get_sales_visual_aggregates(period_filters)" in current_block
    assert "sales = _sales_summary_from_visual(sales_visual)" in current_block
    assert 'if composition_dimension in {"Item Group", "Brand"}:' in current_block
    assert "get_sales_by_item_export(period_filters)" in current_block
    assert "def _sales_summary_from_visual(" in provider
    assert '"net_sales_basis": "submitted Sales Invoice base_net_total after returns;' in provider


def test_financial_dashboard_exposes_permitted_composition_views_without_changing_permissions():
    provider = PROVIDER.read_text()
    ui = OWNER_UI.read_text()
    assert '"composition_options": ["Item Group", "Brand", "Branch"]' in provider
    assert "Unsupported Financial Dashboard composition dimension." in provider
    assert '<template #contextFilters>' in ui
    assert 'label="Composition"' in ui
    assert "compositionOptions" in ui
    assert "onCompositionChanged()" in ui
    assert "responseContext.composition_dimension" in ui


def test_sales_visual_aggregate_rejects_silent_truncation_and_reports_scan_limits():
    sales = (APP / "sales_reporting.py").read_text()
    visual = sales.split("def get_sales_visual_aggregates", 1)[1].split("@frappe.whitelist()", 1)[0]
    for expected in (
        "MAX_VISUAL_TREND_ROWS = 800",
        "MAX_VISUAL_BRANCH_ROWS = 500",
        "limit_page_length=MAX_VISUAL_TREND_ROWS + 1",
        "len(trend_rows) > MAX_VISUAL_TREND_ROWS",
        "Sales trend is too large to load safely.",
        "limit_page_length=MAX_VISUAL_BRANCH_ROWS + 1",
        "len(mix_rows) > MAX_VISUAL_BRANCH_ROWS",
        "Branch sales mix is too large to load safely.",
        '"trend_limit": MAX_VISUAL_TREND_ROWS',
        '"branch_limit": MAX_VISUAL_BRANCH_ROWS',
    ):
        assert expected in sales
    assert "limit_page_length=800" not in visual
    assert "limit_page_length=500" not in visual


def test_financial_dashboard_defaults_to_this_month_and_preserves_view_on_context_change():
    ui = OWNER_UI.read_text()
    assert 'syncSmartDateFromFilters(expression = "custom")' in ui
    assert ': (preserveView ? (this.smartDate?.expression || "custom") : "This Month")' in ui
    assert "from_date: this.filters.from_date" in ui
    assert "comparison_mode: this.filters.comparison_mode" in ui
    assert "composition_dimension: this.filters.composition_dimension" in ui
    assert "this.fetchMetadata({ preserveView: true });" in ui


def test_financial_dashboard_claims_business_hub_handoff_before_async_context_work():
    ui = OWNER_UI.read_text()
    fetch = ui.split("async fetchMetadata", 1)[1]
    assert "retailedgeConsumeBusinessHubRouteOptions" in fetch
    assert fetch.index("retailedgeConsumeBusinessHubRouteOptions") < fetch.index("navigationPromise")


def test_net_sales_helper_matches_invoice_level_tax_exclusive_authority():
    provider = PROVIDER.read_text()
    assert "Submitted Sales Invoice base net totals after discounts and returns; tax exclusive." in provider
    assert "Submitted invoice item net amounts after discounts and returns; tax exclusive." not in provider
