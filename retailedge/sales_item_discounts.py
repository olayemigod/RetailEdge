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
) -> dict[str, Any]:
	"""Map explicit RetailEdge input onto native ERPNext Sales Invoice Item fields."""
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
	return discount


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
