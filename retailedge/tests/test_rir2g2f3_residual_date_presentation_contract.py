from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
	"cash_flow": ROOT / "public/js/cash_flow_outlook/CashFlowOutlookReport.vue",
	"receivables": ROOT / "public/js/customer_receivables/CustomerReceivablesReport.vue",
	"expense_dashboard": ROOT / "public/js/expense_dashboard/ExpenseDashboard.vue",
	"rfq_preview": ROOT / "public/js/professional_purchasing/ProfessionalRfqPreviewOverlay.vue",
	"sales_invoice": ROOT / "public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue",
	"purchase_reporting": ROOT / "public/js/purchase_reporting/PurchaseReportingReport.vue",
	"simple_payment": ROOT / "public/js/retailedge_business_hub/SimplePaymentDialog.vue",
	"stock_integrity": ROOT / "public/js/stock_accounting_integrity/StockAccountingIntegrityReport.vue",
}


def _source(key: str) -> str:
	return FILES[key].read_text(encoding="utf-8")


def test_all_g2f3_components_use_frappe_user_date_formatting():
	for key in FILES:
		assert "frappe.datetime.str_to_user" in _source(key), key


def test_report_metadata_dates_are_formatted():
	assert "formatDate(asOfDate" in _source("cash_flow")
	assert "formatDate(currentBalanceDate" in _source("receivables")
	assert "formatDate(payablesAgeingDate || filters.as_of_date" in _source("purchase_reporting")
	assert "formatDate(scope.from_date)" in _source("stock_integrity")
	assert "formatDate(scope.as_on_date)" in _source("stock_integrity")


def test_expense_overview_formats_period_and_recent_expense_dates():
	source = _source("expense_dashboard")
	for contract in (
		"formatDate(periodContext.mtd?.from_date)",
		"formatDate(periodContext.mtd?.to_date)",
		"formatDate(periodContext.ytd?.from_date)",
		"formatDate(periodContext.ytd?.to_date)",
		"formatDate(row.expense_date)",
		"this.formatDate(anchor)",
	):
		assert contract in source


def test_operational_dialog_dates_are_formatted_without_changing_inputs():
	rfq = _source("rfq_preview")
	assert "formatDate(row.schedule_date)" in rfq
	sales = _source("sales_invoice")
	assert "formatDate(loyaltyStatus.from_date" in sales
	assert "formatDate(loyaltyStatus.to_date" in sales
	assert 'v-model="values.posting_date"' in sales
	assert 'type="date"' in sales
	payment = _source("simple_payment")
	assert "formatDate(customerReview.posting_date)" in payment
	assert "formatDate(supplierReview.posting_date)" in payment
	assert 'v-model="values.posting_date"' in payment


def test_raw_confirmed_leaks_are_removed():
	assert '{{ row.schedule_date || \'—\' }}' not in _source("rfq_preview")
	assert "{{ customerReview.posting_date }}" not in _source("simple_payment")
	assert "{{ supplierReview.posting_date }}" not in _source("simple_payment")
	assert "{{ row.expense_date }}" not in _source("expense_dashboard")
