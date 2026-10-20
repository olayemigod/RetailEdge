from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt


def transaction_promotion_names(doc) -> list[str]:
	"""Return document-level Pricing Rules without treating item promotions as document promotions."""
	result: list[str] = []
	for row in list(doc.get("pricing_rules") or []):
		name = str(row.get("pricing_rule") or "").strip()
		if not name:
			continue
		if row.get("item_code") or row.get("child_docname"):
			continue
		if name not in result:
			result.append(name)
	return result


def validate_manual_document_discount_against_promotions(
	doc,
	values: dict[str, Any],
	*,
	document_label: str = "Invoice",
) -> None:
	"""Prevent a manual document discount from silently stacking with a document promotion."""
	if not transaction_promotion_names(doc):
		return
	if not (
		flt(values.get("additional_discount_percentage") or 0)
		or flt(values.get("discount_amount") or 0)
	):
		return
	label = str(document_label or "Invoice").strip() or "Invoice"
	frappe.throw(
		_(
			"An automatic {0} promotion applies. Remove the manual {0} discount to use the promotion, or change the document so the promotion no longer qualifies."
		).format(label.lower()),
		frappe.ValidationError,
	)
