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
	resolve_retailedge_operational_defaults,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.branch_profile import get_branch_profile, get_branch_profile_defaults

ACTION_KEY = "transfer-stock"
STOCK_ENTRY_DOCTYPE = "Stock Entry"
MATERIAL_TRANSFER = "Material Transfer"
MAX_LINK_RESULTS = 20
MAX_ITEMS = 50


@frappe.whitelist()
def get_simple_stock_transfer_context() -> dict[str, Any]:
	_assert_can_create_stock_entry()
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
		frappe.throw(_("Set a default Company before creating a Stock Transfer."))
	_assert_read_permission("Company", company)
	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)

	source_warehouse = (
		defaults.get("default_source_warehouse")
		or defaults.get("default_warehouse")
		or ""
	)
	target_warehouse = defaults.get("default_target_warehouse") or ""
	if source_warehouse and branch:
		_validate_branch_warehouse(
			branch=branch,
			warehouse=source_warehouse,
			company=company,
			user=user,
		)
	if target_warehouse and branch:
		_validate_branch_warehouse(
			branch=branch,
			warehouse=target_warehouse,
			company=company,
			user=user,
		)
	if target_warehouse == source_warehouse:
		target_warehouse = ""

	return {
		"action_key": ACTION_KEY,
		"title": _("Simple Stock Transfer"),
		"subtitle": _(
			"Create a standard ERPNext Material Transfer draft between permitted warehouses."
		),
		"submit_label": _("Save Draft"),
		"full_form_doctype": STOCK_ENTRY_DOCTYPE,
		"defaults": {
			"company": company,
			"posting_date": nowdate(),
			"source_branch": branch or "",
			"target_branch": branch or "",
			"source_warehouse": source_warehouse,
			"target_warehouse": target_warehouse,
			"remarks": "",
			"items": [{"item_code": "", "qty": 1}],
		},
		"capabilities": {
			"branch_enabled": bool(has_doctype("Branch")),
			"native_form_fallback": True,
			"serial_batch_requires_full_form": True,
		},
		"limits": {"link_results": MAX_LINK_RESULTS, "max_items": MAX_ITEMS},
	}


@frappe.whitelist()
def search_simple_stock_transfer_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_can_create_stock_entry()
	values = _coerce_values(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	source_branch = values.get("source_branch") or ""
	target_branch = values.get("target_branch") or ""

	if fieldname == "item_code":
		return search_link(
			"Item",
			txt or "",
			query="erpnext.controllers.queries.item_query",
			filters={"is_stock_item": 1, "disabled": 0},
			page_length=limit,
			reference_doctype="Stock Entry Detail",
			link_fieldname="item_code",
		)
	if fieldname in {"source_warehouse", "target_warehouse"}:
		branch = source_branch if fieldname == "source_warehouse" else target_branch
		filters = _warehouse_search_filters(company=company, branch=branch, user=frappe.session.user)
		if filters is None:
			return []
		return search_link(
			"Warehouse",
			txt or "",
			filters=filters,
			page_length=limit,
			reference_doctype=STOCK_ENTRY_DOCTYPE,
			link_fieldname="from_warehouse" if fieldname == "source_warehouse" else "to_warehouse",
		)
	if fieldname in {"source_branch", "target_branch"}:
		if not has_doctype("Branch"):
			return []
		return search_link(
			"Branch",
			txt or "",
			filters=_branch_search_filters(company=company, user=frappe.session.user),
			page_length=limit,
			reference_doctype=STOCK_ENTRY_DOCTYPE,
			link_fieldname="retailedge_branch",
		)
	frappe.throw(_("Unsupported Simple Stock Transfer search field: {0}").format(fieldname))
	return []


@frappe.whitelist(methods=["POST"])
def create_simple_stock_transfer_draft(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_create_stock_entry()
	values = _coerce_values(values)
	user = frappe.session.user
	company = values.get("company") or frappe.defaults.get_user_default("Company") or ""
	if not company:
		frappe.throw(_("Company is required."))
	_assert_read_permission("Company", company)

	source_branch = values.get("source_branch") or ""
	target_branch = values.get("target_branch") or ""
	for branch in {source_branch, target_branch} - {""}:
		validate_user_branch_access(branch, user=user, company=company, throw=True)

	source_warehouse = str(values.get("source_warehouse") or "").strip()
	target_warehouse = str(values.get("target_warehouse") or "").strip()
	if not source_warehouse or not target_warehouse:
		frappe.throw(_("Source Warehouse and Target Warehouse are required."))
	if source_warehouse == target_warehouse:
		frappe.throw(_("Source Warehouse and Target Warehouse must be different."))
	for warehouse, branch in (
		(source_warehouse, source_branch),
		(target_warehouse, target_branch),
	):
		_assert_read_permission("Warehouse", warehouse)
		warehouse_company = frappe.db.get_value("Warehouse", warehouse, "company")
		if warehouse_company and warehouse_company != company:
			frappe.throw(_("Warehouse {0} does not belong to Company {1}.").format(warehouse, company))
		if branch:
			_validate_branch_warehouse(
				branch=branch,
				warehouse=warehouse,
				company=company,
				user=user,
			)

	items = _normalise_items(values.get("items"))
	for item in items:
		_assert_simple_stock_item(item["item_code"])

	doc = frappe.new_doc(STOCK_ENTRY_DOCTYPE)
	doc.company = company
	doc.purpose = MATERIAL_TRANSFER
	doc.stock_entry_type = MATERIAL_TRANSFER
	doc.posting_date = getdate(values.get("posting_date") or nowdate())
	doc.from_warehouse = source_warehouse
	doc.to_warehouse = target_warehouse
	if values.get("remarks"):
		doc.remarks = str(values.get("remarks")).strip()

	for item in items:
		doc.append(
			"items",
			{
				"item_code": item["item_code"],
				"qty": item["qty"],
				"s_warehouse": source_warehouse,
				"t_warehouse": target_warehouse,
			},
		)

	# Insert as the current user. ERPNext's Stock Entry controller owns item/UOM
	# defaults, valuation, stock validation and all eventual ledger posting on submit.
	doc.insert()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"purpose": doc.purpose,
		"company": doc.company,
		"source_warehouse": doc.from_warehouse,
		"target_warehouse": doc.to_warehouse,
		"route": f"/app/stock-entry/{doc.name}",
	}


def _normalise_items(items: Any) -> list[dict[str, Any]]:
	if isinstance(items, str):
		items = frappe.parse_json(items)
	if not isinstance(items, list) or not items:
		frappe.throw(_("Add at least one stock item."))
	if len(items) > MAX_ITEMS:
		frappe.throw(_("A Simple Stock Transfer can contain at most {0} items.").format(MAX_ITEMS))

	result: list[dict[str, Any]] = []
	for index, item in enumerate(items, start=1):
		if not isinstance(item, dict):
			frappe.throw(_("Stock item row {0} is invalid.").format(index))
		item_code = str(item.get("item_code") or "").strip()
		if not item_code:
			frappe.throw(_("Item is required on row {0}.").format(index))
		qty = flt(item.get("qty"))
		if qty <= 0:
			frappe.throw(_("Quantity on row {0} must be greater than zero.").format(index))
		result.append({"item_code": item_code, "qty": qty})
	return result


def _assert_simple_stock_item(item_code: str) -> None:
	_assert_read_permission("Item", item_code)
	row = frappe.db.get_value(
		"Item",
		item_code,
		["is_stock_item", "disabled", "has_serial_no", "has_batch_no"],
		as_dict=True,
	)
	if not row or not cint(row.is_stock_item) or cint(row.disabled):
		frappe.throw(_("Item {0} is not an active stock item.").format(item_code))
	if cint(row.has_serial_no) or cint(row.has_batch_no):
		frappe.throw(
			_(
				"Item {0} uses Serial No or Batch tracking. Use the full Stock Entry form for this transfer."
			).format(item_code)
		)


def _warehouse_search_filters(company: str, branch: str, user: str) -> dict[str, Any] | None:
	filters: dict[str, Any] = {"is_group": 0, "disabled": 0}
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
			profile_defaults.get("default_target_warehouse"),
			profile_defaults.get("default_warehouse"),
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


def _assert_can_create_stock_entry() -> None:
	if not has_doctype(STOCK_ENTRY_DOCTYPE) or not frappe.has_permission(STOCK_ENTRY_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Stock Entries."), frappe.PermissionError)


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
	frappe.throw(_("Invalid Simple Stock Transfer values."))
	return {}


def _unique(values: list[str | None]) -> list[str]:
	seen: set[str] = set()
	result: list[str] = []
	for value in values:
		if value and value not in seen:
			seen.add(value)
			result.append(value)
	return result
