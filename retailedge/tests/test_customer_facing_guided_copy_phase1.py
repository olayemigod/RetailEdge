from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDED_ROOT = ROOT / "public" / "js" / "retailedge_business_hub"
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


def test_action_centre_copy_is_business_facing_and_permission_truth_remains_explicit():
	source = ACTION_CENTER.read_text(encoding="utf-8")
	assert "Prioritised business exceptions with separate follow-up tracking." in source
	assert "Follow-up actions do not resolve accounting, stock or workflow exceptions." in source
	assert "existing permissions, approvals, submission rules and accounting controls remain authoritative" in source
	assert "Prioritised issues from existing RetailEdge and ERPNext controls" not in source
	assert "RetailEdge does not resolve accounting" not in source
	assert "RetailEdge could not update this follow-up record." not in source
	assert 'product="RetailEdge"' in source
