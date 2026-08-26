from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt, getdate, nowdate

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	get_user_allowed_branches,
	has_doctype,
	has_field,
	resolve_branch_from_warehouse,
	resolve_retailedge_operational_defaults,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.branch_profile import get_branch_profile, get_branch_profile_defaults
from retailedge.guided_pricing import resolve_price_list_context, resolve_sales_item_pricing

ACTION_KEY = "new-sales-invoice"
SALES_INVOICE_DOCTYPE = "Sales Invoice"
MAX_LINK_RESULTS = 20
MAX_ITEMS = 50


@frappe.whitelist()
def get_simple_sales_invoice_context() -> dict[str, Any]:
	_assert_can_create_sales_invoice()
	user = frappe.session.user
	company = frappe.defaults.get_user_default("Company") or ""
	branch = (
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	)
	defaults = resolve_retailedge_operational_defaults(
		company=company or None,
		branch=branch or None,
		user=user,
	)
	company = defaults.get("company") or company
	branch = defaults.get("branch") or branch
	if not company:
		frappe.throw(_("Set a default Company before creating a Sales Invoice."))
	_assert_read_permission("Company", company)
	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)

	warehouse = (
		defaults.get("default_source_warehouse")
		or defaults.get("default_warehouse")
		or defaults.get("warehouse")
		or ""
	)
	if warehouse and branch:
		_validate_branch_warehouse(branch=branch, warehouse=warehouse, company=company, user=user)

	pricing = resolve_price_list_context(
		mode="selling", company=company, branch=branch or "", user=user
	)

	return {
		"action_key": ACTION_KEY,
		"title": _("Simple Sales Invoice"),
		"subtitle": _("Create a standard ERPNext Sales Invoice draft with only the business fields you need."),
		"submit_label": _("Save Draft"),
		"full_form_doctype": SALES_INVOICE_DOCTYPE,
		"pricing": pricing,
		"defaults": {
			"company": company,
			"branch": branch or "",
			"posting_date": nowdate(),
			"warehouse": warehouse,
			"customer": "",
			"update_stock": 0,
			"remarks": "",
			"items": [{"item_code": "", "qty": 1, "rate": ""}],
		},
		"capabilities": {
			"branch_enabled": bool(has_doctype("Branch")),
			"can_create_customer": bool(
				has_doctype("Customer") and frappe.has_permission("Customer", "create")
			),
			"can_create_item": bool(has_doctype("Item") and frappe.has_permission("Item", "create")),
			"can_override_rate": bool(pricing.get("allow_rate_change", True)),
			"native_form_fallback": True,
		},
		"limits": {"link_results": MAX_LINK_RESULTS, "max_items": MAX_ITEMS},
	}


@frappe.whitelist()
def search_simple_sales_invoice_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_can_create_sales_invoice()
	values = _coerce_values(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	branch = values.get("branch") or ""
	customer = values.get("customer") or ""

	if fieldname == "customer":
		return search_link(
			"Customer",
			txt or "",
			page_length=limit,
			reference_doctype=SALES_INVOICE_DOCTYPE,
			link_fieldname="customer",
		)
	if fieldname == "item_code":
		filters: dict[str, Any] = {"is_sales_item": 1}
		if customer:
			filters["customer"] = customer
		return search_link(
			"Item",
			txt or "",
			query="erpnext.controllers.queries.item_query",
			filters=filters,
			page_length=limit,
			reference_doctype="Sales Invoice Item",
			link_fieldname="item_code",
		)
	if fieldname == "warehouse":
		filters = _warehouse_search_filters(company=company, branch=branch, user=frappe.session.user)
		if filters is None:
			return []
		return search_link(
			"Warehouse",
			txt or "",
			filters=filters,
			page_length=limit,
			reference_doctype=SALES_INVOICE_DOCTYPE,
			link_fieldname="set_warehouse",
		)
	if fieldname == "branch":
		if not has_doctype("Branch"):
			return []
		filters = _branch_search_filters(company=company, user=frappe.session.user)
		return search_link(
			"Branch",
			txt or "",
			filters=filters,
			page_length=limit,
			reference_doctype=SALES_INVOICE_DOCTYPE,
			link_fieldname="retailedge_branch",
		)
	frappe.throw(_("Unsupported Simple Sales Invoice search field: {0}").format(fieldname))
	return []


@frappe.whitelist()
def get_simple_sales_invoice_item_pricing(
	item_code: str,
	values: dict | str | None = None,
) -> dict[str, Any]:
	_assert_can_create_sales_invoice()
	values = _coerce_values(values)
	user = frappe.session.user
	company, branch, warehouse = _validate_transaction_context(values, user=user)
	customer = str(values.get("customer") or "").strip()
	if not customer:
		frappe.throw(_("Select a Customer before pricing items."))
	_assert_read_permission("Customer", customer)
	item_code = str(item_code or "").strip()
	_assert_read_permission("Item", item_code)
	return resolve_sales_item_pricing(
		item_code=item_code,
		company=company,
		customer=customer,
		branch=branch,
		warehouse=warehouse,
		posting_date=values.get("posting_date") or nowdate(),
		qty=flt(values.get("qty") or 1),
		user=user,
	)


@frappe.whitelist(methods=["POST"])
def create_simple_sales_invoice_draft(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_create_sales_invoice()
	values = _coerce_values(values)
	user = frappe.session.user
	company, branch, warehouse = _validate_transaction_context(values, user=user)

	customer = str(values.get("customer") or "").strip()
	if not customer:
		frappe.throw(_("Customer is required."))
	_assert_read_permission("Customer", customer)

	items = _normalise_items(values.get("items"))
	update_stock = cint(values.get("update_stock") or 0)
	if update_stock and not warehouse:
		frappe.throw(_("Warehouse is required when Update Stock is enabled."))

	pricing_context = resolve_price_list_context(
		mode="selling", company=company, branch=branch, party=customer, user=user
	)

	doc = frappe.new_doc(SALES_INVOICE_DOCTYPE)
	doc.company = company
	doc.customer = customer
	doc.posting_date = getdate(values.get("posting_date") or nowdate())
	doc.update_stock = update_stock
	if pricing_context.get("price_list"):
		doc.selling_price_list = pricing_context["price_list"]
	if warehouse:
		doc.set_warehouse = warehouse
	if values.get("remarks"):
		doc.remarks = str(values.get("remarks")).strip()
	if branch:
		doc.branch = branch

	for item in items:
		_assert_read_permission("Item", item["item_code"])
		resolved = resolve_sales_item_pricing(
			item_code=item["item_code"],
			company=company,
			customer=customer,
			branch=branch,
			warehouse=warehouse,
			posting_date=str(doc.posting_date),
			qty=item["qty"],
			user=user,
		)
		resolved_rate = resolved.get("rate")
		manual_rate = item.get("rate")
		if resolved_rate is None and manual_rate is None:
			frappe.throw(
				_(
					"No selling price could be resolved for Item {0}. Set an Item Price or Item Standard Rate before saving."
				).format(item["item_code"])
			)
		if resolved.get("source") == "pos_profile" and not resolved.get("allow_rate_change", True):
			effective_rate = resolved_rate
		else:
			effective_rate = manual_rate if manual_rate is not None else resolved_rate
		if effective_rate is None:
			frappe.throw(_("Selling Rate is required for Item {0}.").format(item["item_code"]))

		row = {
			"item_code": item["item_code"],
			"qty": item["qty"],
			"rate": effective_rate,
		}
		if warehouse:
			row["warehouse"] = warehouse
		doc.append("items", row)

	# The effective Price List and rates are resolved on the server from the
	# authenticated user's defaults/POS profile and ERPNext pricing engine. The
	# browser cannot choose a different Price List or bypass a POS rate lock.
	doc.insert()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"customer": doc.customer,
		"company": doc.company,
		"branch": getattr(doc, "retailedge_branch", None) or branch,
		"selling_price_list": getattr(doc, "selling_price_list", None) or pricing_context.get("price_list"),
		"grand_total": doc.grand_total,
		"currency": doc.currency,
		"route": f"/app/sales-invoice/{doc.name}",
	}


def _normalise_items(items: Any) -> list[dict[str, Any]]:
	if isinstance(items, str):
		items = frappe.parse_json(items)
	if not isinstance(items, list):
		frappe.throw(_("Add at least one invoice item."))
	if not items:
		frappe.throw(_("Add at least one invoice item."))
	if len(items) > MAX_ITEMS:
		frappe.throw(_("A Simple Sales Invoice can contain at most {0} items.").format(MAX_ITEMS))

	normalised: list[dict[str, Any]] = []
	for index, item in enumerate(items, start=1):
		if not isinstance(item, dict):
			frappe.throw(_("Invoice item row {0} is invalid.").format(index))
		item_code = str(item.get("item_code") or "").strip()
		if not item_code:
			frappe.throw(_("Item is required on row {0}.").format(index))
		qty = flt(item.get("qty"))
		if qty <= 0:
			frappe.throw(_("Quantity on row {0} must be greater than zero.").format(index))
		rate_value = item.get("rate")
		rate = None if rate_value in (None, "") else flt(rate_value)
		if rate is not None and rate < 0:
			frappe.throw(_("Selling Rate on row {0} cannot be negative.").format(index))
		normalised.append({"item_code": item_code, "qty": qty, "rate": rate})
	return normalised


def _validate_transaction_context(values: dict[str, Any], *, user: str) -> tuple[str, str, str]:
	company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	_assert_read_permission("Company", company)

	branch = str(values.get("branch") or "").strip()
	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)

	warehouse = str(values.get("warehouse") or "").strip()
	if warehouse:
		_assert_read_permission("Warehouse", warehouse)
		warehouse_company = frappe.db.get_value("Warehouse", warehouse, "company")
		if warehouse_company and warehouse_company != company:
			frappe.throw(_("Warehouse {0} does not belong to Company {1}.").format(warehouse, company))
		if branch:
			_validate_branch_warehouse(branch=branch, warehouse=warehouse, company=company, user=user)
	return company, branch, warehouse


def _warehouse_search_filters(company: str, branch: str, user: str) -> dict[str, Any] | None:
	filters: dict[str, Any] = {"is_group": 0}
	if company and has_field("Warehouse", "company"):
		filters["company"] = company
	if not branch:
		return filters

	validate_user_branch_access(branch, user=user, company=company or None, throw=True)
	branch_field = get_first_existing_field("Warehouse", BRANCH_FIELD_CANDIDATES)
	if branch_field:
		filters[branch_field] = branch
		return filters

	profile_defaults = get_branch_profile_defaults(company=company or None, branch=branch, user=user)
	warehouses = _unique(
		[
			profile_defaults.get("default_source_warehouse"),
			profile_defaults.get("default_warehouse"),
			profile_defaults.get("default_target_warehouse"),
			profile_defaults.get("default_returns_warehouse"),
		]
	)
	if not warehouses:
		return None
	filters["name"] = ["in", warehouses]
	return filters


def _branch_search_filters(company: str, user: str) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if company and has_field("Branch", "company"):
		filters["company"] = company
	if user_has_global_branch_access(user=user):
		return filters
	allowed = get_user_allowed_branches(user=user, company=company or None).get("branches") or []
	if allowed:
		filters["name"] = ["in", allowed]
	return filters


def _validate_branch_warehouse(*, branch: str, warehouse: str, company: str, user: str) -> None:
	resolved = resolve_branch_from_warehouse(warehouse, company=company)
	warehouse_branch = resolved.get("branch")
	if warehouse_branch:
		if warehouse_branch != branch:
			frappe.throw(
				_("Warehouse {0} belongs to Branch {1}, not Branch {2}.").format(
					warehouse, warehouse_branch, branch
				)
			)
		return

	profile = get_branch_profile(
		company=company,
		branch=branch,
		user=user,
		warehouse=warehouse,
		active_only=True,
	)
	if profile:
		return
	frappe.throw(
		_("Warehouse {0} is not configured for Branch {1}. Choose a warehouse linked to this branch.").format(
			warehouse, branch
		)
	)


def _assert_can_create_sales_invoice() -> None:
	if not has_doctype(SALES_INVOICE_DOCTYPE) or not frappe.has_permission(
		SALES_INVOICE_DOCTYPE, "create"
	):
		frappe.throw(_("You do not have permission to create Sales Invoices."), frappe.PermissionError)


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
	frappe.throw(_("Invalid Simple Sales Invoice values."))
	return {}


def _unique(values: list[str | None]) -> list[str]:
	seen: set[str] = set()
	result: list[str] = []
	for value in values:
		if value and value not in seen:
			seen.add(value)
			result.append(value)
	return result
