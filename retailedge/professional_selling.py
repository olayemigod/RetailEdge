from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt, nowdate
from frappe.utils.user import get_user_fullname

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	get_user_allowed_branches,
	has_field,
	resolve_branch_from_warehouse,
	validate_user_branch_access,
)
from retailedge.branch_profile import get_branch_profile_defaults
from retailedge.guided_pricing import resolve_price_list_context, resolve_sales_item_pricing
from retailedge.operating_context import (
	get_allowed_operating_branches,
	get_operating_context,
	validate_operating_branch,
)


MAX_LINK_RESULTS = 20
SELLING_DOCUMENTS: tuple[dict[str, Any], ...] = (
	{
		"key": "quotation",
		"doctype": "Quotation",
		"item_doctype": "Quotation Item",
		"label": "Quotation",
		"stage": "Quote",
		"date_field": "transaction_date",
		"party_field": "party_name",
		"party_type_field": "quotation_to",
		"supports_shipping_rule": True,
		"supports_source_warehouse": False,
		"native_route": "/app/quotation",
	},
	{
		"key": "sales-order",
		"doctype": "Sales Order",
		"item_doctype": "Sales Order Item",
		"label": "Sales Order",
		"stage": "Order",
		"date_field": "transaction_date",
		"party_field": "customer",
		"supports_shipping_rule": True,
		"supports_source_warehouse": True,
		"native_route": "/app/sales-order",
	},
	{
		"key": "delivery-note",
		"doctype": "Delivery Note",
		"item_doctype": "Delivery Note Item",
		"label": "Delivery Note",
		"stage": "Delivery",
		"date_field": "posting_date",
		"party_field": "customer",
		"supports_shipping_rule": True,
		"supports_source_warehouse": True,
		"native_route": "/app/delivery-note",
	},
)

_DOCUMENT_BY_KEY = {row["key"]: row for row in SELLING_DOCUMENTS}
_DOCUMENT_BY_DOCTYPE = {row["doctype"]: row for row in SELLING_DOCUMENTS}


def get_selling_document_definition(value: str) -> dict[str, Any]:
	key = str(value or "").strip()
	definition = _DOCUMENT_BY_KEY.get(key) or _DOCUMENT_BY_DOCTYPE.get(key)
	if not definition:
		frappe.throw(_("Unsupported Professional Selling document: {0}").format(key))
	return dict(definition)


def _doctype_available(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype))


def _permission(doctype: str, ptype: str) -> bool:
	try:
		return bool(_doctype_available(doctype) and frappe.has_permission(doctype, ptype))
	except Exception:
		return False


def _field_exists(doctype: str, fieldname: str) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return False


def _assert_read(doctype: str, name: str) -> None:
	name = str(name or "").strip()
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} is not available.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have permission to use {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)


def _document_capability(definition: dict[str, Any]) -> dict[str, Any]:
	doctype = definition["doctype"]
	available = _doctype_available(doctype)
	return {
		**definition,
		"available": available,
		"can_read": _permission(doctype, "read"),
		"can_create": _permission(doctype, "create"),
		"shipping_rule_field": available and _field_exists(doctype, "shipping_rule"),
		"selling_price_list_field": available and _field_exists(doctype, "selling_price_list"),
		"source_warehouse_field": available and _field_exists(doctype, "set_warehouse"),
	}


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	return dict(values or {})


def _validate_context(values: dict[str, Any]) -> tuple[str, str, str]:
	operating = get_operating_context() or {}
	company = str(
		values.get("company")
		or operating.get("company")
		or frappe.defaults.get_user_default("Company")
		or ""
	).strip()
	branch = str(values.get("branch") or operating.get("branch") or "").strip()
	warehouse = str(values.get("warehouse") or "").strip()
	if not company:
		frappe.throw(_("Choose an Operating Company before starting a selling document."))
	_assert_read("Company", company)
	if branch:
		validate_user_branch_access(
			branch,
			user=frappe.session.user,
			company=company,
			throw=True,
		)
		validate_operating_branch(
			company=company,
			branch=branch,
			user=frappe.session.user,
			throw=True,
		)
	if warehouse:
		_assert_read("Warehouse", warehouse)
		warehouse_company = str(frappe.db.get_value("Warehouse", warehouse, "company") or "").strip()
		if warehouse_company and warehouse_company != company:
			frappe.throw(_("Stock Location {0} does not belong to Company {1}.").format(warehouse, company))
		resolved = resolve_branch_from_warehouse(warehouse, company=company)
		warehouse_branch = str(resolved.get("branch") or "").strip()
		if branch and warehouse_branch and warehouse_branch != branch:
			frappe.throw(_("Stock Location {0} does not belong to Branch {1}.").format(warehouse, branch))
	return company, branch, warehouse


def _branch_filters(company: str) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	if company and has_field("Branch", "company"):
		filters["company"] = company
	allowed = get_allowed_operating_branches(company=company, user=frappe.session.user)
	filters["name"] = ["in", allowed] if allowed else ["in", ["__no_permitted_branch__"]]
	return filters


def _warehouse_filters(company: str, branch: str) -> dict[str, Any] | None:
	filters: dict[str, Any] = {"is_group": 0}
	if company and has_field("Warehouse", "company"):
		filters["company"] = company
	if not branch:
		return filters
	validate_user_branch_access(
		branch,
		user=frappe.session.user,
		company=company or None,
		throw=True,
	)
	validate_operating_branch(
		company=company,
		branch=branch,
		user=frappe.session.user,
		throw=True,
	)
	branch_field = get_first_existing_field("Warehouse", BRANCH_FIELD_CANDIDATES)
	if branch_field:
		filters[branch_field] = branch
		return filters
	defaults = get_branch_profile_defaults(
		company=company or None,
		branch=branch,
		user=frappe.session.user,
	)
	warehouses = []
	for key in (
		"default_source_warehouse",
		"default_warehouse",
		"default_target_warehouse",
		"default_returns_warehouse",
	):
		value = str(defaults.get(key) or "").strip()
		if value and value not in warehouses:
			warehouses.append(value)
	if not warehouses:
		return None
	filters["name"] = ["in", warehouses]
	return filters


@frappe.whitelist()
def get_professional_selling_context() -> dict[str, Any]:
	"""Return a read-only, permission-aware Quote → Order → Delivery context."""
	operating = get_operating_context() or {}
	company = str(operating.get("company") or "").strip()
	branch = str(operating.get("branch") or "").strip()
	pricing: dict[str, Any] = {}
	if company and _permission("Price List", "read"):
		pricing = resolve_price_list_context(
			mode="selling",
			company=company,
			branch=branch,
			user=frappe.session.user,
		)

	documents = [_document_capability(row) for row in SELLING_DOCUMENTS]
	return {
		"operating": {
			"company": company,
			"branch": branch,
			"default_stock_location": operating.get("default_stock_location") or "",
		},
		"pricing": {
			"price_list": pricing.get("price_list") or "",
			"source": pricing.get("source") or "",
			"allow_rate_change": bool(pricing.get("allow_rate_change", True)),
		},
		"documents": documents,
		"today": nowdate(),
		"shipping": {
			"doctype": "Shipping Rule",
			"available": _doctype_available("Shipping Rule"),
			"can_read": _permission("Shipping Rule", "read"),
			"policy": "erpnext_native",
		},
		"safety": {
			"draft_first": True,
			"submitted_documents_immutable": True,
			"erpnext_pricing_authoritative": True,
			"erpnext_shipping_rule_authoritative": True,
		},
		"user_name": get_user_fullname(frappe.session.user) if getattr(frappe, "session", None) else "",
	}


@frappe.whitelist()
def search_professional_selling_options(
	document: str,
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	"""Bound Link searches to records valid for the current selling context."""
	definition = get_selling_document_definition(document)
	if not _permission(definition["doctype"], "create"):
		frappe.throw(
			_("You do not have permission to create {0}.").format(definition["doctype"]),
			frappe.PermissionError,
		)
	values = _coerce_values(values)
	company, branch, _warehouse = _validate_context(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	customer = str(values.get("customer") or values.get("party_name") or "").strip()

	if fieldname == "customer":
		return search_link(
			"Customer",
			txt or "",
			page_length=limit,
			reference_doctype=definition["doctype"],
			link_fieldname=definition["party_field"],
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
			reference_doctype=definition["item_doctype"],
			link_fieldname="item_code",
		)
	if fieldname == "branch":
		return search_link(
			"Branch",
			txt or "",
			filters=_branch_filters(company),
			page_length=limit,
			reference_doctype=definition["doctype"],
		)
	if fieldname == "warehouse":
		filters = _warehouse_filters(company, branch)
		if filters is None:
			return []
		return search_link(
			"Warehouse",
			txt or "",
			filters=filters,
			page_length=limit,
			reference_doctype=definition["doctype"],
			link_fieldname="set_warehouse",
		)
	if fieldname == "shipping_rule":
		filters = {"disabled": 0, "shipping_rule_type": "Selling", "company": company}
		return search_link(
			"Shipping Rule",
			txt or "",
			filters=filters,
			page_length=limit,
			reference_doctype=definition["doctype"],
			link_fieldname="shipping_rule",
		)
	frappe.throw(_("Unsupported Professional Selling search field: {0}").format(fieldname))
	return []


@frappe.whitelist()
def get_professional_selling_item_pricing(
	document: str,
	item_code: str,
	values: dict | str | None = None,
) -> dict[str, Any]:
	"""Resolve item price on the server; the browser never selects the effective Price List."""
	definition = get_selling_document_definition(document)
	if not _permission(definition["doctype"], "create"):
		frappe.throw(
			_("You do not have permission to create {0}.").format(definition["doctype"]),
			frappe.PermissionError,
		)
	values = _coerce_values(values)
	company, branch, warehouse = _validate_context(values)
	customer = str(values.get("customer") or values.get("party_name") or "").strip()
	if not customer:
		frappe.throw(_("Select a Customer before pricing items."))
	_assert_read("Customer", customer)
	item_code = str(item_code or "").strip()
	_assert_read("Item", item_code)
	return resolve_sales_item_pricing(
		item_code=item_code,
		company=company,
		customer=customer,
		branch=branch,
		warehouse=warehouse,
		posting_date=str(values.get("transaction_date") or values.get("posting_date") or nowdate()),
		qty=flt(values.get("qty") or 1),
		user=frappe.session.user,
	)


@frappe.whitelist()
def get_recent_selling_documents(document: str, limit: int = 8) -> list[dict[str, Any]]:
	"""Return a bounded recent-document list using native Frappe permissions."""
	definition = get_selling_document_definition(document)
	doctype = definition["doctype"]
	if not _permission(doctype, "read"):
		frappe.throw(_("You do not have permission to view {0}.").format(doctype), frappe.PermissionError)

	limit = max(1, min(int(limit or 8), 20))
	meta = frappe.get_meta(doctype)
	fields = ["name", "docstatus", "modified"]
	for candidate in (
		definition["party_field"],
		definition["date_field"],
		"status",
		"grand_total",
		"currency",
		"shipping_rule",
	):
		if candidate not in fields and meta.has_field(candidate):
			fields.append(candidate)

	rows = frappe.get_list(doctype, fields=fields, order_by="modified desc", limit_page_length=limit)
	return [dict(row) for row in rows]
