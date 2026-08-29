from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
HUB_ROOT = APP_ROOT / "public" / "js" / "retailedge_business_hub"


def test_stock_item_quick_create_capability_comes_from_server_context():
	backend = (APP_ROOT / "guided_stock_transfer.py").read_text(encoding="utf-8")
	frontend = (HUB_ROOT / "SimpleStockTransferDialog.vue").read_text(encoding="utf-8")

	assert '"can_create_item": bool(' in backend
	assert 'frappe.has_permission("Item", "create")' in backend
	assert "this.formContext.capabilities?.can_create_item" in frontend
	assert "frappe?.model?.can_create" not in frontend


def test_guided_draft_endpoints_never_bypass_permissions_or_submit_documents():
	for module in (
		"guided_sales_invoice.py",
		"guided_purchase_invoice.py",
		"guided_payment.py",
		"guided_cashier_expense.py",
		"guided_stock_transfer.py",
	):
		source = (APP_ROOT / module).read_text(encoding="utf-8")
		assert "ignore_permissions=True" not in source
		assert ".submit()" not in source
		assert "frappe.db.commit()" not in source


def test_client_cannot_supply_effective_sales_or_buying_price_list():
	sales = (APP_ROOT / "guided_sales_invoice.py").read_text(encoding="utf-8")
	purchase = (APP_ROOT / "guided_purchase_invoice.py").read_text(encoding="utf-8")

	assert 'values.get("selling_price_list")' not in sales
	assert 'values.get("buying_price_list")' not in purchase
	assert 'values.get("price_list")' not in sales
	assert 'values.get("price_list")' not in purchase
	assert "resolve_price_list_context" in sales
	assert "resolve_price_list_context" in purchase
