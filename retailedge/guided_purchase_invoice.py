from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt, getdate, nowdate

from retailedge.branch_assignment import has_branch_assignments
from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	get_first_existing_field,
	has_doctype,
	has_field,
	resolve_retailedge_operational_defaults,
	validate_user_branch_access,
)
from retailedge.branch_profile import get_branch_profile, get_branch_profile_defaults
from retailedge.guided_pricing import resolve_price_list_context, resolve_purchase_item_pricing
from retailedge.operating_context import get_operational_branch_scope, resolve_operational_branch

ACTION_KEY = "record-purchase"
PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"
MAX_LINK_RESULTS = 20
MAX_ITEMS = 50


@frappe.whitelist()
def get_simple_purchase_invoice_context() -> dict[str, Any]:
	_assert_can_create_purchase_invoice()
	user = frappe.session.user
	company = frappe.defaults.get_user_default("Company") or ""
	legacy_default_branch = (
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	)
	if not company:
		frappe.throw(_("Set a default Company before creating a Purchase Invoice."))
	_assert_read_permission("Company", company)

	scope = get_operational_branch_scope(company, user=user)
	if scope["restricted"]:
		if len(scope["allowed_branches"]) <= 1:
			branch = _resolve_guided_branch(company=company, branch="", user=user)
		else:
			branch = ""
	else:
		branch = str(legacy_default_branch or "").strip()
		if branch:
			branch = _resolve_guided_branch(company=company, branch=branch, user=user)

	defaults = resolve_retailedge_operational_defaults(
		company=company or None,
		branch=branch or None,
		user=user,
	)
	company = defaults.get("company") or company
	_assert_read_permission("Company", company)
	if branch:
		branch = _resolve_guided_branch(company=company, branch=branch, user=user)
	elif not scope["restricted"] and defaults.get("branch"):
		branch = _resolve_guided_branch(
			company=company,
			branch=defaults.get("branch") or "",
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
		_validate_branch_warehouse(branch=branch, warehouse=warehouse, company=company, user=user)

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
			"update_stock": 0,
			"remarks": "",
			"items": [{"item_code": "", "qty": 1, "rate": ""}],
		},
		"capabilities": {
			"branch_enabled": bool(has_doctype("Branch")),
			"can_create_supplier": bool(
				has_doctype("Supplier") and frappe.has_permission("Supplier", "create")
			),
			"can_create_item": bool(has_doctype("Item") and frappe.has_permission("Item", "create")),
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
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
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
	update_stock = cint(values.get("update_stock") or 0)
	if update_stock and not warehouse:
		frappe.throw(_("Warehouse is required when Update Stock is enabled."))

	pricing_context = resolve_price_list_context(
		mode="buying", company=company, branch=branch, party=supplier, user=user
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
	# from the authenticated user's setup and ERPNext's item-pricing service.
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
	branch = str(branch or "").strip()
	# Explicit Branch values keep the established legacy validation path until a
	# user has Branch Assignment history. Assignment-backed users and every blank-
	# Branch write use the explicit operational-scope resolver.
	if branch and not has_branch_assignments(user=user):
		validate_user_branch_access(branch, user=user, company=company, throw=True)
		return branch
	return str(resolve_operational_branch(company, branch, user=user).get("branch") or "").strip()


def _validate_transaction_context(values: dict[str, Any], *, user: str) -> tuple[str, str, str]:
	company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	_assert_read_permission("Company", company)

	branch = _resolve_guided_branch(
		company=company,
		branch=str(values.get("branch") or "").strip(),
		user=user,
	)

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
	if not company:
		return None
	filters: dict[str, Any] = {"is_group": 0}
	if has_field("Warehouse", "company"):
		filters["company"] = company
	branch = str(branch or "").strip()
	if not branch:
		scope = get_operational_branch_scope(company, user=user)
		if not scope["restricted"]:
			return filters
		if len(scope["allowed_branches"]) > 1:
			return None
	branch = _resolve_guided_branch(company=company, branch=branch, user=user)
	if not branch:
		return filters

	branch_field = get_first_existing_field("Warehouse", BRANCH_FIELD_CANDIDATES)
	if branch_field:
		filters[branch_field] = branch
		return filters

	profile_defaults = get_branch_profile_defaults(company=company or None, branch=branch, user=user)
	warehouses = _unique(
		[
			profile_defaults.get("default_target_warehouse"),
			profile_defaults.get("default_warehouse"),
			profile_defaults.get("default_source_warehouse"),
			profile_defaults.get("default_returns_warehouse"),
		]
	)
	if not warehouses:
		return None
	filters["name"] = ["in", warehouses]
	return filters


def _branch_search_filters(company: str, user: str) -> dict[str, Any]:
	if not company:
		return {"name": "__never__"}
	filters: dict[str, Any] = {}
	if has_field("Branch", "company"):
		filters["company"] = company
	scope = get_operational_branch_scope(company, user=user)
	if scope["restricted"]:
		filters["name"] = ["in", scope["allowed_branches"]] if scope["allowed_branches"] else "__never__"
	return filters


def _validate_branch_warehouse(*, branch: str, warehouse: str, company: str, user: str) -> None:
	branch_field = get_first_existing_field("Warehouse", BRANCH_FIELD_CANDIDATES)
	if branch_field:
		warehouse_branch = frappe.db.get_value("Warehouse", warehouse, branch_field)
		if warehouse_branch and warehouse_branch != branch:
			frappe.throw(
				_("Warehouse {0} belongs to Branch {1}, not Branch {2}.").format(
					warehouse, warehouse_branch, branch
				)
			)
		if warehouse_branch:
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


def _unique(values: list[str | None]) -> list[str]:
	seen: set[str] = set()
	result: list[str] = []
	for value in values:
		if value and value not in seen:
			seen.add(value)
			result.append(value)
	return result
