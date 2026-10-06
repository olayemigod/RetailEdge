from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORTING_ACTIONS = ROOT / "retailedge" / "public" / "js" / "retailedge_reporting_actions.js"
BUSINESS_HUB = ROOT / "retailedge" / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
EXPENSE_REGISTER = ROOT / "retailedge" / "public" / "js" / "expense_register" / "ExpenseRegisterReport.vue"
SALES_REPORTING = ROOT / "retailedge" / "public" / "js" / "sales_reporting" / "SalesReportingReport.vue"
PURCHASE_REPORTING = ROOT / "retailedge" / "public" / "js" / "purchase_reporting" / "PurchaseReportingReport.vue"
STOCK_MOVEMENT = ROOT / "retailedge" / "public" / "js" / "stock_movement_history" / "StockMovementHistory.vue"
PAYMENT_ANALYSIS = ROOT / "retailedge" / "public" / "js" / "payment_settlement_analysis" / "PaymentSettlementAnalysis.vue"


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
    for source in (
        BUSINESS_HUB,
        EXPENSE_REGISTER,
        SALES_REPORTING,
        PURCHASE_REPORTING,
        STOCK_MOVEMENT,
        PAYMENT_ANALYSIS,
    ):
        text = source.read_text()
        assert "EdgeSmartDateRange" in text, source


def test_reporting_smart_dates_still_resolve_to_backend_iso_filter_fields():
    for source in (SALES_REPORTING, PURCHASE_REPORTING, STOCK_MOVEMENT, PAYMENT_ANALYSIS):
        text = source.read_text()
        assert "from_date" in text, source
        assert "to_date" in text, source
        assert "SmartDateResolved" in text or "smartDateResolved" in text, source


def test_exact_transaction_date_semantics_are_not_globally_replaced():
    text = REPORTING_ACTIONS.read_text()
    assert "posting_date" not in text
    assert "due_date" not in text
    assert "reference_date" not in text
