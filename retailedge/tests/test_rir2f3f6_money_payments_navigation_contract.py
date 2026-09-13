from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAVIGATION = ROOT / "edgesuite_ui.py"
PAGE_LOADER = ROOT / "retailedge" / "page" / "payment_management" / "payment_management.js"
HISTORY_PANEL = ROOT / "public" / "js" / "payment_management" / "PaymentHistoryPanel.vue"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _navigation_item(source: str, label: str) -> str:
	marker = f'{{"label": "{label}"'
	start = source.index(marker)
	end = source.index("},", start) + 2
	return source[start:end]


def test_money_payments_routes_to_edgesuite_payment_management():
	source = _read(NAVIGATION)
	payments = _navigation_item(source, "Payments")
	assert '"target_type": "Page"' in payments
	assert '"target": "payment-management"' in payments
	assert '"target": "Payment Entry"' not in payments
	assert '"icon": "wallet"' in payments


def test_reconciliation_and_payment_orders_remain_native_in_f3f6():
	source = _read(NAVIGATION)
	reconciliation = _navigation_item(source, "Payment Reconciliation")
	payment_orders = _navigation_item(source, "Payment Orders")
	assert '"target_type": "DocType"' in reconciliation
	assert '"target": "Payment Reconciliation"' in reconciliation
	assert '"target_type": "DocType"' in payment_orders
	assert '"target": "Payment Order"' in payment_orders


def test_payment_management_route_and_operational_guard_remain_authoritative():
	loader = _read(PAGE_LOADER)
	assert 'const PAGE_ROUTE = "payment-management"' in loader
	assert '.retailedge-payment-management-root' in loader
	assert '"Payment Entry"' in loader
	assert '"Payment Reconciliation"' in loader
	assert "retailedgeInstallEdgesuiteOnlyOperationalGuard" in loader


def test_native_payment_entry_is_only_explicit_permission_gated_history_fallback():
	panel = _read(HISTORY_PANEL)
	assert "canUseNativeDesk" in panel
	assert 'v-if="canUseNativeDesk"' in panel
	assert "Open in ERPNext" in panel
	assert "openPaymentInERPNext" in panel
	assert 'if (!this.canUseNativeDesk || !name) return;' in panel
