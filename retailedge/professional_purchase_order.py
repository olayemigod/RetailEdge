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
	resolve_branch_from_warehouse,
	resolve_retailedge_operational_defaults,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.guided_pricing import resolve_price_list_context, resolve_purchase_item_pricing
from retailedge.guided_purchase_invoice import (
	MAX_ITEMS,
	MAX_LINK_RESULTS,
	_assert_read_permission,
	_branch_search_filters,
	_coerce_values,
	_normalise_items,
	_validate_transaction_context,
	_warehouse_search_filters,
)

PURCHASE_ORDER_DOCTYPE = "Purchase Order"
PURCHASE_ORDER_ITEM_DOCTYPE = "Purchase Order Item"


def _assert_can_create_purchase_order() -> None:
	if not has_doctype(PURCHASE_ORDER_DOCTYPE) or not frappe.has_permission(PURCHASE_ORDER_DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Purchase Order."), frappe.PermissionError)


def _validate_purchase_order_context(values: dict[str, Any], *, user: str) -> tuple[str, str, str]:
	"""Validate Company/Branch/Warehouse and require branch attribution for restricted users."""
	company, branch, warehouse = _validate_transaction_context(values, user=user)

	if warehouse:
		resolved = resolve_branch_from_warehouse(warehouse, company=company) or {}
		warehouse_branch = str(resolved.get("branch") or "").strip()
		if warehouse_branch:
			validate_user_branch_access(warehouse_branch, user=user, company=company, throw=True)
			if branch and warehouse_branch != branch:
				frappe.throw(_("Stock Location {0} does not belong to Branch {1}.").format(warehouse, branch))
			branch = branch or warehouse_branch

	if not branch and not user_has_global_branch_access(user=user):
		allowed = list(get_user_allowed_branches(user=user, company=company).get("branches") or [])
		if len(allowed) == 1:
			branch = str(allowed[0] or "").strip()
		else:
			frappe.throw(_("Choose a permitted Branch before creating a Purchase Order."))

	if branch:
		validate_user_branch_access(branch, user=user, company=company, throw=True)
		if warehouse:
			# Repeat the established branch/warehouse validator after any server-side
			# Branch derivation so clearing Branch on the client cannot weaken scope.
			_validate_transaction_context(
				{"company": company, "branch": branch, "warehouse": warehouse},
				user=user,
			)
	return company, branch, warehouse


def _set_branch(doc, branch: str) -> str:
	branch = str(branch or "").strip()
	if not branch:
		return ""
	fieldname = get_first_existing_field(PURCHASE_ORDER_DOCTYPE, BRANCH_FIELD_CANDIDATES)
	if not fieldname:
		frappe.throw(
			_("Purchase Order branch attribution is unavailable. Run site migration before using Branch-scoped guided purchasing.")
		)
	doc.set(fieldname, branch)
	return fieldname


@frappe.whitelist()
def get_professional_purchase_order_context() -> dict[str, Any]:
	"""Return permission-aware defaults for one guided ERPNext Purchase Order draft."""
	_assert_can_create_purchase_order()
	user = frappe.session.user
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	defaults = resolve_retailedge_operational_defaults(
		company=company or None,
		branch=branch or None,
		user=user,
	)
	company = str(defaults.get("company") or company or "").strip()
	branch = str(defaults.get("branch") or branch or "").strip()
	if not company:
		frappe.throw(_("Set an Operating Company before creating a Purchase Order."))
	_assert_read_permission("Company", company)

	warehouse = str(
		defaults.get("default_target_warehouse")
		or defaults.get("default_warehouse")
		or defaults.get("warehouse")
		or ""
	).strip()
	company, branch, warehouse = _validate_purchase_order_context(
		{"company": company, "branch": branch, "warehouse": warehouse},
		user=user,
	)

	pricing = resolve_price_list_context(
		mode="buying",
		company=company,
		branch=branch,
		user=user,
	)
	return {
		"title": _("New Purchase Order"),
		"subtitle": _("Prepare a standard ERPNext Purchase Order draft with supplier, receiving location and buying-price controls."),
		"submit_label": _("Save Draft Order"),
		"full_form_doctype": PURCHASE_ORDER_DOCTYPE,
		"pricing": pricing,
		"defaults": {
			"company": company,
			"branch": branch,
			"warehouse": warehouse,
			"supplier": "",
			"transaction_date": nowdate(),
			"schedule_date": nowdate(),
			"terms": "",
			"items": [{"item_code": "", "qty": 1, "rate": ""}],
		},
		"capabilities": {
			"branch_enabled": bool(has_doctype("Branch")),
			"can_create_supplier": bool(has_doctype("Supplier") and frappe.has_permission("Supplier", "create")),
			"can_create_item": bool(has_doctype("Item") and frappe.has_permission("Item", "create")),
			"native_form_fallback": True,
		},
		"limits": {"link_results": MAX_LINK_RESULTS, "max_items": MAX_ITEMS},
	}


@frappe.whitelist()
def search_professional_purchase_order_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	"""Search only permitted Purchase Order dependencies for the current operating scope."""
	_assert_can_create_purchase_order()
	values = _coerce_values(values)
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	branch = str(values.get("branch") or "").strip()
	supplier = str(values.get("supplier") or "").strip()

	if fieldname == "supplier":
		return list(
			search_link(
				"Supplier",
				txt or "",
				page_length=limit,
				reference_doctype=PURCHASE_ORDER_DOCTYPE,
				link_fieldname="supplier",
			)
		)
	if fieldname == "item_code":
		filters: dict[str, Any] = {"is_purchase_item": 1, "disabled": 0}
		if supplier:
			filters["supplier"] = supplier
		return list(
			search_link(
				"Item",
				txt or "",
				query="erpnext.controllers.queries.item_query",
				filters=filters,
				page_length=limit,
				reference_doctype=PURCHASE_ORDER_ITEM_DOCTYPE,
				link_fieldname="item_code",
			)
		)
	if fieldname == "warehouse":
		filters = _warehouse_search_filters(company=company, branch=branch, user=frappe.session.user)
		if filters is None:
			return []
		return list(
			search_link(
				"Warehouse",
				txt or "",
				filters=filters,
				page_length=limit,
				reference_doctype=PURCHASE_ORDER_DOCTYPE,
				link_fieldname="set_warehouse",
			)
		)
	if fieldname == "branch":
		if not has_doctype("Branch"):
			return []
		branch_field = get_first_existing_field(PURCHASE_ORDER_DOCTYPE, BRANCH_FIELD_CANDIDATES) or "retailedge_branch"
		return list(
			search_link(
				"Branch",
				txt or "",
				filters=_branch_search_filters(company=company, user=frappe.session.user),
				page_length=limit,
				reference_doctype=PURCHASE_ORDER_DOCTYPE,
				link_fieldname=branch_field,
			)
		)
	frappe.throw(_("Unsupported guided Purchase Order search field: {0}").format(fieldname))
	return []


@frappe.whitelist()
def get_professional_purchase_order_item_pricing(
	item_code: str,
	values: dict | str | None = None,
) -> dict[str, Any]:
	"""Resolve the current ERPNext buying rate without trusting a client-selected Price List."""
	_assert_can_create_purchase_order()
	values = _coerce_values(values)
	user = frappe.session.user
	company, branch, warehouse = _validate_purchase_order_context(values, user=user)
	supplier = str(values.get("supplier") or "").strip()
	if not supplier:
		frappe.throw(_("Select a Supplier before pricing Purchase Order items."))
	_assert_read_permission("Supplier", supplier)
	item_code = str(item_code or "").strip()
	_assert_read_permission("Item", item_code)
	return resolve_purchase_item_pricing(
		item_code=item_code,
		company=company,
		supplier=supplier,
		branch=branch,
		warehouse=warehouse,
		posting_date=values.get("transaction_date") or nowdate(),
		qty=flt(values.get("qty") or 1),
		user=user,
	)


@frappe.whitelist(methods=["POST"])
def create_professional_purchase_order_draft(values: dict | str | None = None) -> dict[str, Any]:
	"""Create one standard ERPNext Purchase Order draft; never submit or post stock/accounting."""
	_assert_can_create_purchase_order()
	values = _coerce_values(values)
	user = frappe.session.user
	company, branch, warehouse = _validate_purchase_order_context(values, user=user)

	supplier = str(values.get("supplier") or "").strip()
	if not supplier:
		frappe.throw(_("Supplier is required."))
	_assert_read_permission("Supplier", supplier)
	items = _normalise_items(values.get("items"))

	transaction_date = getdate(values.get("transaction_date") or nowdate())
	schedule_date = getdate(values.get("schedule_date") or transaction_date)
	if schedule_date < transaction_date:
		frappe.throw(_("Required By date cannot be before the Order Date."))

	pricing_context = resolve_price_list_context(
		mode="buying",
		company=company,
		branch=branch,
		party=supplier,
		user=user,
	)

	doc = frappe.new_doc(PURCHASE_ORDER_DOCTYPE)
	doc.company = company
	doc.supplier = supplier
	doc.transaction_date = transaction_date
	if doc.meta.has_field("schedule_date"):
		doc.schedule_date = schedule_date
	if warehouse and doc.meta.has_field("set_warehouse"):
		doc.set_warehouse = warehouse
	if pricing_context.get("price_list") and doc.meta.has_field("buying_price_list"):
		doc.buying_price_list = pricing_context["price_list"]
	if values.get("terms") and doc.meta.has_field("terms"):
		doc.terms = str(values.get("terms") or "").strip()
	branch_field = _set_branch(doc, branch)

	for item in items:
		_assert_read_permission("Item", item["item_code"])
		resolved = resolve_purchase_item_pricing(
			item_code=item["item_code"],
			company=company,
			supplier=supplier,
			branch=branch,
			warehouse=warehouse,
			posting_date=str(transaction_date),
			qty=item["qty"],
			user=user,
		)
		manual_rate = item.get("rate")
		resolved_rate = resolved.get("rate")
		effective_rate = manual_rate if manual_rate is not None else resolved_rate
		if effective_rate is None:
			frappe.throw(
				_("No buying price could be resolved for Item {0}. Set a Buying Item Price or enter the agreed buying rate before saving.").format(item["item_code"])
			)
		row: dict[str, Any] = {
			"item_code": item["item_code"],
			"qty": item["qty"],
			"rate": effective_rate,
			"schedule_date": schedule_date,
		}
		if warehouse:
			row["warehouse"] = warehouse
		doc.append("items", row)

	# Draft-only. ERPNext Purchase Order validation remains authoritative for supplier,
	# UOM, taxes, terms, item eligibility and all later receiving/billing behavior.
	doc.insert()
	if cint(doc.docstatus) != 0:
		frappe.throw(_("Guided purchasing may create only a draft Purchase Order."))
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": cint(doc.docstatus),
		"supplier": doc.supplier,
		"company": doc.company,
		"branch": doc.get(branch_field) if branch_field else "",
		"buying_price_list": doc.get("buying_price_list") or pricing_context.get("price_list") or "",
		"grand_total": doc.grand_total,
		"currency": doc.currency,
		"item_count": len(items),
		"posting_status": "Draft",
		"source_of_truth": "ERPNext Purchase Order",
		"route": f"/app/purchase-order/{doc.name}",
	}
