from __future__ import annotations

from pathlib import Path

from retailedge.master_experience import (
	NAVIGATION_PRESENTATION_GROUPS,
	_reclassify_navigation_for_task_frequency,
)
from retailedge.report_center import REPORT_GROUPS
from retailedge.workspace_home import HOME_SECTIONS, HOME_WORKSPACE_ITEMS


ROOT = Path(__file__).resolve().parents[1]


def _group(key: str, *items: dict) -> dict:
	return {"key": key, "label": key, "icon": "x", "items": list(items)}


def _item(label: str, target_type: str, target: str) -> dict:
	return {"label": label, "target_type": target_type, "target": target, "icon": "x"}


def test_final_navigation_separates_operations_reports_reviews_and_setup():
	groups = [
		_group("home", _item("Business Hub", "Page", "retailedge-business-hub")),
		_group(
			"sell",
			_item("Start POS", "URL", "/pos"),
			_item("Sales Invoices", "DocType", "Sales Invoice"),
			_item("Sales People", "DocType", "Sales Person"),
			_item("Sales Person Commissions", "Report", "Sales Person Commission Summary"),
		),
		_group(
			"buy",
			_item("Purchase Invoices", "DocType", "Purchase Invoice"),
			_item("Purchase Register", "Page", "purchase-register"),
		),
		_group(
			"stock",
			_item("Products", "DocType", "Item"),
			_item("Stock Transfers", "DocType", "Stock Entry"),
			_item("Stock Ledger", "Report", "Stock Ledger"),
			_item("Inventory Intelligence", "Page", "inventory-intelligence"),
		),
		_group(
			"review-approvals",
			_item("Daily Sales Audit", "Page", "daily-sales-audit"),
			_item("Bank Matching", "Page", "bank-matching-reconciliation"),
		),
		_group(
			"accounting",
			_item("Trial Balance", "Report", "Trial Balance"),
			_item("Journal Entries", "DocType", "Journal Entry"),
			_item("Cost Centers", "DocType", "Cost Center"),
		),
		_group(
			"setup",
			_item("Bank Accounts", "DocType", "Bank Account"),
			_item("Settings", "DocType", "RetailEdge Settings"),
		),
		_group("reports", _item("Reports Centre", "Page", "reports-centre")),
	]

	_reclassify_navigation_for_task_frequency(groups)

	keys = [group["key"] for group in groups]
	assert keys == [
		"home",
		"point-of-sale",
		"sales",
		"purchases",
		"stock",
		"money-banking",
		"operations-review",
		"banking-reconciliation",
		"insights",
		"reports",
		"selling-setup",
		"stock-setup",
		"finance-setup",
		"business-setup",
	]

	by_key = {group["key"]: group for group in groups}
	assert [item["target"] for item in by_key["point-of-sale"]["items"]] == ["/pos"]
	assert "Sales Invoice" in {item["target"] for item in by_key["sales"]["items"]}
	assert "Sales Person" in {item["target"] for item in by_key["selling-setup"]["items"]}
	assert "Purchase Invoice" in {item["target"] for item in by_key["purchases"]["items"]}
	assert "purchase-register" not in {
		item["target"] for group in groups for item in group["items"]
	}
	assert "Item" in {item["target"] for item in by_key["stock-setup"]["items"]}
	assert "Stock Entry" in {item["target"] for item in by_key["stock"]["items"]}
	assert "inventory-intelligence" in {item["target"] for item in by_key["insights"]["items"]}
	assert "bank-matching-reconciliation" in {
		item["target"] for item in by_key["banking-reconciliation"]["items"]
	}
	assert "daily-sales-audit" in {
		item["target"] for item in by_key["operations-review"]["items"]
	}
	assert "Journal Entry" in {item["target"] for item in by_key["money-banking"]["items"]}
	assert "Cost Center" in {item["target"] for item in by_key["finance-setup"]["items"]}
	assert "RetailEdge Settings" in {item["target"] for item in by_key["business-setup"]["items"]}
	assert by_key["reports"]["items"] == [
		_item("Reports Centre", "Page", "reports-centre")
	]
	assert all(
		item["target_type"] != "Report"
		for group in groups
		for item in group["items"]
	)


def test_reports_centre_absorbs_detailed_links_removed_from_daily_navigation():
	targets = {
		item["target"]
		for group in REPORT_GROUPS
		for item in group["items"]
	}
	for target in {
		"Sales Person Commission Summary",
		"Sales Partner Commission Summary",
		"Sales Person Target Variance Based On Item Group",
		"Sales Partner Target Variance based on Item Group",
		"Stock Balance",
		"Stock Ledger",
		"Stock Projected Qty",
		"Stock Ageing",
		"Accounts Receivable",
		"Accounts Payable",
		"RetailEdge Customer Advance Register",
		"RetailEdge Invoice Payment Audit",
		"RetailEdge Daily Sales Audit Register",
		"RetailEdge Project Portfolio",
		"RetailEdge Project Financial Control",
	}:
		assert target in targets


def test_native_workspace_uses_same_task_frequency_taxonomy():
	assert HOME_SECTIONS == (
		"Home",
		"Point of Sale",
		"Sales",
		"Purchases",
		"Stock",
		"Money & Banking",
		"Expenses",
		"Customers",
		"Suppliers & Payables",
		"Operations Review",
		"Banking & Reconciliation",
		"Insights & Dashboards",
		"Reports",
		"Selling Setup",
		"Stock Setup",
		"Finance Setup",
		"Business Setup",
	)
	by_section: dict[str, set[str]] = {}
	for item in HOME_WORKSPACE_ITEMS:
		by_section.setdefault(item.section, set()).add(item.link_to)

	assert "Sales Invoice" in by_section["Sales"]
	assert "Sales Person" not in by_section["Sales"]
	assert "Sales Person" in by_section["Selling Setup"]
	assert "Stock Ledger" not in by_section["Stock"]
	assert "Item" not in by_section["Stock"]
	assert "Item" in by_section["Stock Setup"]
	assert by_section["Reports"] == {"reports-centre"}


def test_product_menu_supports_every_final_navigation_group():
	source = (ROOT / "public" / "js" / "retailedge_product_menu.bundle.js").read_text(encoding="utf-8")
	for key, _label, _icon in NAVIGATION_PRESENTATION_GROUPS:
		assert f'{key}:' in source or f'"{key}":' in source


def test_workspace_sync_no_longer_depends_on_obsolete_section_labels_or_readds_stock_report():
	source = (ROOT / "workspace_sync.py").read_text(encoding="utf-8")
	assert 'POS_SECTION_LABEL = "Point of Sale"' in source
	assert 'REPORTS_SECTION_LABEL = "Reports"' in source
	assert '"Sales & POS"' not in source
	assert '"Reports & Insights"' not in source
	assert "_ensure_workspace_business_hub_link(_ensure_workspace_report_link(" not in source
	assert "_ensure_sidebar_business_hub_link(_ensure_sidebar_report_link(" not in source


def test_purchase_invoice_remains_an_operational_destination_when_reports_centre_is_available():
	source = (ROOT / "master_experience.py").read_text(encoding="utf-8")
	context_builder = source.split(
		"def get_retailedge_business_hub_context()", 1
	)[1].split("def _can_create_master", 1)[0]
	assert "_promote_purchase_invoice_ownership(navigation_groups)" not in context_builder
	assert 'feature_flags["purchase_invoice_ownership"] = "native_invoice_plus_reports_centre"' in context_builder
