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


def test_recurring_billing_native_routes_are_deliberate_fallbacks():
	source = _read(NAVIGATION)
	for label, doctype in (
		("Subscriptions", "Subscription"),
		("Subscription Plans", "Subscription Plan"),
	):
		item = _navigation_item(source, label)
		assert '"target_type": "DocType"' in item
		assert f'"target": "{doctype}"' in item
		assert '"mode": "native_fallback"' in item
		assert '"required_roles"' not in item


def test_recurring_billing_uses_existing_native_desk_and_erpnext_permission_contract():
	source = _read(NAVIGATION)
	assert 'if item.get("mode") == "native_fallback" and not native_desk_enabled:' in source
	assert 'if target_type == "DocType":' in source
	assert '_has_permission_cached(target, "read", permission_cache)' in source


def test_existing_money_operational_ownership_is_unchanged():
	source = _read(NAVIGATION)
	payments = _navigation_item(source, "Payments")
	payment_reconciliation = _navigation_item(source, "Payment Reconciliation")
	bank_transactions = _navigation_item(source, "Bank Transactions")
	statement_import = _navigation_item(source, "Import Bank Statement")
	bank_matching = _navigation_item(source, "Bank Matching")

	assert '"target_type": "Page"' in payments
	assert '"target": "payment-management"' in payments
	assert '"mode": "native_fallback"' in payment_reconciliation
	assert '"target": "Payment Reconciliation"' in payment_reconciliation
	assert '"mode": "native_fallback"' in bank_transactions
	assert '"target": "Bank Transaction"' in bank_transactions
	assert '"target": "RetailEdge Payment Statement Import"' in statement_import
	assert '"target_type": "Page"' in bank_matching
	assert '"target": "bank-matching-reconciliation"' in bank_matching
