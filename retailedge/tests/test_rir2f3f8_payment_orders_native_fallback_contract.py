from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAVIGATION = ROOT / "edgesuite_ui.py"
SUPPLIER_PAYABLES = ROOT / "public" / "js" / "purchase_reporting" / "PurchaseReportingReport.vue"
PAYMENT_DIALOG = ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePaymentDialog.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _navigation_item(source: str, label: str) -> str:
	marker = f'{{"label": "{label}"'
	start = source.index(marker)
	end = source.index("},", start) + 2
	return source[start:end]


def test_payment_orders_remain_native_but_are_advanced_fallback_only():
	source = _read(NAVIGATION)
	payment_orders = _navigation_item(source, "Payment Orders")
	assert '"target_type": "DocType"' in payment_orders
	assert '"target": "Payment Order"' in payment_orders
	assert '"mode": "native_fallback"' in payment_orders
	assert '"required_roles": tuple(sorted(FINANCE_TRANSFER_ROLES))' in payment_orders


def test_native_fallback_navigation_is_hidden_without_native_desk_access():
	source = _read(NAVIGATION)
	assert 'native_desk_enabled=bool(access_context.get("can_use_native_desk"))' in source
	assert 'if item.get("mode") == "native_fallback" and not native_desk_enabled:' in source
	assert 'resolved.pop("mode", None)' in source


def test_supplier_payables_is_the_everyday_supplier_payment_owner():
	page = _read(SUPPLIER_PAYABLES)
	assert '<SimplePaymentDialog' in page
	assert 'intent="pay-supplier"' in page
	assert ':nativeFallbackEnabled="canUseNativeDesk"' in page
	assert 'reference_name: row.invoice' in page
	assert 'frappe.new_doc("Payment Entry")' in page
	assert 'Payment Order' not in page


def test_guided_supplier_payment_submits_native_payment_entry_not_payment_order():
	dialog = _read(PAYMENT_DIALOG)
	assert 'SUPPLIER_PREVIEW_METHOD = "retailedge.standard_supplier_payment_submit.get_supplier_payment_submit_preview"' in dialog
	assert 'SUPPLIER_SUBMIT_METHOD = "retailedge.standard_supplier_payment_submit.submit_standard_supplier_payment"' in dialog
	assert "Submitting uses the native ERPNext Payment Entry submit flow." in dialog
	assert "Payment Order" not in dialog
