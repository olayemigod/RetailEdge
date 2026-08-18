from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_guided_searches_route_through_shared_adapter():
	hooks = (ROOT / "retailedge" / "hooks.py").read_text()
	assert (
		'"retailedge.guided_sales_invoice.search_simple_sales_invoice_options": '
		'"retailedge.guided_link_search.search_simple_sales_invoice_options"'
	) in hooks
	assert (
		'"retailedge.guided_purchase_invoice.search_simple_purchase_invoice_options": '
		'"retailedge.guided_link_search.search_simple_purchase_invoice_options"'
	) in hooks


def test_guided_adapter_uses_shared_edgesuite_ranker_with_rollback_fallback():
	source = (ROOT / "retailedge" / "guided_link_search.py").read_text()
	assert "from edgesuite_ui.search_ranking import rank_search_records" in source
	assert "guided_sales_invoice.search_simple_sales_invoice_options" in source
	assert "guided_purchase_invoice.search_simple_purchase_invoice_options" in source
	assert "CANDIDATE_LIMIT = 100" in source
	assert 'exact_fields=("value",)' in source
	assert 'search_fields=("label", "description")' in source


def test_sales_candidate_search_preserves_business_filters():
	source = (ROOT / "retailedge" / "guided_link_search.py").read_text()
	assert 'filters: dict[str, Any] = {"is_sales_item": 1}' in source
	assert 'filters["customer"] = customer' in source
	assert "guided_sales_invoice._warehouse_search_filters" in source
	assert "guided_sales_invoice._branch_search_filters" in source
	assert 'reference_doctype="Sales Invoice Item"' in source


def test_purchase_candidate_search_preserves_business_filters():
	source = (ROOT / "retailedge" / "guided_link_search.py").read_text()
	assert 'filters: dict[str, Any] = {"is_purchase_item": 1}' in source
	assert 'filters["supplier"] = supplier' in source
	assert "guided_purchase_invoice._warehouse_search_filters" in source
	assert "guided_purchase_invoice._branch_search_filters" in source
	assert 'reference_doctype="Purchase Invoice Item"' in source


def test_existing_guided_ui_still_uses_edgesuite_link_fields():
	sales = (
		ROOT
		/ "retailedge"
		/ "public"
		/ "js"
		/ "retailedge_business_hub"
		/ "SimpleSalesInvoiceDialog.vue"
	).read_text()
	purchase = (
		ROOT
		/ "retailedge"
		/ "public"
		/ "js"
		/ "retailedge_business_hub"
		/ "SimplePurchaseInvoiceDialog.vue"
	).read_text()
	assert "<EdgeLinkField" in sales
	assert "<EdgeLinkField" in purchase
	assert "search_simple_sales_invoice_options" in sales
	assert "search_simple_purchase_invoice_options" in purchase
