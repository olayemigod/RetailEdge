from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt, getdate, nowdate
from frappe.utils.user import get_user_fullname

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	has_field,
	resolve_branch_from_warehouse,
)
from retailedge.branch_profile import get_branch_profile, get_branch_profile_defaults
from retailedge.guided_pricing import resolve_price_list_context, resolve_sales_item_pricing
from retailedge.operating_context import (
	get_allowed_operating_branches,
	get_operating_context,
	get_operational_branch_scope,
	resolve_operational_branch,
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

_LIST_DOCUMENTS: dict[str, dict[str, Any]] = {
	**{row["key"]: dict(row) for row in SELLING_DOCUMENTS},
	"sales-invoice": {
		"key": "sales-invoice",
		"doctype": "Sales Invoice",
		"label": "Sales Invoice",
		"stage": "Invoice",
		"date_field": "posting_date",
		"party_field": "customer",
		"native_route": "/app/sales-invoice",
	},
}


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


def _validate_stored_operational_branch(
	*,
	company: str,
	branch: str,
	label: str,
) -> str:
	branch = str(branch or "").strip()
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if branch:
		return str(
			resolve_operational_branch(
				company,
				branch,
				user=frappe.session.user,
			).get("branch")
			or ""
		).strip()
	if scope["restricted"]:
		frappe.throw(
			_("{0} has no Branch attribution for your restricted access.").format(label),
			frappe.PermissionError,
		)
	return ""


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	return dict(values or {})


def _validate_context(
	values: dict[str, Any],
	*,
	allow_unresolved_branch: bool = False,
) -> tuple[str, str, str]:
	operating = get_operating_context() or {}
	company = str(
		values.get("company")
		or operating.get("company")
		or frappe.defaults.get_user_default("Company")
		or ""
	).strip()
	branch_supplied = "branch" in values
	branch = str(
		values.get("branch")
		if branch_supplied
		else (operating.get("branch") or "")
	).strip()
	warehouse = str(values.get("warehouse") or "").strip()
	if not company:
		frappe.throw(_("Choose an Operating Company before starting a selling document."))
	_assert_read("Company", company)

	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if branch:
		branch = resolve_operational_branch(company, branch, user=frappe.session.user)["branch"]
	elif scope["restricted"]:
		if allow_unresolved_branch and len(scope["allowed_branches"]) != 1:
			branch = ""
		else:
			branch = resolve_operational_branch(company, "", user=frappe.session.user)["branch"]

	if warehouse:
		_assert_read("Warehouse", warehouse)
		warehouse_company = str(frappe.db.get_value("Warehouse", warehouse, "company") or "").strip()
		if warehouse_company and warehouse_company != company:
			frappe.throw(_("Stock Location {0} does not belong to Company {1}.").format(warehouse, company))

		resolved = resolve_branch_from_warehouse(warehouse, company=company)
		warehouse_branch = str(resolved.get("branch") or "").strip()
		if warehouse_branch:
			warehouse_branch = resolve_operational_branch(
				company,
				warehouse_branch,
				user=frappe.session.user,
			)["branch"]
			if branch and warehouse_branch != branch:
				frappe.throw(_("Stock Location {0} does not belong to Branch {1}.").format(warehouse, branch))
			branch = branch or warehouse_branch
		elif branch:
			profile = get_branch_profile(
				company=company,
				branch=branch,
				user=frappe.session.user,
				warehouse=warehouse,
				active_only=True,
			)
			if not profile:
				frappe.throw(
					_("Stock Location {0} is not configured for Branch {1}.").format(warehouse, branch)
				)
		elif scope["restricted"]:
			if allow_unresolved_branch and len(scope["allowed_branches"]) != 1:
				frappe.throw(_("Choose a Branch before selecting a Stock Location."))
			branch = resolve_operational_branch(company, "", user=frappe.session.user)["branch"]
			profile = get_branch_profile(
				company=company,
				branch=branch,
				user=frappe.session.user,
				warehouse=warehouse,
				active_only=True,
			)
			if not profile:
				frappe.throw(
					_("Stock Location {0} is not configured for Branch {1}.").format(warehouse, branch)
				)
	return company, branch, warehouse


def _operating_document_filters(doctype: str, *, company: str, branch: str) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	meta = frappe.get_meta(doctype)
	if company and meta.has_field("company"):
		filters["company"] = company

	branch_field = get_first_existing_field(doctype, BRANCH_FIELD_CANDIDATES)
	if branch:
		branch = resolve_operational_branch(company, branch, user=frappe.session.user)["branch"]
		if branch_field:
			filters[branch_field] = branch
		return filters

	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if scope["restricted"]:
		if not scope["allowed_branches"] or not branch_field:
			filters["name"] = "__never__"
		else:
			filters[branch_field] = ["in", scope["allowed_branches"]]
	return filters


def _branch_filters(company: str) -> dict[str, Any]:
	if not company:
		return {"name": "__never__"}
	filters: dict[str, Any] = {}
	if has_field("Branch", "company"):
		filters["company"] = company
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	allowed = get_allowed_operating_branches(company=company, user=frappe.session.user)
	if scope["restricted"] or allowed:
		filters["name"] = ["in", allowed] if allowed else "__never__"
	return filters


def _warehouse_filters(company: str, branch: str) -> dict[str, Any] | None:
	if not company:
		return None
	filters: dict[str, Any] = {"is_group": 0}
	if has_field("Warehouse", "company"):
		filters["company"] = company

	branch = str(branch or "").strip()
	if not branch:
		scope = get_operational_branch_scope(company, user=frappe.session.user)
		if not scope["restricted"]:
			return filters
		if not scope["allowed_branches"]:
			filters["name"] = "__never__"
			return filters
		if len(scope["allowed_branches"]) > 1:
			return None
	branch = resolve_operational_branch(company, branch, user=frappe.session.user)["branch"]

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
	company, branch, _warehouse = _validate_context(values, allow_unresolved_branch=True)
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
	"""Return a bounded recent-document list within active Operating Context."""
	definition = get_selling_document_definition(document)
	doctype = definition["doctype"]
	if not _permission(doctype, "read"):
		frappe.throw(_("You do not have permission to view {0}.").format(doctype), frappe.PermissionError)

	operating = get_operating_context() or {}
	company = str(operating.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(operating.get("branch") or "").strip()
	if not company:
		frappe.throw(_("Choose an Operating Company before viewing recent selling documents."))
	_assert_read("Company", company)
	filters = _operating_document_filters(doctype, company=company, branch=branch)

	limit = max(1, min(int(limit or 8), 20))
	meta = frappe.get_meta(doctype)
	fields = ["name", "docstatus", "modified"]
	branch_field = get_first_existing_field(doctype, BRANCH_FIELD_CANDIDATES)
	if branch_field and branch_field not in fields:
		fields.append(branch_field)
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

	rows = frappe.get_list(
		doctype,
		filters=filters,
		fields=fields,
		order_by="modified desc",
		limit_page_length=limit,
	)
	return [dict(row) for row in rows]


def _selling_list_definition(document: str) -> dict[str, Any]:
	key = str(document or "").strip()
	definition = _LIST_DOCUMENTS.get(key)
	if not definition:
		frappe.throw(_("Unsupported Professional Selling list: {0}").format(key))
	return dict(definition)


def _selling_record_actions(document: str, row: dict[str, Any]) -> list[dict[str, str]]:
	"""Return permission/status-aware secondary actions for one submitted selling record.

	These are discoverability hints only. Every target endpoint revalidates
	permissions, Company/Branch context and native ERPNext conversion rules.
	"""
	if cint(row.get("docstatus")) != 1:
		return []

	actions: list[dict[str, str]] = []
	status = str(row.get("status") or "").strip()
	if document == "quotation":
		if _permission("Sales Order", "create") and status not in {"Ordered", "Lost", "Cancelled", "Expired"}:
			actions.append({"value": "create-sales-order", "label": _("Create Sales Order")})
		if _permission("Sales Invoice", "create") and status not in {"Partially Ordered", "Ordered", "Lost", "Cancelled", "Expired"}:
			actions.append({"value": "create-sales-invoice", "label": _("Create Sales Invoice")})

	elif document == "sales-order":
		if (
			_permission("Delivery Note", "create")
			and status not in {"Closed", "Completed", "Cancelled"}
			and flt(row.get("per_delivered")) < 99.999
		):
			actions.append({"value": "create-delivery-note", "label": _("Create Delivery Note")})
		if (
			_permission("Sales Invoice", "create")
			and status not in {"Closed", "Cancelled"}
			and flt(row.get("per_billed")) < 99.999
		):
			actions.append({"value": "create-sales-invoice", "label": _("Create Sales Invoice")})
		if _permission("Payment Entry", "create") and flt(row.get("grand_total")) - flt(row.get("advance_paid")) > 0.005:
			actions.append({"value": "make-payment", "label": _("Make Payment")})

	elif document == "delivery-note":
		if (
			_permission("Sales Invoice", "create")
			and not cint(row.get("is_return"))
			and status not in {"Closed", "Cancelled"}
			and flt(row.get("per_billed")) < 99.999
		):
			actions.append({"value": "create-sales-invoice", "label": _("Create Sales Invoice")})

	elif document == "sales-invoice":
		if (
			_permission("Delivery Note", "create")
			and not cint(row.get("is_return"))
			and not cint(row.get("update_stock"))
			and status not in {"Cancelled", "Return"}
		):
			actions.append({"value": "create-delivery-note", "label": _("Create Delivery Note")})
		if (
			_permission("Sales Invoice", "create")
			and not cint(row.get("is_return"))
			and status not in {"Cancelled", "Return"}
		):
			actions.append({"value": "create-return-credit-note", "label": _("Return / Credit Note")})
		if _permission("Payment Entry", "create") and flt(row.get("outstanding_amount")) > 0.005:
			actions.append({"value": "make-payment", "label": _("Make Payment")})

	return actions


def _selling_list_status_filter(meta, status: str, filters: dict[str, Any]) -> None:
	status = str(status or "").strip()
	if not status or status == "All":
		return
	if status == "Draft":
		filters["docstatus"] = 0
		return
	if status == "Submitted":
		filters["docstatus"] = 1
		return
	if status == "Cancelled":
		filters["docstatus"] = 2
		return
	if meta.has_field("status"):
		filters["status"] = status


@frappe.whitelist()
def get_professional_selling_list(
	document: str,
	search: str = "",
	status: str = "All",
	from_date: str = "",
	to_date: str = "",
	start: int = 0,
	page_length: int = 20,
) -> dict[str, Any]:
	"""Return a filter-aware, permission-aware selling list for the four Professional Selling tabs."""
	definition = _selling_list_definition(document)
	doctype = definition["doctype"]
	if not _permission(doctype, "read"):
		frappe.throw(_("You do not have permission to view {0}.").format(doctype), frappe.PermissionError)

	operating = get_operating_context() or {}
	company = str(operating.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(operating.get("branch") or "").strip()
	if not company:
		frappe.throw(_("Choose an Operating Company before viewing Professional Selling records."))
	_assert_read("Company", company)

	filters = _operating_document_filters(doctype, company=company, branch=branch)
	meta = frappe.get_meta(doctype)
	branch_field = get_first_existing_field(doctype, BRANCH_FIELD_CANDIDATES)
	_selling_list_status_filter(meta, status, filters)

	date_field = definition["date_field"]
	from_text = str(from_date or "").strip()
	to_text = str(to_date or "").strip()
	if from_text:
		from_value = getdate(from_text)
		filters[date_field] = [">=", from_value]
	if to_text:
		to_value = getdate(to_text)
		if from_text and to_value < getdate(from_text):
			frappe.throw(_("To Date cannot be before From Date."))
		if date_field in filters:
			filters[date_field] = ["between", [getdate(from_text), to_value]]
		else:
			filters[date_field] = ["<=", to_value]

	search_text = str(search or "").strip()
	or_filters: list[list[Any]] = []
	if search_text:
		like = f"%{search_text}%"
		or_filters.append(["name", "like", like])
		party_field = definition["party_field"]
		if meta.has_field(party_field):
			or_filters.append([party_field, "like", like])
		if meta.has_field("status"):
			or_filters.append(["status", "like", like])

	start = max(0, cint(start))
	page_length = max(5, min(cint(page_length) or 20, 100))
	fields = ["name", "docstatus", "modified"]
	if branch_field and branch_field not in fields:
		fields.append(branch_field)
	for candidate in (
		definition["party_field"],
		date_field,
		"status",
		"grand_total",
		"currency",
		"shipping_rule",
		"delivery_status",
		"per_delivered",
		"per_billed",
		"advance_paid",
		"outstanding_amount",
		"update_stock",
		"is_return",
	):
		if candidate not in fields and meta.has_field(candidate):
			fields.append(candidate)

	rows = frappe.get_list(
		doctype,
		filters=filters,
		or_filters=or_filters,
		fields=fields,
		order_by=f"{date_field} desc, modified desc",
		limit_start=start,
		limit_page_length=page_length + 1,
	)
	has_more = len(rows) > page_length
	rows = rows[:page_length]
	result_rows: list[dict[str, Any]] = []
	for row in rows:
		payload = dict(row)
		payload["branch"] = str(payload.get(branch_field) or branch or "").strip() if branch_field else branch
		payload["actions"] = _selling_record_actions(definition["key"], payload)
		result_rows.append(payload)
	return {
		"document": definition["key"],
		"doctype": doctype,
		"label": definition["label"],
		"date_field": date_field,
		"party_field": definition["party_field"],
		"rows": result_rows,
		"start": start,
		"page_length": page_length,
		"next_start": start + len(rows),
		"has_more": has_more,
		"filters": {
			"search": search_text,
			"status": str(status or "All"),
			"from_date": from_text,
			"to_date": to_text,
		},
	}


@frappe.whitelist()
def _delivery_has_direct_sales_order_billing(delivery) -> bool:
	sales_orders = {
		str(row.get("against_sales_order") or "").strip()
		for row in list(delivery.get("items") or [])
		if str(row.get("against_sales_order") or "").strip()
	}
	if not sales_orders:
		return False
	rows = frappe.db.sql(
		"""
		SELECT si.name
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` item ON item.parent = si.name
		WHERE si.docstatus = 1
			AND COALESCE(si.is_return, 0) = 0
			AND item.sales_order IN %(sales_orders)s
			AND COALESCE(item.delivery_note, '') = ''
		LIMIT 1
		""",
		{"sales_orders": tuple(sales_orders)},
	)
	return bool(rows)

def get_professional_selling_record_actions(document: str, name: str) -> dict[str, Any]:
	"""Resolve permitted next actions for one visible Professional Selling record."""
	document = str(document or "").strip()
	name = str(name or "").strip()
	if not name:
		frappe.throw(_("Document name is required."))

	result = get_professional_selling_list(
		document=document,
		search=name,
		status="All",
		start=0,
		page_length=20,
	)
	row = next((row for row in result.get("rows") or [] if str(row.get("name") or "") == name), None)
	if not row:
		frappe.throw(
			_("The selected document is not available in your current Company/Branch context."),
			frappe.PermissionError,
		)
	actions = list(row.get("actions") or [])
	if document == "delivery-note":
		delivery = frappe.get_doc("Delivery Note", name)
		invoice_sourced = any(str(row.get("against_sales_invoice") or "").strip() for row in delivery.get("items") or [])
		direct_order_billing = _delivery_has_direct_sales_order_billing(delivery)
		if invoice_sourced or direct_order_billing:
			actions = [action for action in actions if action.get("value") != "create-sales-invoice"]

	return {
		"document": document,
		"doctype": result.get("doctype"),
		"name": name,
		"actions": actions,
	}
