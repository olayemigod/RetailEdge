from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
	return (ROOT / relative).read_text(encoding="utf-8")


def _json(relative: str) -> dict:
	return json.loads(_read(relative))


def test_settings_use_vertical_navigation_and_expose_price_list_governance():
	vue = _read("public/js/retail_settings/RetailSettings.vue")
	settings = _json("retailedge/doctype/retailedge_settings/retailedge_settings.json")
	fields = {row["fieldname"]: row for row in settings["fields"]}

	assert 'class="settings-nav-shell"' in vue
	assert "grid-template-columns:minmax(13rem, 15rem) minmax(0, 1fr)" in vue
	assert ".settings-tabs { display:grid;" in vue
	assert "overflow-x:auto" not in vue
	for fieldname in (
		"enable_price_list_governance",
		"selling_price_list_policy",
		"buying_price_list_policy",
		"allow_price_list_switch",
	):
		assert fieldname in fields
	assert fields["enable_price_list_governance"]["default"] == "1"
	assert fields["selling_price_list_policy"]["default"] == "Party > POS > Branch > Assigned Choice"
	assert fields["buying_price_list_policy"]["default"] == "Party > Branch > Assigned Choice"


def test_branch_setup_and_assignments_own_their_pricing_governance_data():
	profile = _json("retailedge/doctype/retailedge_branch_profile/retailedge_branch_profile.json")
	assignment = _json("retailedge/doctype/retailedge_branch_assignment/retailedge_branch_assignment.json")
	child = _json(
		"retailedge/doctype/retailedge_branch_assignment_price_list/retailedge_branch_assignment_price_list.json"
	)
	profile_fields = {row["fieldname"]: row for row in profile["fields"]}
	assignment_fields = {row["fieldname"]: row for row in assignment["fields"]}

	assert profile_fields["default_selling_price_list"]["options"] == "Price List"
	assert profile_fields["default_buying_price_list"]["options"] == "Price List"
	assert assignment_fields["price_lists"]["options"] == "RetailEdge Branch Assignment Price List"
	assert child["istable"] == 1
	assert child["fields"][0]["options"] == "Price List"


def test_ranked_guided_search_preserves_governed_price_list_lookup():
	search = (ROOT / "guided_link_search.py").read_text()

	assert 'fieldname == "price_list"' in search
	assert "guided_sales_invoice.search_simple_sales_invoice_options(" in search
	assert "guided_purchase_invoice.search_simple_purchase_invoice_options(" in search
	assert "CANDIDATE_LIMIT" in search


def test_branch_assignment_price_lists_participate_in_price_list_permission_scope():
	assignment = _read("branch_assignment.py")
	workspace = _read("pricing_promotions_workspace.py")

	assert "def get_raw_assignment_price_lists(" in assignment
	assert "get_raw_assignment_price_lists" in workspace
	assert '"branch_assignment": []' in workspace
	assert 'sources["branch_assignment"].append(name)' in workspace
	assert 'user=doc.user' not in assignment[assignment.index("def _validate_assignment_price_lists"):assignment.index("def _validate_assignment_price_list_immutability")]


def test_selling_surfaces_can_show_one_assigned_alternative_price_list():
	simple = _read("public/js/retailedge_business_hub/SimpleSalesInvoiceDialog.vue")
	quotation = _read("public/js/professional_selling/ProfessionalQuotationDialog.vue")
	order = _read("public/js/professional_selling/ProfessionalSalesOrderDialog.vue")
	invoice = _read("public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue")

	assert "available_price_lists || []).length);" in simple
	for component in (quotation, order, invoice):
		assert "this.availablePriceLists.length);" in component
		assert "this.availablePriceLists.length > 1" not in component


def test_governed_resolver_and_edgesuite_surfaces_revalidate_price_list_choice():
	pricing = _read("guided_pricing.py")
	sales = _read("guided_sales_invoice.py")
	purchase = _read("guided_purchase_invoice.py")
	sales_ui = _read("public/js/retailedge_business_hub/SimpleSalesInvoiceDialog.vue")
	purchase_ui = _read("public/js/retailedge_business_hub/SimplePurchaseInvoiceDialog.vue")
	assign_ui = _read("public/js/branch_assignments/BranchAssignments.vue")
	professional_quotation = _read("public/js/professional_selling/ProfessionalQuotationDialog.vue")
	professional_order = _read("public/js/professional_selling/ProfessionalSalesOrderDialog.vue")
	professional_invoice = _read("public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue")
	professional_purchase_order = _read("public/js/professional_purchasing/ProfessionalPurchaseOrderDialog.vue")

	for expected in (
		"get_assignment_price_lists",
		"get_exact_branch_profile",
		"requested_price_list not in available_price_lists",
		'"Party > POS > Branch > Assigned Choice"',
		'"Party > Branch > Assigned Choice"',
	):
		assert expected in pricing
	assert 'fieldname == "price_list"' in sales
	assert 'fieldname == "price_list"' in purchase
	assert "requested_price_list=values.get(\"price_list\") or \"\"" in sales
	assert "requested_price_list=values.get(\"price_list\") or \"\"" in purchase
	for component in (
		sales_ui,
		purchase_ui,
		professional_quotation,
		professional_order,
		professional_invoice,
		professional_purchase_order,
	):
		assert 'label="Price List"' in component
		assert "searchPriceList" in component
		assert "setPriceList" in component
		assert "this.values.price_list" in component
	assert "Allowed Price Lists" in assign_ui
	assert "searchAssignPriceList" in assign_ui
	assert "searchTransferPriceList" in assign_ui
	assert "Edit Price Lists" in assign_ui
	assert "UPDATE_PRICE_LISTS_METHOD" in assign_ui
