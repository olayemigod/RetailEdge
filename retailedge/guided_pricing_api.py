from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from retailedge.guided_pricing import resolve_purchase_item_pricing, resolve_sales_item_pricing
from retailedge.guided_purchase_invoice import (
	MAX_ITEMS as PURCHASE_MAX_ITEMS,
	_assert_can_create_purchase_invoice,
	_assert_read_permission as _assert_purchase_read_permission,
	_coerce_values as _coerce_purchase_values,
	_validate_transaction_context as _validate_purchase_context,
)
from retailedge.guided_sales_invoice import (
	MAX_ITEMS as SALES_MAX_ITEMS,
	_assert_can_create_sales_invoice,
	_assert_read_permission as _assert_sales_read_permission,
	_coerce_values as _coerce_sales_values,
	_validate_transaction_context as _validate_sales_context,
)


@frappe.whitelist()
def get_sales_item_pricing_batch(
	items: list[dict[str, Any]] | str | None = None,
	values: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	"""Resolve guided Sales Invoice item prices in one bounded HTTP request."""
	_assert_can_create_sales_invoice()
	values = _coerce_sales_values(values)
	rows = _normalise_pricing_rows(items, max_items=SALES_MAX_ITEMS)
	user = frappe.session.user
	company, branch, warehouse = _validate_sales_context(values, user=user)
	customer = str(values.get("customer") or "").strip()
	if not customer:
		frappe.throw(_("Select a Customer before pricing items."))
	_assert_sales_read_permission("Customer", customer)

	results: list[dict[str, Any]] = []
	for row in rows:
		_assert_sales_read_permission("Item", row["item_code"])
		pricing = resolve_sales_item_pricing(
			item_code=row["item_code"],
			company=company,
			customer=customer,
			branch=branch,
			warehouse=warehouse,
			posting_date=values.get("posting_date") or nowdate(),
			qty=row["qty"],
			user=user,
		)
		results.append({"index": row["index"], **pricing})

	return {"rows": results, "count": len(results), "max_items": SALES_MAX_ITEMS}


@frappe.whitelist()
def get_purchase_item_pricing_batch(
	items: list[dict[str, Any]] | str | None = None,
	values: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	"""Resolve guided Purchase Invoice item prices in one bounded HTTP request."""
	_assert_can_create_purchase_invoice()
	values = _coerce_purchase_values(values)
	rows = _normalise_pricing_rows(items, max_items=PURCHASE_MAX_ITEMS)
	user = frappe.session.user
	company, branch, warehouse = _validate_purchase_context(values, user=user)
	supplier = str(values.get("supplier") or "").strip()
	if not supplier:
		frappe.throw(_("Select a Supplier before pricing items."))
	_assert_purchase_read_permission("Supplier", supplier)

	results: list[dict[str, Any]] = []
	for row in rows:
		_assert_purchase_read_permission("Item", row["item_code"])
		pricing = resolve_purchase_item_pricing(
			item_code=row["item_code"],
			company=company,
			supplier=supplier,
			branch=branch,
			warehouse=warehouse,
			posting_date=values.get("posting_date") or nowdate(),
			qty=row["qty"],
			user=user,
		)
		results.append({"index": row["index"], **pricing})

	return {"rows": results, "count": len(results), "max_items": PURCHASE_MAX_ITEMS}


def _normalise_pricing_rows(
	items: list[dict[str, Any]] | str | None,
	*,
	max_items: int,
) -> list[dict[str, Any]]:
	if isinstance(items, str):
		items = frappe.parse_json(items)
	if not isinstance(items, list):
		frappe.throw(_("Pricing items must be a list."))
	if len(items) > max_items:
		frappe.throw(_("At most {0} items can be priced at once.").format(max_items))

	rows: list[dict[str, Any]] = []
	for position, item in enumerate(items):
		if not isinstance(item, dict):
			frappe.throw(_("Pricing item row {0} is invalid.").format(position + 1))
		item_code = str(item.get("item_code") or "").strip()
		if not item_code:
			continue
		qty_value = item.get("qty")
		qty = flt(1 if qty_value in (None, "") else qty_value)
		if qty <= 0:
			frappe.throw(_("Quantity for Item {0} must be greater than zero.").format(item_code))
		index = item.get("index")
		try:
			index = int(index) if index is not None else position
		except (TypeError, ValueError):
			index = position
		rows.append({"index": index, "item_code": item_code, "qty": qty})
	return rows
