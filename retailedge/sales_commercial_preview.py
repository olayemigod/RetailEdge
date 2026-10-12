from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from retailedge.guided_entry_context import get_guided_branch_names
from retailedge.guided_pricing import resolve_price_list_context, resolve_sales_item_pricing
from retailedge.guided_sales_invoice import (
	SALES_INVOICE_DOCTYPE,
	_assert_can_create_sales_invoice,
	_assert_read_permission,
	_coerce_values,
	_normalise_items,
	_validate_transaction_context,
)
from retailedge.utils.settings import get_retailedge_settings


@frappe.whitelist(methods=["POST"])
def get_sales_invoice_commercial_preview(values: dict | str | None = None) -> dict[str, Any]:
	"""Return an unsaved ERPNext Sales Invoice commercial preview.

	This endpoint never inserts, saves or submits a document. It exists only to
	show the same pricing, discount, tax and total information the Sales Invoice
	will use when the user eventually saves the draft.
	"""
	_assert_can_create_sales_invoice()
	values = _coerce_values(values)
	user = frappe.session.user
	company, branch, warehouse = _validate_transaction_context(values, user=user)

	customer = str(values.get("customer") or "").strip()
	if not customer:
		frappe.throw(_("Customer is required before calculating the sale."))
	_assert_read_permission("Customer", customer)

	items = _normalise_items(values.get("items"))
	pricing_context = resolve_price_list_context(
		mode="selling",
		company=company,
		branch=branch,
		party=customer,
		selected_price_list=str(values.get("price_list") or "").strip(),
		user=user,
	)
	if pricing_context.get("selection_required"):
		frappe.throw(_("Choose a Selling Price List assigned to you for this Branch before calculating the sale."))

	settings = get_retailedge_settings()
	can_edit_update_stock = bool(getattr(settings, "allow_guided_sales_update_stock_edit", 0))
	update_stock = cint(values.get("update_stock") or 0) if can_edit_update_stock else 1
	configured_branches = get_guided_branch_names(company, user=user)
	if update_stock and configured_branches and not branch:
		frappe.throw(_("Choose a Branch before calculating this stock-updating sale."))
	if update_stock and not warehouse:
		frappe.throw(_("Choose a Stock Location before calculating this stock-updating sale."))

	doc = _build_preview_document(
		company=company,
		branch=branch,
		warehouse=warehouse,
		customer=customer,
		posting_date=values.get("posting_date") or nowdate(),
		price_list=pricing_context.get("price_list") or "",
		requested_price_list=values.get("price_list") or "",
		update_stock=update_stock,
		items=items,
		user=user,
	)
	_prepare_preview_document(doc)
	return _serialize_preview(doc, branch=branch, pricing_context=pricing_context)


def _build_preview_document(
	*,
	company: str,
	branch: str,
	warehouse: str,
	customer: str,
	posting_date: str,
	price_list: str,
	requested_price_list: str,
	update_stock: int,
	items: list[dict[str, Any]],
	user: str,
):
	doc = frappe.new_doc(SALES_INVOICE_DOCTYPE)
	doc.company = company
	doc.customer = customer
	doc.posting_date = getdate(posting_date or nowdate())
	doc.update_stock = update_stock
	if price_list:
		doc.selling_price_list = price_list
	if warehouse:
		doc.set_warehouse = warehouse
	if branch:
		_set_branch(doc, branch)

	for item in items:
		_assert_read_permission("Item", item["item_code"])
		resolved = resolve_sales_item_pricing(
			item_code=item["item_code"],
			company=company,
			customer=customer,
			branch=branch,
			warehouse=warehouse,
			posting_date=str(doc.posting_date),
			qty=item["qty"],
			selected_price_list=price_list,
			user=user,
			requested_price_list=requested_price_list,
		)
		resolved_rate = resolved.get("rate")
		manual_rate = item.get("rate")
		if resolved_rate is None and manual_rate is None:
			frappe.throw(
				_("No selling price could be resolved for Item {0}.").format(item["item_code"])
			)
		if resolved.get("source") == "pos_profile" and not resolved.get("allow_rate_change", True):
			effective_rate = resolved_rate
		else:
			effective_rate = manual_rate if manual_rate is not None else resolved_rate
		if effective_rate is None:
			frappe.throw(_("Selling Rate is required for Item {0}.").format(item["item_code"]))

		row = {
			"item_code": item["item_code"],
			"qty": item["qty"],
			"rate": effective_rate,
		}
		if warehouse:
			row["warehouse"] = warehouse
		doc.append("items", row)

	return doc


def _prepare_preview_document(doc) -> None:
	"""Use ERPNext's own document methods without persistence side effects."""
	doc.run_method("set_missing_values")
	doc.run_method("calculate_taxes_and_totals")


def _set_branch(doc, branch: str) -> None:
	for fieldname in ("branch", "retailedge_branch"):
		if doc.meta.has_field(fieldname):
			doc.set(fieldname, branch)
			return
	# Keep compatibility with the current guided draft path where Branch is a
	# runtime field supplied by the installed ERPNext/RetailEdge composition.
	doc.branch = branch


def _serialize_preview(doc, *, branch: str, pricing_context: dict[str, Any]) -> dict[str, Any]:
	item_rows = [_serialize_item(row) for row in list(doc.get("items") or [])]
	item_savings = sum(_item_savings(row) for row in list(doc.get("items") or []))
	rounded_total = flt(doc.get("rounded_total") or 0)
	grand_total = flt(doc.get("grand_total") or 0)
	invoice_total = rounded_total or grand_total

	return {
		"doctype": SALES_INVOICE_DOCTYPE,
		"company": doc.get("company") or "",
		"branch": doc.get("branch") or doc.get("retailedge_branch") or branch,
		"customer": doc.get("customer") or "",
		"currency": doc.get("currency") or pricing_context.get("currency") or "",
		"selling_price_list": doc.get("selling_price_list") or pricing_context.get("price_list") or "",
		"tax_category": doc.get("tax_category") or "",
		"taxes_and_charges": doc.get("taxes_and_charges") or "",
		"items": item_rows,
		"subtotal": flt(doc.get("total") or 0),
		"net_total": flt(doc.get("net_total") or 0),
		"item_discount_total": flt(item_savings),
		"additional_discount_percentage": flt(doc.get("additional_discount_percentage") or 0),
		"additional_discount": flt(doc.get("discount_amount") or 0),
		"apply_discount_on": doc.get("apply_discount_on") or "",
		"taxes": [_serialize_tax(row) for row in list(doc.get("taxes") or [])],
		"total_taxes_and_charges": flt(doc.get("total_taxes_and_charges") or 0),
		"rounding_adjustment": flt(doc.get("rounding_adjustment") or 0),
		"grand_total": grand_total,
		"rounded_total": rounded_total,
		"invoice_total": invoice_total,
		"has_discount": bool(item_savings or flt(doc.get("discount_amount") or 0)),
		"has_tax": bool(flt(doc.get("total_taxes_and_charges") or 0) or list(doc.get("taxes") or [])),
		"is_preview": True,
	}


def _serialize_item(row) -> dict[str, Any]:
	return {
		"item_code": row.get("item_code") or "",
		"item_name": row.get("item_name") or row.get("item_code") or "",
		"uom": row.get("uom") or row.get("stock_uom") or "",
		"stock_uom": row.get("stock_uom") or "",
		"qty": flt(row.get("qty") or 0),
		"price_list_rate": flt(row.get("price_list_rate") or 0),
		"discount_percentage": flt(row.get("discount_percentage") or 0),
		"discount_amount": flt(row.get("discount_amount") or 0),
		"rate": flt(row.get("rate") or 0),
		"amount": flt(row.get("amount") or 0),
		"net_rate": flt(row.get("net_rate") or row.get("rate") or 0),
		"net_amount": flt(row.get("net_amount") or row.get("amount") or 0),
		"pricing_rule": row.get("pricing_rules") or row.get("pricing_rule") or "",
		"is_free_item": bool(cint(row.get("is_free_item") or 0)),
	}


def _item_savings(row) -> float:
	qty = flt(row.get("qty") or 0)
	price_list_rate = flt(row.get("price_list_rate") or 0)
	amount = flt(row.get("amount") or 0)
	if qty <= 0 or price_list_rate <= 0:
		return 0.0
	return max((price_list_rate * qty) - amount, 0.0)


def _serialize_tax(row) -> dict[str, Any]:
	amount = flt(row.get("tax_amount_after_discount_amount") or row.get("tax_amount") or 0)
	return {
		"description": row.get("description") or row.get("account_head") or _("Tax"),
		"rate": flt(row.get("rate") or 0),
		"tax_amount": amount,
		"included_in_print_rate": bool(cint(row.get("included_in_print_rate") or 0)),
	}
