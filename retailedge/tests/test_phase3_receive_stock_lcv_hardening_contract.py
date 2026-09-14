from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "professional_purchase_receipt.py"
LANDED = ROOT / "landed_cost_allocation.py"
PURCHASING_UI = ROOT / "public/js/professional_purchasing/ProfessionalPurchasing.vue"


def test_receive_stock_remains_native_erpnext_stock_posting():
	source = RECEIPT.read_text(encoding="utf-8")
	assert "make_purchase_receipt" in source
	assert "validate_guided_branch_warehouse" in source
	assert "receipt.insert()" in source
	assert "receipt.submit()" in source
	assert '"stock_posted_by": "ERPNext Purchase Receipt submit"' in source
	assert "ignore_permissions=True" not in source
	assert 'frappe.new_doc("Stock Ledger Entry")' not in source
	assert 'frappe.new_doc("GL Entry")' not in source


def test_receive_stock_result_exposes_safe_landed_cost_handoff():
	source = RECEIPT.read_text(encoding="utf-8")
	assert '"landed_cost_handoff"' in source
	assert '"source_type": "purchase_receipt"' in source
	assert '"source_name": receipt.name' in source
	assert '"authority": "ERPNext Landed Cost Voucher"' in source


def test_landed_cost_is_v16_34_compatible_and_uses_native_mapper():
	source = LANDED.read_text(encoding="utf-8")
	assert "from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_lcv" in source
	assert "get_accounting_dimensions" in source
	assert "from erpnext.stock.doctype.landed_cost_voucher.landed_cost_voucher import get_lcv_dimension_fields" not in source
	assert "make_lcv(" in source
	assert 'run_method("validate")' in source
	assert "landed_cost_voucher.insert()" in source
	assert "landed_cost_voucher.submit()" in source
	assert "ignore_permissions=True" not in source


def test_purchase_receipt_is_supported_as_landed_cost_source_in_edgesuite():
	backend = LANDED.read_text(encoding="utf-8")
	ui = PURCHASING_UI.read_text(encoding="utf-8")
	assert '"purchase_receipt": PURCHASE_RECEIPT_DOCTYPE' in backend
	assert "Review Landed Cost" in ui
	assert "Prepare Landed Cost Draft" in ui
	assert "Advanced: Prepare in ERPNext" in ui
