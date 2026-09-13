from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_remaining_guided_searches_route_through_shared_adapter():
	hooks = (ROOT / "retailedge" / "hooks.py").read_text()
	for source, target in (
		(
			"retailedge.guided_stock_transfer.search_simple_stock_transfer_options",
			"retailedge.guided_link_search_extended.search_simple_stock_transfer_options",
		),
		(
			"retailedge.guided_stock_adjustment.search_simple_stock_adjustment_options",
			"retailedge.guided_link_search_extended.search_simple_stock_adjustment_options",
		),
		(
			"retailedge.guided_cash_transfer.search_simple_cash_transfer_options",
			"retailedge.guided_link_search_extended.search_simple_cash_transfer_options",
		),
		(
			"retailedge.cash_custody.search_cash_deposit_options",
			"retailedge.guided_link_search_extended.search_cash_deposit_options",
		),
	):
		assert f'"{source}": "{target}"' in hooks


def test_extended_adapter_uses_shared_ranker_and_bounded_candidates():
	source = (ROOT / "retailedge" / "guided_link_search_extended.py").read_text()
	assert "from edgesuite_ui.search_ranking import rank_search_records" in source
	assert "CANDIDATE_LIMIT = 100" in source
	assert 'exact_fields=("value",)' in source
	assert 'search_fields=("label", "description")' in source
	assert "if _shared_ranker() is None:" in source


def test_non_empty_search_anchors_permission_scoped_provider_queries():
	source = (ROOT / "retailedge" / "guided_link_search_extended.py").read_text()
	assert "_query_anchors" in source
	assert "MAX_ANCHORS = 4" in source
	assert "_collect_candidates" in source
	assert "remaining = CANDIDATE_LIMIT - len(rows)" in source
	assert "txt=txt" in source or "txt=query" in source
	assert 'search_link(\n\t\t\t\t"Item",\n\t\t\t\ttxt,' in source


def test_stock_search_preserves_erpnext_and_branch_filters():
	source = (ROOT / "retailedge" / "guided_link_search_extended.py").read_text()
	assert 'filters={"is_stock_item": 1, "disabled": 0}' in source
	assert "guided_stock_transfer._warehouse_search_filters" in source
	assert "guided_stock_transfer._branch_search_filters" in source
	assert "guided_stock_adjustment._warehouse_search_filters" in source
	assert "guided_stock_adjustment._branch_search_filters" in source
	assert 'reference_doctype="Stock Entry Detail"' in source
	assert 'reference_doctype="Stock Reconciliation Item"' in source


def test_cash_search_preserves_account_and_bank_account_providers():
	source = (ROOT / "retailedge" / "guided_link_search_extended.py").read_text()
	assert "guided_cash_transfer._search_bank_cash_accounts" in source
	assert "guided_cash_transfer._search_branches" in source
	assert "cash_custody.search_retailedge_bank_accounts" in source
	assert 'fieldname not in {"to_bank_account", "to_account"}' in source


def test_existing_guided_dialogs_remain_edgesuite_link_consumers():
	business_hub = ROOT / "retailedge" / "public" / "js" / "retailedge_business_hub"
	for filename in (
		"SimpleStockTransferDialog.vue",
		"SimpleCashDepositDialog.vue",
		"SimpleCashTransferDialog.vue",
	):
		source = (business_hub / filename).read_text()
		assert "<EdgeLinkField" in source
