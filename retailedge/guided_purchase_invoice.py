from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt, getdate, nowdate

from retailedge.branch_context import has_doctype, resolve_retailedge_operational_defaults
from retailedge.guided_entry_context import (
	get_guided_branch_names,
	get_guided_branch_search_filters,
	get_guided_warehouse_search_filters,
	resolve_guided_branch,
	resolve_guided_company,
	resolve_guided_default_branch,
	validate_guided_branch_warehouse,
)
from retailedge.guided_pricing import resolve_price_list_context, resolve_purchase_item_pricing
from retailedge.operating_context import get_operating_context, get_operational_branch_scope

ACTION_KEY = "record-purchase"
PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"
MAX_LINK_RESULTS = 20
MAX_ITEMS = 50


@frappe.whitelist()
def get_simple_purchase_invoice_context() -> dict[str, Any]:
	_assert_can_create_purchase_invoice()
	user = frappe.session.user
	operating = get_operating_context() or {}
	company = resolve_guided_company("", user=user)
	legacy_default_branch = (
		operating.get("branch")
		or frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	)
	if not company:
		frappe.throw(_("Set a default Company before creating a Purchase Invoice."))
	_assert_read_permission("Company", company)

	scope = get_operational_branch_scope(company, user=user)
	branch = resolve_guided_default_branch(
		company,
		str(legacy_default_branch or "").strip(),
		user=user,
	)

	defaults = resolve_retailedge_operational_defaults(
		company=company or None,
		branch=branch or None,
		user=user,
	)
	company = defaults.get("company") or company
	_assert_read_permission("Company", company)
	if branch:
		branch = resolve_guided_branch(company, branch, user=user)
	elif defaults.get("branch"):
		branch = resolve_guided_default_branch(
			company,
			defaults.get("branch") or "",
			user=user,
		)

	warehouse = (
		defaults.get("default_target_warehouse")
		or defaults.get("default_warehouse")
		or defaults.get("warehouse")
		or ""
	)
	if scope["restricted"] and not branch:
		warehouse = ""
	if warehouse and branch:
		try:
			validate_guided_branch_warehouse(
				branch=branch,
				warehouse=warehouse,
				company=company,
				user=user,
			)
		except Exception:
			warehouse = ""

	pricing = resolve_price_list_context(
		mode="buying", company=company, branch=branch or "", user=user
	)

	return {
		"action_key": ACTION_KEY,
		"title": _("Simple Purchase Invoice"),
		"subtitle": _("Create a standard ERPNext Purchase Invoice draft with the essential buying fields."),
		"submit_label": _("Save Draft"),
		"full_form_doctype": PURCHASE_INVOICE_DOCTYPE,
		"pricing": pricing,
		"defaults": {
			"company": company,
			"branch": branch or "",
			"posting_date": nowdate(),
			"bill_no": "",
			"bill_date": nowdate(),
			"warehouse": warehouse,
			"supplier": "",
			"price_list": "",
			"update_stock": 0,
			"remarks": "",
			"items": [{"item_code": "", "qty": 1, "rate": ""}],
		},
		"capabilities": {
			"branch_enabled": bool(has_doctype("Branch")),
			"requires_branch_selection": bool(
				get_guided_branch_names(company, user=user)
			),
			"can_create_supplier": bool(
				has_doctype("Supplier") and frappe.has_permission("Supplier", "create")
			),
			"can_create_item": bool(has_doctype("Item") and frappe.has_permission("Item", "create")),
			"can_switch_price_list": bool(pricing.get("can_switch_price_list")),
			"native_form_fallback": True,
		},
		"limits": {"link_results": MAX_LINK_RESULTS, "max_items": MAX_ITEMS},
	}


@frappe.whitelist()
def search_simple_purchase_invoice_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_can_create_purchase_invoice()
	values = _coerce_values(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	company = resolve_guided_company(values.get("company") or "", user=frappe.session.user)
	branch = values.get("branch") or ""
	supplier = values.get("supplier") or ""

	if fieldname == "supplier":
		return search_link(
			"Supplier",
			txt or "",
			page_length=limit,
			reference_doctype=PURCHASE_INVOICE_DOCTYPE,
			link_fieldname="supplier",
		)
	if fieldname == "item_code":
		filters: dict[str, Any] = {"is_purchase_item": 1}
		if supplier:
			filters["supplier"] = supplier
		return search_link(
			"Item",
			txt or "",
			query="erpnext.controllers.queries.item_query",
			filters=filters,
			page_length=limit,
			reference_doctype="Purchase Invoice Item",
			link_fieldname="item_code",
		)
	if fieldname == "price_list":
		pricing = resolve_price_list_context(
			mode="buying",
			company=company,
			branch=branch,
			party=supplier,
			user=frappe.session.user,
		)
		query = str(txt or "").strip().lower()
		return [
			{"value": name, "label": name}
			for name in pricing.get("available_price_lists") or []
			if not query or query in str(name).lower()
		][:limit]
	if fieldname == "warehouse":
		filters = _warehouse_search_filters(company=company, branch=branch, user=frappe.session.user)
		if filters is None:
			return []
		return search_link(
			"Warehouse",
			txt or "",
			filters=filters,
			page_length=limit,
			reference_doctype=PURCHASE_INVOICE_DOCTYPE,
			link_fieldname="set_warehouse",
		)
	if fieldname == "branch":
		if not has_doctype("Branch"):
			return []
		return search_link(
			"Branch",
			txt or "",
			filters=_branch_search_filters(company=company, user=frappe.session.user),
			page_length=limit,
			reference_doctype=PURCHASE_INVOICE_DOCTYPE,
			link_fieldname="retailedge_branch",
		)
	frappe.throw(_("Unsupported Simple Purchase Invoice search field: {0}").format(fieldname))
	return []


@frappe.whitelist()
def get_simple_purchase_invoice_item_pricing(
	item_code: str,
	values: dict | str | None = None,
) -> dict[str, Any]:
	_assert_can_create_purchase_invoice()
	values = _coerce_values(values)
	user = frappe.session.user
	company, branch, warehouse = _validate_transaction_context(values, user=user)
	supplier = str(values.get("supplier") or "").strip()
	if not supplier:
		frappe.throw(_("Select a Supplier before pricing items."))
	_assert_read_permission("Supplier", supplier)
	item_code = str(item_code or "").strip()
	_assert_read_permission("Item", item_code)
	return resolve_purchase_item_pricing(
		item_code=item_code,
		company=company,
		supplier=supplier,
		branch=branch,
		warehouse=warehouse,
		posting_date=values.get("posting_date") or nowdate(),
		qty=flt(values.get("qty") or 1),
		user=user,
		requested_price_list=values.get("price_list") or "",
	)


@frappe.whitelist(methods=["POST"])
def create_simple_purchase_invoice_draft(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_create_purchase_invoice()
	values = _coerce_values(values)
	user = frappe.session.user
	company, branch, warehouse = _validate_transaction_context(values, user=user)

	supplier = str(values.get("supplier") or "").strip()
	if not supplier:
		frappe.throw(_("Supplier is required."))
	_assert_read_permission("Supplier", supplier)

	items = _normalise_items(values.get("items"))
	configured_branches = get_guided_branch_names(company, user=user)
	update_stock = cint(values.get("update_stock") or 0)
	if update_stock and configured_branches and not branch:
		frappe.throw(_("Choose a Branch before saving a stock-updating Purchase Invoice."))
	if update_stock and not warehouse:
		frappe.throw(_("Warehouse is required when Update Stock is enabled."))

	pricing_context = resolve_price_list_context(
		mode="buying",
		company=company,
		branch=branch,
		party=supplier,
		user=user,
		requested_price_list=values.get("price_list") or "",
	)

	doc = frappe.new_doc(PURCHASE_INVOICE_DOCTYPE)
	doc.company = company
	doc.supplier = supplier
	doc.posting_date = getdate(values.get("posting_date") or nowdate())
	doc.update_stock = update_stock
	if pricing_context.get("price_list"):
		doc.buying_price_list = pricing_context["price_list"]
	bill_no = str(values.get("bill_no") or "").strip()
	if bill_no:
		doc.bill_no = bill_no
		doc.bill_date = getdate(values.get("bill_date") or doc.posting_date)
	if warehouse:
		doc.set_warehouse = warehouse
	if values.get("remarks"):
		doc.remarks = str(values.get("remarks")).strip()
	if branch:
		doc.branch = branch

	for item in items:
		_assert_read_permission("Item", item["item_code"])
		resolved = resolve_purchase_item_pricing(
			item_code=item["item_code"],
			company=company,
			supplier=supplier,
			branch=branch,
			warehouse=warehouse,
			posting_date=str(doc.posting_date),
			qty=item["qty"],
			user=user,
			requested_price_list=values.get("price_list") or "",
		)
		manual_rate = item.get("rate")
		resolved_rate = resolved.get("rate")
		effective_rate = manual_rate if manual_rate is not None else resolved_rate
		if effective_rate is None:
			frappe.throw(
				_(
					"No buying price could be resolved for Item {0}. Set a Buying Item Price or enter the agreed buying rate before saving."
				).format(item["item_code"])
			)

		row = {
			"item_code": item["item_code"],
			"qty": item["qty"],
			"rate": effective_rate,
		}
		if warehouse:
			row["warehouse"] = warehouse
		doc.append("items", row)

	# Buying Price List selection and fallback pricing are resolved server-side
	# from the governed supplier/Branch/assignment policy and ERPNext pricing.
	doc.insert()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"supplier": doc.supplier,
		"company": doc.company,
		"branch": getattr(doc, "retailedge_branch", None) or branch,
		"buying_price_list": getattr(doc, "buying_price_list", None) or pricing_context.get("price_list"),
		"grand_total": doc.grand_total,
		"currency": doc.currency,
		"route": f"/app/purchase-invoice/{doc.name}",
	}


def _normalise_items(items: Any) -> list[dict[str, Any]]:
	if isinstance(items, str):
		items = frappe.parse_json(items)
	if not isinstance(items, list) or not items:
		frappe.throw(_("Add at least one purchase item."))
	if len(items) > MAX_ITEMS:
		frappe.throw(_("A Simple Purchase Invoice can contain at most {0} items.").format(MAX_ITEMS))

	result: list[dict[str, Any]] = []
	for index, item in enumerate(items, start=1):
		if not isinstance(item, dict):
			frappe.throw(_("Purchase item row {0} is invalid.").format(index))
		item_code = str(item.get("item_code") or "").strip()
		if not item_code:
			frappe.throw(_("Item is required on row {0}.").format(index))
		qty = flt(item.get("qty"))
		if qty <= 0:
			frappe.throw(_("Quantity on row {0} must be greater than zero.").format(index))
		rate_value = item.get("rate")
		rate = None if rate_value in (None, "") else flt(rate_value)
		if rate is not None and rate < 0:
			frappe.throw(_("Buying Rate on row {0} cannot be negative.").format(index))
		result.append({"item_code": item_code, "qty": qty, "rate": rate})
	return result


def _resolve_guided_branch(*, company: str, branch: str, user: str) -> str:
	return resolve_guided_branch(company, branch, user=user)


def _validate_transaction_context(values: dict[str, Any], *, user: str) -> tuple[str, str, str]:
	company = resolve_guided_company(values.get("company") or "", user=user)
	if not company:
		frappe.throw(_("Company is required."))
	_assert_read_permission("Company", company)

	branch = resolve_guided_branch(
		company,
		str(values.get("branch") or "").strip(),
		user=user,
	)

	warehouse = str(values.get("warehouse") or "").strip()
	configured_branches = get_guided_branch_names(company, user=user)
	if warehouse and configured_branches and not branch:
		frappe.throw(_("Choose a Branch before selecting a Receiving Stock Location."))
	if warehouse:
		_assert_read_permission("Warehouse", warehouse)
		warehouse_company = frappe.db.get_value("Warehouse", warehouse, "company")
		if warehouse_company and warehouse_company != company:
			frappe.throw(_("Warehouse {0} does not belong to Company {1}.").format(warehouse, company))
		if branch:
			validate_guided_branch_warehouse(
				branch=branch,
				warehouse=warehouse,
				company=company,
				user=user,
			)
	return company, branch, warehouse


def _warehouse_search_filters(company: str, branch: str, user: str) -> dict[str, Any] | None:
	return get_guided_warehouse_search_filters(company, branch, user=user)


def _branch_search_filters(company: str, user: str) -> dict[str, Any]:
	return get_guided_branch_search_filters(company, user=user)


def _validate_branch_warehouse(*, branch: str, warehouse: str, company: str, user: str) -> None:
	validate_guided_branch_warehouse(
		branch=branch,
		warehouse=warehouse,
		company=company,
		user=user,
	)


def _assert_can_create_purchase_invoice() -> None:
	if not has_doctype(PURCHASE_INVOICE_DOCTYPE) or not frappe.has_permission(
		PURCHASE_INVOICE_DOCTYPE, "create"
	):
		frappe.throw(_("You do not have permission to create Purchase Invoices."), frappe.PermissionError)


def _assert_read_permission(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError)


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if not values:
		return {}
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if isinstance(values, frappe._dict):
		return dict(values)
	if isinstance(values, dict):
		return dict(values)
	frappe.throw(_("Invalid Simple Purchase Invoice values."))
	return {}
