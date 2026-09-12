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
