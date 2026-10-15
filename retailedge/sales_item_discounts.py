from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt


MANUAL_DISCOUNT_PERCENTAGE = "manual_discount_percentage"
MANUAL_DISCOUNT_AMOUNT = "manual_discount_amount"


def normalise_manual_item_discount(values: dict[str, Any], *, index: int | None = None) -> dict[str, Any]:
	"""Return bounded manual line-discount input without touching ERPNext pricing truth.

	ERPNext Sales Invoice Item ``discount_amount`` is a per-unit discount against
	the item rate. RetailEdge keeps that native meaning and labels it accordingly.
	"""
	percentage_present = MANUAL_DISCOUNT_PERCENTAGE in values
	amount_present = MANUAL_DISCOUNT_AMOUNT in values
	percentage = flt(values.get(MANUAL_DISCOUNT_PERCENTAGE) or 0) if percentage_present else 0.0
	amount = flt(values.get(MANUAL_DISCOUNT_AMOUNT) or 0) if amount_present else 0.0
	label = _(" on row {0}").format(index) if index else ""

	if percentage < 0 or percentage > 100:
		frappe.throw(
			_("Manual Discount %{0} must be between 0 and 100.").format(label),
			frappe.ValidationError,
		)
	if amount < 0:
		frappe.throw(
			_("Discount per Unit{0} cannot be negative.").format(label),
			frappe.ValidationError,
		)
	if percentage and amount:
		frappe.throw(
			_("Use either Manual Discount % or Discount per Unit{0}, not both.").format(label),
			frappe.ValidationError,
		)

	return {
		MANUAL_DISCOUNT_PERCENTAGE: percentage,
		MANUAL_DISCOUNT_AMOUNT: amount,
		"supplied": bool(percentage_present or amount_present),
		"active": bool(percentage or amount),
	}


def apply_manual_item_discount(
	row,
	values: dict[str, Any],
	*,
	index: int | None = None,
	rate_locked: bool = False,
	lock_reason: str = "",
	price_list_rate: float | None = None,
) -> dict[str, Any]:
	"""Map explicit RetailEdge input onto native ERPNext Sales Invoice Item fields.

	ERPNext treats ``rate`` as the resolved post-discount line rate. RetailEdge's
	Selling Rate is the operator's pre-discount basis. When those values differ
	from the governed Price List, encode the Selling Rate with ERPNext's native
	Amount margin fields, then leave the final ``rate`` for ERPNext to calculate.
	If no Price List rate exists, the entered Selling Rate becomes the native
	price-list basis for this line so ERPNext can still calculate the discount.
	"""
	discount = normalise_manual_item_discount(values, index=index)
	if not discount["supplied"]:
		return discount
	if discount["active"] and rate_locked:
		item_code = str(row.get("item_code") or values.get("item_code") or "").strip()
		message = _("Manual line discount is not allowed for Item {0} because its selling rate is locked.").format(
			item_code or index or ""
		)
		if lock_reason:
			message = _("{0} {1}").format(message, lock_reason)
		frappe.throw(message, frappe.PermissionError)

	row.set("discount_percentage", discount[MANUAL_DISCOUNT_PERCENTAGE])
	row.set("discount_amount", discount[MANUAL_DISCOUNT_AMOUNT])
	if discount["active"]:
		_set_manual_discount_rate_basis(row, values, price_list_rate=price_list_rate)
	return discount


def _set_manual_discount_rate_basis(row, values: dict[str, Any], *, price_list_rate: float | None) -> None:
	"""Represent the entered Selling Rate with native ERPNext price/margin fields."""
	rate_value = values.get("rate")
	base_rate = flt(row.get("rate") if rate_value in (None, "") else rate_value)

	list_rate_value = price_list_rate
	if list_rate_value in (None, ""):
		list_rate_value = row.get("price_list_rate")
	list_rate = flt(list_rate_value or 0)

	if list_rate:
		row.set("price_list_rate", list_rate)
		margin_amount = flt(base_rate - list_rate)
		if margin_amount:
			row.set("margin_type", "Amount")
			row.set("margin_rate_or_amount", margin_amount)
		else:
			row.set("margin_type", "")
			row.set("margin_rate_or_amount", 0)
	elif base_rate:
		# ERPNext removes manual discount fields when price_list_rate is blank.
		# Use the entered Selling Rate as the native basis when no Item Price exists.
		row.set("price_list_rate", base_rate)
		row.set("margin_type", "")
		row.set("margin_rate_or_amount", 0)

	# ERPNext will resolve the final post-discount rate from the native basis above.
	row.set("rate", 0)


def manual_item_discount_state(row) -> dict[str, Any]:
	"""Expose manual input separately from automatic Pricing Rule discount output."""
	pricing_rule = str(row.get("pricing_rules") or row.get("pricing_rule") or "").strip()
	return {
		MANUAL_DISCOUNT_PERCENTAGE: 0.0 if pricing_rule else flt(row.get("discount_percentage") or 0),
		MANUAL_DISCOUNT_AMOUNT: 0.0 if pricing_rule else flt(row.get("discount_amount") or 0),
		"pricing_rule": pricing_rule,
	}


def validate_manual_item_discounts_after_pricing(doc, requested_items: Any) -> None:
	"""Fail closed when a manual line discount would override ERPNext promotion truth."""
	if isinstance(requested_items, str):
		requested_items = frappe.parse_json(requested_items)
	if not isinstance(requested_items, list):
		return

	requested = [row for row in requested_items if isinstance(row, dict) and str(row.get("item_code") or "").strip()]
	actual = [row for row in list(doc.get("items") or []) if not cint(row.get("is_free_item") or 0)]
	if len(requested) != len(actual):
		frappe.throw(
			_("The invoice items changed while validating discounts. Refresh the sale and try again."),
			frappe.ValidationError,
		)

	for index, (input_row, actual_row) in enumerate(zip(requested, actual), start=1):
		requested_code = str(input_row.get("item_code") or "").strip()
		actual_code = str(actual_row.get("item_code") or "").strip()
		if requested_code != actual_code:
			frappe.throw(
				_("The invoice item on row {0} changed while validating discounts. Refresh and try again.").format(index),
				frappe.ValidationError,
			)
		discount = normalise_manual_item_discount(input_row, index=index)
		if not discount["active"]:
			continue
		pricing_rule = str(actual_row.get("pricing_rules") or actual_row.get("pricing_rule") or "").strip()
		if pricing_rule:
			frappe.throw(
				_(
					"Item {0} already has an automatic promotion. Remove the manual line discount or review the Pricing Rule."
				).format(requested_code),
				frappe.ValidationError,
			)
