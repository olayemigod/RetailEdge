from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORTING_ACTIONS = ROOT / "retailedge" / "public" / "js" / "retailedge_reporting_actions.js"
BUSINESS_HUB = ROOT / "retailedge" / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
EXPENSE_REGISTER = ROOT / "retailedge" / "public" / "js" / "expense_register" / "ExpenseRegisterReport.vue"
SALES_REPORTING = ROOT / "retailedge" / "public" / "js" / "sales_reporting" / "SalesReportingReport.vue"
PURCHASE_REPORTING = ROOT / "retailedge" / "public" / "js" / "purchase_reporting" / "PurchaseReportingReport.vue"
STOCK_MOVEMENT = ROOT / "retailedge" / "public" / "js" / "stock_movement_history" / "StockMovementHistory.vue"
PAYMENT_ANALYSIS = ROOT / "retailedge" / "public" / "js" / "payment_settlement_analysis" / "PaymentSettlementAnalysis.vue"
MONEY_OVERVIEW = ROOT / "retailedge" / "public" / "js" / "money_overview" / "MoneyOverview.vue"
CUSTOMER_SALES_INTELLIGENCE = ROOT / "retailedge" / "public" / "js" / "customer_sales_intelligence" / "CustomerSalesIntelligence.vue"
PAYMENT_HISTORY = ROOT / "retailedge" / "public" / "js" / "payment_management" / "PaymentHistoryPanel.vue"


SMART_DATE_SURFACES = (
    BUSINESS_HUB,
    EXPENSE_REGISTER,
    SALES_REPORTING,
    PURCHASE_REPORTING,
    STOCK_MOVEMENT,
    PAYMENT_ANALYSIS,
    MONEY_OVERVIEW,
    CUSTOMER_SALES_INTELLIGENCE,
    PAYMENT_HISTORY,
)

MIGRATED_NATIVE_RANGE_SURFACES = (
    MONEY_OVERVIEW,
    CUSTOMER_SALES_INTELLIGENCE,
    PAYMENT_HISTORY,
)


def test_retailedge_replaces_shared_smart_date_with_one_reporting_policy():
    text = REPORTING_ACTIONS.read_text()
    assert "installSmartDatePolicy" in text
    assert 'runtime.registerComponent("EdgeSmartDateRange", RetailEdgeSmartDateRange, { replace: true })' in text
    assert "presets: []" in text
    assert "May to June 2026" in text
    assert "last 2 months" in text
    assert "previous 2 months" in text
    assert 'minWidth: "0"' in text
    assert 'width: "100%"' in text
    assert 'maxWidth: "100%"' in text
    assert 'window.addEventListener("edgesuite:report-runtime-ready"' in text


def test_known_reporting_surfaces_use_shared_smart_date_component():
    for source in SMART_DATE_SURFACES:
        text = source.read_text()
        assert "EdgeSmartDateRange" in text, source


def test_migrated_period_filters_no_longer_render_native_from_to_date_inputs():
    for source in MIGRATED_NATIVE_RANGE_SURFACES:
        text = source.read_text()
        assert 'type="date"' not in text, source
        assert 'label="Period"' in text, source
        assert "onSmartDateResolved" in text, source


def test_reporting_smart_dates_still_resolve_to_backend_iso_filter_fields():
    for source in (
        SALES_REPORTING,
        PURCHASE_REPORTING,
        STOCK_MOVEMENT,
        PAYMENT_ANALYSIS,
        MONEY_OVERVIEW,
        CUSTOMER_SALES_INTELLIGENCE,
        PAYMENT_HISTORY,
    ):
        text = source.read_text()
        assert "from_date" in text, source
        assert "to_date" in text, source
        assert "SmartDateResolved" in text or "smartDateResolved" in text, source


def test_migrated_filter_grids_allow_smart_date_to_shrink_without_overlap():
    for source in MIGRATED_NATIVE_RANGE_SURFACES:
        text = source.read_text()
        assert "min-width: 0" in text or "min-width:0" in text, source
        assert "max-width: 100%" in text or "max-width:100%" in text, source


def test_exact_transaction_date_semantics_are_not_globally_replaced():
    text = REPORTING_ACTIONS.read_text()
    assert "posting_date" not in text
    assert "due_date" not in text
    assert "reference_date" not in text
