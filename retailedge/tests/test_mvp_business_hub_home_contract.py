from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "business_hub_home.py"
FRONTEND = ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"


def test_business_hub_home_uses_existing_reporting_authorities():
	source = BACKEND.read_text()
	assert "get_owner_dashboard_data" in source
	assert "get_bank_exception_summary" in source
	assert "get_cash_shift_verification" in source
	assert "get_operational_branch_scope" in source
	assert "validate_operating_branch" in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit" not in source


def test_business_hub_home_exposes_operational_command_centre_sections():
	source = FRONTEND.read_text()
	assert "retailedge.business_hub_home.get_business_hub_home_snapshot" in source
	for label in ("Understand", "Act", "Operate", "Respond"):
		assert f">{label}<" in source
	assert "Five connected experiences" not in source
	assert "homeSnapshot.cards" in source
	assert "homeSnapshot.indices" in source
	for index_key in ("sales", "cash", "stock", "expenses", "receivables", "payables", "branch", "banking"):
		assert f'key="{index_key}"' in source or index_key in source
	assert "homeSnapshot.attention" in source
	assert "refreshHomeSnapshot" in source
	assert "EdgeSmartDateRange" in source
	assert "homePeriodPreset" in source
	assert "homeSmartDate" in source


def test_business_hub_period_filter_is_fuzzy_bounded_and_server_resolved():
	backend = BACKEND.read_text()
	frontend = FRONTEND.read_text()

	for preset in ("Today", "Yesterday", "This Week", "This Month", "Last 7 Days", "Last 30 Days", "Year to Date", "Last Month"):
		assert preset in frontend or preset in backend

	for contract in (
		"EdgeSmartDateRange",
		'placeholder="e.g. last 30 days, YTD, this month"',
		'dateOrder="DMY"',
		'@resolved="handleHomeDateResolved"',
		"homeSmartDate",
		"from_date: resolvedRange?.from_date",
		"to_date: resolvedRange?.to_date",
		"formatDisplayDate",
	):
		assert contract in frontend

	for contract in (
		"MAX_CUSTOM_PERIOD_DAYS = 366",
		"def _custom_range_from_text",
		"def _assert_bounded_period",
		'"ytd": "Year to Date"',
		'"mtd": "This Month"',
		'r"(?:last|past)\\s+(\\d{1,3})\\s+days?"',
		"Both From Date and To Date are required",
		"From Date cannot be after To Date.",
		'"preset": "Custom Period"',
	):
		assert contract in backend

	assert "date_preset" in frontend
	assert "def _resolve_period(" in backend
	assert '"from_date": period["from_date"]' in backend
	assert '"to_date": period["to_date"]' in backend


def test_business_hub_compacts_large_values_and_preserves_exact_value_tooltips():
	frontend = FRONTEND.read_text()

	for contract in (
		"compactNumber(value",
		'notation: "compact"',
		'{ value: 1e9, suffix: "B" }',
		'{ value: 1e6, suffix: "M" }',
		'{ value: 1e3, suffix: "K" }',
		'formatHomeValue(card, { compact = true } = {})',
		':title="formatHomeValue(card, { compact: false })"',
		':title="formatHomeValue(index.headline, { compact: false })"',
		':title="formatHomeValue(index.signal, { compact: false })"',
		':title="formatHomeValue(item, { compact: false })"',
		"repeat(auto-fit, minmax(13.5rem, 1fr))",
		"text-overflow: ellipsis;",
		"white-space: nowrap;",
	):
		assert contract in frontend


def test_business_hub_home_never_falls_back_to_company_wide_data_for_restricted_blank_scope():
	source = BACKEND.read_text()
	assert "if len(allowed) == 1:" in source
	assert "branch = allowed[0]" in source
	assert "_unavailable_scope_snapshot" in source
	assert "Choose a Branch to load scoped business signals." in source
	assert '"cards": []' in source
	assert '"attention": []' in source


def test_business_hub_respects_retailedge_global_manager_company_access_contract():
	source = BACKEND.read_text()
	assert "user_has_global_branch_access" in source
	assert 'or frappe.has_permission("Company", "read", doc=company)' in source
	assert "get_operational_branch_scope" in source


def test_business_hub_optional_sections_do_not_leak_caught_frappe_messages():
	source = BACKEND.read_text()
	assert 'previous_messages = list(getattr(frappe.local, "message_log", []) or [])' in source
	assert "finally:" in source
	assert "frappe.local.message_log = previous_messages" in source


def test_business_hub_keeps_existing_guided_entry_ownership():
	source = FRONTEND.read_text()
	for token in (
		"SimpleSalesInvoiceDialog",
		"SimplePaymentDialog",
		"SimpleCashDepositDialog",
		"SimpleCashTransferDialog",
		"SimplePurchaseInvoiceDialog",
		"SimpleCashierExpenseDialog",
		"SimpleStockTransferDialog",
		"SimpleStockAdjustmentDialog",
	):
		assert token in source
