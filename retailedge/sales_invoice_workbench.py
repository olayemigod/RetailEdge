from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.operating_context import get_operating_context
from retailedge.standard_sales_invoice_completion import get_standard_sales_invoice_completion_preview


SALES_INVOICE_DOCTYPE = "Sales Invoice"
MAX_RESUMABLE_DRAFTS = 12


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _item_review(doc) -> list[dict[str, Any]]:
	return [
		{
			"name": _clean(row.get("name")),
			"item_code": _clean(row.get("item_code")),
			"item_name": _clean(row.get("item_name")),
			"description": _clean(row.get("description")),
			"uom": _clean(row.get("uom")),
			"qty": flt(row.get("qty")),
			"rate": flt(row.get("rate")),
			"discount_percentage": flt(row.get("discount_percentage")),
			"net_rate": flt(row.get("net_rate")),
			"amount": flt(row.get("amount")),
			"net_amount": flt(row.get("net_amount")),
			"warehouse": _clean(row.get("warehouse")),
		}
		for row in list(doc.get("items") or [])
	]


def _tax_review(doc) -> list[dict[str, Any]]:
	return [
		{
			"description": _clean(row.get("description")),
			"account_head": _clean(row.get("account_head")),
			"charge_type": _clean(row.get("charge_type")),
			"rate": flt(row.get("rate")),
			"tax_amount": flt(row.get("tax_amount")),
			"total": flt(row.get("total")),
		}
		for row in list(doc.get("taxes") or [])
	]


def _payment_review(doc) -> list[dict[str, Any]]:
	return [
		{
			"mode_of_payment": _clean(row.get("mode_of_payment")),
			"amount": flt(row.get("amount")),
		}
		for row in list(doc.get("payments") or [])
		if _clean(row.get("mode_of_payment")) or flt(row.get("amount"))
	]


@frappe.whitelist(methods=["GET"])
def get_sales_invoice_submission_review(
	name: str,
	source_mode: str = "standard",
) -> dict[str, Any]:
	"""Return the complete governed review required before Sales Invoice submission.

	The standard completion preview remains the permission, Branch, Workflow and
	submission authority. This endpoint only enriches that authority with the full
	business detail needed for an informed review; it does not create a second
	calculation or submission path.
	"""
	preview = get_standard_sales_invoice_completion_preview(name, source_mode=source_mode)
	doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, preview["name"])

	items = _item_review(doc)
	preview.update(
		{
			"customer_name": _clean(doc.get("customer_name")) or _clean(doc.get("customer")),
			"total_qty": flt(doc.get("total_qty")),
			"total": flt(doc.get("total")),
			"net_total": flt(doc.get("net_total")),
			"discount_amount": flt(doc.get("discount_amount")),
			"additional_discount_percentage": flt(doc.get("additional_discount_percentage")),
			"total_taxes_and_charges": flt(doc.get("total_taxes_and_charges")),
			"rounded_total": flt(doc.get("rounded_total")),
			"paid_amount": flt(doc.get("paid_amount")),
			"change_amount": flt(doc.get("change_amount")),
			"items": items,
			"item_count": len(items),
			"taxes": _tax_review(doc),
			"payments": _payment_review(doc),
			"review_complete": True,
		}
	)
	return preview


@frappe.whitelist(methods=["GET"])
def get_resumable_sales_invoice_drafts(limit: int = MAX_RESUMABLE_DRAFTS) -> list[dict[str, Any]]:
	"""List this user's own unfinished Make Sale drafts in the active context.

	The list is deliberately owner-scoped so a cashier cannot silently take over
	another cashier's unfinished transaction. The standard completion preview is
	used for each candidate so current Company/Branch and document permissions are
	revalidated before a draft is advertised as resumable.
	"""
	user = _clean(getattr(frappe.session, "user", ""))
	if not user or user == "Guest":
		frappe.throw(_("Please sign in to continue an unfinished sale."), frappe.PermissionError)
	if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "read"):
		return []

	limit = max(1, min(cint(limit) or MAX_RESUMABLE_DRAFTS, MAX_RESUMABLE_DRAFTS))
	operating = get_operating_context() or {}
	filters: dict[str, Any] = {
		"docstatus": 0,
		"owner": user,
		"is_return": 0,
		"is_pos": 0,
		"is_consolidated": 0,
	}
	company = _clean(operating.get("company"))
	if company:
		filters["company"] = company

	rows = frappe.get_list(
		SALES_INVOICE_DOCTYPE,
		filters=filters,
		fields=[
			"name",
			"customer",
			"customer_name",
			"posting_date",
			"currency",
			"grand_total",
			"modified",
			"company",
		],
		order_by="modified desc",
		limit_page_length=limit * 3,
	)

	result: list[dict[str, Any]] = []
	for row in rows:
		try:
			preview = get_standard_sales_invoice_completion_preview(row.name, source_mode="standard")
		except frappe.PermissionError:
			continue
		doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, row.name)
		if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "write", doc=doc):
			continue
		result.append(
			{
				"name": row.name,
				"customer": _clean(row.customer),
				"customer_name": _clean(row.customer_name) or _clean(row.customer),
				"posting_date": _clean(row.posting_date),
				"currency": _clean(row.currency),
				"grand_total": flt(row.grand_total),
				"modified": _clean(row.modified),
				"company": _clean(row.company),
				"branch": _clean(preview.get("branch")),
				"item_count": cint(preview.get("item_count")),
				"can_edit": bool(preview.get("can_edit")),
				"can_submit": bool(preview.get("can_submit")),
				"blockers": list(preview.get("blockers") or []),
			}
		)
		if len(result) >= limit:
			break

	return result
