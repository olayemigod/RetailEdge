from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDED_ROOT = ROOT / "public" / "js" / "retailedge_business_hub"
BUSINESS_HUB = GUIDED_ROOT / "RetailEdgeBusinessHub.vue"
ACTION_CENTER = ROOT / "public" / "js" / "action_center" / "ActionCenter.vue"


def _source(name: str) -> str:
	return (GUIDED_ROOT / name).read_text(encoding="utf-8")


def test_guided_sales_invoice_uses_stock_location_customer_language():
	source = _source("SimpleSalesInvoiceDialog.vue")
	assert 'label="Stock Location"' in source
	assert 'placeholder="Search stock location"' in source
	assert "Unable to use the selected Stock Location." in source
	assert 'label="Warehouse"' not in source
	assert 'placeholder="Search warehouse"' not in source
	assert "RetailEdge falls back" not in source
	assert "Unable to prepare Simple Sales Invoice." not in source


def test_guided_purchase_invoice_uses_receiving_stock_location_language():
	source = _source("SimplePurchaseInvoiceDialog.vue")
	assert 'label="Receiving Stock Location"' in source
	assert 'placeholder="Search receiving stock location"' in source
	assert "Unable to use the selected Receiving Stock Location." in source
	assert 'label="Warehouse"' not in source
	assert 'placeholder="Search warehouse"' not in source
	assert "Unable to prepare Simple Purchase Invoice." not in source


def test_guided_payment_uses_business_facing_name_without_simple_implementation_wording():
	source = _source("SimplePaymentDialog.vue")
	assert ":title=\"formContext.title || 'Payment'\"" in source
	assert "Create a Payment Entry draft using ERPNext payment and allocation controls." in source
	assert "Unable to prepare Payment Entry." in source
	assert "Simple Payment" not in source


def test_guided_cashier_expense_keeps_internal_doctype_but_not_visible_product_prefix():
	source = _source("SimpleCashierExpenseDialog.vue")
	assert "Record a controlled cashier expense for the current operating context." in source
	assert "The expense account, cost centre and cash account are resolved" in source
	assert 'this.$emit("open-native", "RetailEdge Cashier Expense")' in source
	assert "controlled RetailEdge cashier expense" not in source
	assert "RetailEdge will resolve the expense account" not in source


def test_guided_stock_transfer_preserves_internal_warehouse_keys_but_not_visible_warehouse_labels():
	source = _source("SimpleStockTransferDialog.vue")
	assert 'label="Source Stock Location"' in source
	assert 'label="Destination Stock Location"' in source
	assert 'source_warehouse' in source
	assert 'target_warehouse' in source
	assert 'label="Source Warehouse"' not in source
	assert 'label="Target Warehouse"' not in source
	assert "Source and Target Warehouse must be different." not in source


def test_guided_stock_adjustment_uses_stock_location_language():
	source = _source("SimpleStockAdjustmentDialog.vue")
	assert 'label="Stock Location"' in source
	assert 'placeholder="Search permitted stock location"' in source
	assert "Company and Stock Location are required." in source
	assert 'label="Warehouse"' not in source
	assert "Company and Warehouse are required." not in source


def test_guided_cash_transfer_hides_payment_entry_implementation_detail_from_context():
	source = _source("SimpleCashTransferDialog.vue")
	assert "Move funds safely between permitted Cash and Bank accounts." in source
	assert "<span>Transfer Type</span><strong>Internal Transfer</strong>" in source
	assert 'this.formContext.full_form_doctype || "Payment Entry"' in source
	assert "<span>Document</span><strong>Payment Entry · Internal Transfer</strong>" not in source


def test_business_hub_keeps_product_identity_but_removes_redundant_operational_prefixes():
	source = BUSINESS_HUB.read_text(encoding="utf-8")
	assert 'title="RetailEdge"' in source
	assert 'title="Business Hub"' in source
	assert 'message="Loading your permitted business tools..."' in source
	assert "Five connected experiences" in source
	assert "Guided entry" in source
	assert "RetailEdge Business Hub" not in source
	assert "Loading your permitted RetailEdge tools" not in source
	assert "Five connected RetailEdge experiences" not in source
	assert "Product switching suspended" not in source
	assert '"RetailEdge entry"' not in source


def test_action_centre_copy_is_business_facing_and_permission_truth_remains_explicit():
	source = ACTION_CENTER.read_text(encoding="utf-8")
	assert "Prioritised business exceptions with separate follow-up tracking." in source
	assert "Follow-up actions do not resolve accounting, stock or workflow exceptions." in source
	assert "existing permissions, approvals, submission rules and accounting controls remain authoritative" in source
	assert "Prioritised issues from existing RetailEdge and ERPNext controls" not in source
	assert "RetailEdge does not resolve accounting" not in source
	assert "RetailEdge could not update this follow-up record." not in source
	assert 'product="RetailEdge"' in source
