from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAVIGATION = ROOT / "edgesuite_ui.py"
BANK_WORKSPACE = ROOT / "public" / "js" / "bank_matching_edgesuite_workspace.js"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def _navigation_item(source: str, label: str) -> str:
	marker = f'{{"label": "{label}"'
	start = source.index(marker)
	end = source.index("},", start) + 2
	return source[start:end]


def test_bank_transactions_is_finance_native_fallback():
	source = _read(NAVIGATION)
	item = _navigation_item(source, "Bank Transactions")
	assert '"target_type": "DocType"' in item
	assert '"target": "Bank Transaction"' in item
	assert '"mode": "native_fallback"' in item
	assert '"required_roles": tuple(sorted(FINANCE_TRANSFER_ROLES))' in item


def test_bank_matching_and_statement_import_ownership_are_unchanged():
	source = _read(NAVIGATION)
	bank_matching = _navigation_item(source, "Bank Matching")
	statement_import = _navigation_item(source, "Import Bank Statement")
	assert '"target_type": "Page"' in bank_matching
	assert '"target": "bank-matching-reconciliation"' in bank_matching
	assert '"target_type": "DocType"' in statement_import
	assert '"target": "RetailEdge Payment Statement Import"' in statement_import


def test_bank_workspace_derives_native_desk_access_fail_closed():
	source = _read(BANK_WORKSPACE)
	assert "canUseNativeDesk: false" in source
	assert "retailedgeGetBusinessHubContext" in source
	assert "retailedge.master_experience.get_master_retailedge_business_hub_context" in source
	assert "state.canUseNativeDesk = Boolean" in source
	assert "state.canUseNativeDesk = false" in source


def test_bank_workspace_native_document_links_are_permission_gated():
	source = _read(BANK_WORKSPACE)
	assert "function routeToNativeDocument" in source
	assert "if (!state.canUseNativeDesk) return;" in source
	assert "state.canUseNativeDesk && row.bank_transaction" in source
	assert "state.canUseNativeDesk && row.suggested_document" in source
	assert "state.canUseNativeDesk && doc.bank_transaction" in source
	assert "state.canUseNativeDesk && doc.suggested_document" in source
	assert 'routeToDocument("RetailEdge Bank Transaction Match", state.review.matchName)' in source


def test_bank_matching_operational_reconciliation_remains_retailedge_owned():
	source = _read(BANK_WORKSPACE)
	assert 'method: "retailedge.banking_workspace.get_banking_workspace_rows"' in source
	assert 'method: "retailedge.banking_operations.match_and_reconcile"' in source
	assert "confirm_reconciliation: 1" in source
	assert "ERPNext remains the reconciliation authority." in source
