from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.branch_context import resolve_branch_from_warehouse
from retailedge.guided_pricing import resolve_sales_item_pricing
from retailedge.professional_selling import _assert_read


MAX_DRAFT_ITEMS = 100
SOURCE_LINK_FIELDS = (
	"quotation_item",
	"prevdoc_docname",
	"sales_order",
	"so_detail",
	"against_sales_order",
	"sales_invoice",
	"against_sales_invoice",
	"si_detail",
	"delivery_note",
	"dn_detail",
)


def clean(value: Any) -> str:
	return str(value or "").strip()


def editable_items(doc) -> list[dict[str, Any]]:
	return [
		{
			"name": clean(row.get("name")),
			"item_code": clean(row.get("item_code")),
			"item_name": clean(row.get("item_name")),
			"qty": flt(row.get("qty")),
			"rate": flt(row.get("rate")),
			"amount": flt(row.get("amount")),
			"warehouse": clean(row.get("warehouse")),
			"delivery_date": clean(row.get("delivery_date")),
			"source_locked": _source_linked(row),
		}
		for row in list(doc.get("items") or [])
	]


def update_draft_items(
	doc,
	requested_items: Any,
	*,
	company: str,
	branch: str,
	customer: str,
	posting_date: str,
	default_warehouse: str = "",
	default_delivery_date: str = "",
	selected_price_list: str = "",
) -> None:
	if isinstance(requested_items, str):
		requested_items = frappe.parse_json(requested_items)
	if not isinstance(requested_items, list) or not requested_items:
		frappe.throw(_("Add at least one item."))
	if len(requested_items) > MAX_DRAFT_ITEMS:
		frappe.throw(_("A draft can contain at most {0} items here.").format(MAX_DRAFT_ITEMS))

	current_rows = {
		clean(row.get("name")): row
		for row in list(doc.get("items") or [])
		if clean(row.get("name"))
	}
	requested_existing: set[str] = set()

	for index, item in enumerate(requested_items, start=1):
		if not isinstance(item, dict):
			frappe.throw(_("Item row {0} is invalid.").format(index))
		row_name = clean(item.get("name"))
		if row_name:
			row = current_rows.get(row_name)
			if not row:
				frappe.throw(_("Item row {0} is no longer part of this draft. Refresh and try again.").format(index))
			if row_name in requested_existing:
				frappe.throw(_("Item row {0} is repeated.").format(index))
			requested_existing.add(row_name)
			requested_code = clean(item.get("item_code"))
			if requested_code and requested_code != clean(row.get("item_code")):
				frappe.throw(_("Existing item identity cannot be replaced here. Add a new item row instead."))
			_apply_editable_row_values(
				row,
				item,
				index=index,
				company=company,
				branch=branch,
				customer=customer,
				posting_date=posting_date,
				default_warehouse=default_warehouse,
				default_delivery_date=default_delivery_date,
				selected_price_list=selected_price_list,
			)
			continue

		item_code = clean(item.get("item_code"))
		if not item_code:
			frappe.throw(_("Item is required on new row {0}.").format(index))
		_assert_read("Item", item_code)
		row = doc.append("items", {"item_code": item_code})
		_apply_editable_row_values(
			row,
			item,
			index=index,
			company=company,
			branch=branch,
			customer=customer,
			posting_date=posting_date,
			default_warehouse=default_warehouse,
			default_delivery_date=default_delivery_date,
			selected_price_list=selected_price_list,
		)

	for row_name, row in list(current_rows.items()):
		if row_name in requested_existing:
			continue
		if _source_linked(row):
			frappe.throw(
				_("Source-linked item {0} cannot be removed here. Adjust its quantity or use the full form.").format(
					clean(row.get("item_code")) or row_name
				)
			)
		doc.remove(row)

	if hasattr(doc, "set_missing_values"):
		doc.set_missing_values()


def _apply_editable_row_values(
	row,
	values: dict[str, Any],
	*,
	index: int,
	company: str,
	branch: str,
	customer: str,
	posting_date: str,
	default_warehouse: str,
	default_delivery_date: str,
	selected_price_list: str,
) -> None:
	qty = flt(values.get("qty"))
	if qty <= 0:
		frappe.throw(_("Quantity on row {0} must be greater than zero.").format(index))
	row.qty = qty

	warehouse = clean(values.get("warehouse") or row.get("warehouse") or default_warehouse)
	if warehouse:
		_assert_read("Warehouse", warehouse)
		_validate_warehouse_branch(warehouse, company=company, branch=branch)
		if row.meta.has_field("warehouse"):
			row.warehouse = warehouse

	rate_value = values.get("rate")
	if rate_value in (None, ""):
		rate = _resolve_rate(
			item_code=clean(row.get("item_code")),
			company=company,
			customer=customer,
			branch=branch,
			warehouse=warehouse,
			posting_date=posting_date,
			qty=qty,
			selected_price_list=selected_price_list,
		)
	else:
		rate = flt(rate_value)
	if rate < 0:
		frappe.throw(_("Rate on row {0} cannot be negative.").format(index))
	if row.meta.has_field("rate"):
		row.rate = rate

	if row.meta.has_field("delivery_date"):
		delivery_date = clean(values.get("delivery_date") or row.get("delivery_date") or default_delivery_date)
		if delivery_date:
			row.delivery_date = delivery_date


def _resolve_rate(
	*,
	item_code: str,
	company: str,
	customer: str,
	branch: str,
	warehouse: str,
	posting_date: str,
	qty: float,
	selected_price_list: str = "",
) -> float:
	if not item_code:
		return 0.0
	resolved = resolve_sales_item_pricing(
		item_code=item_code,
		company=company,
		customer=customer,
		branch=branch,
		warehouse=warehouse,
		posting_date=posting_date,
		qty=qty,
		selected_price_list=selected_price_list,
		user=frappe.session.user,
	)
	rate = resolved.get("rate")
	if rate is None:
		frappe.throw(
			_("No selling price could be resolved for Item {0}. Enter a rate before saving.").format(item_code)
		)
	return flt(rate)


def _validate_warehouse_branch(warehouse: str, *, company: str, branch: str) -> None:
	warehouse_company = clean(frappe.db.get_value("Warehouse", warehouse, "company"))
	if warehouse_company and warehouse_company != company:
		frappe.throw(_("Stock Location {0} does not belong to Company {1}.").format(warehouse, company))
	if not branch:
		return
	resolved = resolve_branch_from_warehouse(warehouse, company=company) or {}
	warehouse_branch = clean(resolved.get("branch"))
	if warehouse_branch and warehouse_branch != branch:
		frappe.throw(_("Stock Location {0} does not belong to Branch {1}.").format(warehouse, branch))


def _source_linked(row) -> bool:
	return any(clean(row.get(fieldname)) for fieldname in SOURCE_LINK_FIELDS if row.meta.has_field(fieldname))
