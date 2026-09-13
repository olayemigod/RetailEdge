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


def test_business_hub_home_exposes_mvp_command_centre_sections():
	source = FRONTEND.read_text()
	assert "retailedge.business_hub_home.get_business_hub_home_snapshot" in source
	assert "Business at a glance" in source
	assert "homeSnapshot.cards" in source
	assert "['stock', 'banking', 'branch', 'cash_shift']" in source
	assert ">Attention<" in source
	assert "refreshHomeSnapshot" in source


def test_business_hub_home_never_falls_back_to_company_wide_data_for_restricted_blank_scope():
	source = BACKEND.read_text()
	assert "if len(allowed) == 1:" in source
	assert "branch = allowed[0]" in source
	assert "_unavailable_scope_snapshot" in source
	assert "Choose a Branch to load scoped business signals." in source
	assert '"cards": []' in source
	assert '"attention": []' in source


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
