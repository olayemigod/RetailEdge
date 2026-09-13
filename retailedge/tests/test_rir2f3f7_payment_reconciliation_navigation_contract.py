from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAVIGATION = ROOT / "edgesuite_ui.py"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _navigation_item(source: str, label: str) -> str:
	marker = f'{{"label": "{label}"'
	start = source.index(marker)
	end = source.index("},", start) + 2
	return source[start:end]


def test_payment_reconciliation_remains_native_advanced_accounting_fallback():
	source = _read(NAVIGATION)
	reconciliation = _navigation_item(source, "Payment Reconciliation")
	assert '"target_type": "DocType"' in reconciliation
	assert '"target": "Payment Reconciliation"' in reconciliation
	assert '"mode": "native_fallback"' in reconciliation
	assert '"required_roles": tuple(sorted(FINANCE_TRANSFER_ROLES))' in reconciliation


def test_navigation_filter_reuses_edgesuite_native_desk_access_context():
	source = _read(NAVIGATION)
	assert 'native_desk_enabled=bool(access_context.get("can_use_native_desk"))' in source
	assert 'native_desk_enabled: bool = True' in source
	assert 'if item.get("mode") == "native_fallback" and not native_desk_enabled:' in source
	assert 'resolved.pop("mode", None)' in source


def test_everyday_payment_and_bank_matching_routes_remain_edgesuite_owned():
	source = _read(NAVIGATION)
	payments = _navigation_item(source, "Payments")
	bank_matching = _navigation_item(source, "Bank Matching")
	assert '"target_type": "Page"' in payments
	assert '"target": "payment-management"' in payments
	assert '"target_type": "Page"' in bank_matching
	assert '"target": "bank-matching-reconciliation"' in bank_matching


def test_payment_orders_remain_unchanged_in_f3f7():
	source = _read(NAVIGATION)
	payment_orders = _navigation_item(source, "Payment Orders")
	assert '"target_type": "DocType"' in payment_orders
	assert '"target": "Payment Order"' in payment_orders
	assert '"mode": "native_fallback"' not in payment_orders
