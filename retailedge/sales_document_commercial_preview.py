from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from retailedge.guided_pricing import resolve_price_list_context, resolve_sales_item_pricing
from retailedge.professional_quotation import _normalise_items
from retailedge.professional_selling import _assert_read, _coerce_values, _validate_context
from retailedge.sales_commercial_preview import (
	_prepare_preview_document,
	_preview_item_rows,
	_serialize_preview,
)
from retailedge.sales_commercial_promotion_guard import validate_manual_document_discount_against_promotions
from retailedge.sales_commercial_terms import (
	SALES_INVOICE_DOCTYPE,
	SUPPORTED_SALES_COMMERCIAL_DOCTYPES,
	apply_sales_commercial_terms,
	get_sales_commercial_term_capabilities,
)
from retailedge.sales_item_discounts import (
	apply_manual_item_discount,
	validate_manual_item_discounts_after_pricing,
)


PREVIEWABLE_DOCTYPES = {"Quotation", "Sales Order"}


@frappe.whitelist(methods=["POST"])
def get_sales_document_commercial_preview(
	document_type: str,
	values: dict | str | None = None,
) -> dict[str, Any]:
	"""Calculate a persistence-free ERPNext commercial preview for a selling document.

	This endpoint deliberately supports newly authored Quotation and Sales Order
	drafts. Sales Invoice keeps its existing preview API so saved-invoice editing
	and stock-mode rules remain backward compatible. No document is inserted,
	saved, submitted or committed here.
	"""
	doctype = str(document_type or "").strip()
	if doctype == SALES_INVOICE_DOCTYPE:
		frappe.throw(
			_("Use the Sales Invoice commercial preview for Sales Invoice calculations."),
			frappe.ValidationError,
		)
	if doctype not in PREVIEWABLE_DOCTYPES or doctype not in SUPPORTED_SALES_COMMERCIAL_DOCTYPES:
		frappe.throw(_("Commercial preview is not supported for {0}.").format(doctype or "this document"))
	if not frappe.has_permission(doctype, "create"):
		frappe.throw(_("You do not have permission to calculate a new {0}.").format(doctype), frappe.PermissionError)

	values = _coerce_values(values)
	company, branch, warehouse = _validate_context(values)
	customer = str(values.get("customer") or values.get("party_name") or "").strip()
	if not customer:
		frappe.throw(_("Customer is required before calculating the {0}.").format(doctype))
	_assert_read("Customer", customer)

	items = _normalise_items(_preview_item_rows(values.get("items")))
	pricing_context = resolve_price_list_context(
		mode="selling",
		company=company,
		branch=branch,
		party=customer,
		selected_price_list=str(values.get("price_list") or "").strip(),
		user=frappe.session.user,
		requested_price_list=values.get("price_list") or "",
	)
	if pricing_context.get("selection_required"):
		frappe.throw(
			_("Choose a Selling Price List assigned to you for this Branch before calculating the {0}.").format(doctype)
		)

	doc = _build_sales_document_preview(
		doctype=doctype,
		values=values,
		company=company,
		branch=branch,
		warehouse=warehouse,
		customer=customer,
		price_list=str(pricing_context.get("price_list") or ""),
		items=items,
	)
	apply_sales_commercial_terms(doc, values)
	_prepare_preview_document(doc)
	validate_manual_item_discounts_after_pricing(doc, items)
	validate_manual_document_discount_against_promotions(
		doc,
		values,
		document_label=doctype,
	)

	preview = _serialize_preview(doc, branch=branch, pricing_context=pricing_context)
	preview["doctype"] = doctype
	preview["document_label"] = doctype
	preview["document_total"] = preview.get("invoice_total")
	preview["commercial_term_capabilities"] = get_sales_commercial_term_capabilities(
		document_type=doctype
	)
	return preview


def _build_sales_document_preview(
	*,
	doctype: str,
	values: dict[str, Any],
	company: str,
	branch: str,
	warehouse: str,
	customer: str,
	price_list: str,
	items: list[dict[str, Any]],
):
	transaction_date = getdate(values.get("transaction_date") or nowdate())
	doc = frappe.new_doc(doctype)
	doc.company = company
	doc.flags.retailedge_item_pricing_provenance = []
	if doctype == "Quotation":
		doc.quotation_to = "Customer"
		doc.party_name = customer
		doc.transaction_date = transaction_date
		if values.get("valid_till"):
			valid_till = getdate(values.get("valid_till"))
			if valid_till < transaction_date:
				frappe.throw(_("Valid Till cannot be before the Quotation Date."))
			doc.valid_till = valid_till
	else:
		doc.customer = customer
		doc.transaction_date = transaction_date
		delivery_date = getdate(values.get("delivery_date") or transaction_date)
		if delivery_date < transaction_date:
			frappe.throw(_("Delivery Date cannot be before the Order Date."))
		doc.delivery_date = delivery_date
		if warehouse:
			doc.set_warehouse = warehouse

	if price_list:
		doc.selling_price_list = price_list
	_set_branch(doc, branch)

	for index, item in enumerate(items, start=1):
		_assert_read("Item", item["item_code"])
		resolved = resolve_sales_item_pricing(
			item_code=item["item_code"],
			company=company,
			customer=customer,
			branch=branch,
			warehouse=warehouse,
			posting_date=str(transaction_date),
			qty=item["qty"],
			selected_price_list=price_list,
			user=frappe.session.user,
			requested_price_list=values.get("price_list") or "",
		)
		resolved_rate = resolved.get("rate")
		manual_rate = item.get("rate")
		rate_locked = not bool(resolved.get("allow_rate_change", True))
		if resolved_rate is None and manual_rate is None:
			frappe.throw(_("No selling price could be resolved for Item {0}.").format(item["item_code"]))
		effective_rate = resolved_rate if rate_locked else (
			manual_rate if manual_rate is not None else resolved_rate
		)
		if effective_rate is None:
			frappe.throw(_("Selling Rate is required for Item {0}.").format(item["item_code"]))

		doc.flags.retailedge_item_pricing_provenance.append(
			{
				"index": index,
				"item_code": item["item_code"],
				"price_list_rate": flt(resolved.get("price_list_rate") or 0),
				"automatic_rate": flt(resolved_rate) if resolved_rate is not None else None,
				"entered_rate": flt(effective_rate),
				"manual_rate_supplied": bool(manual_rate is not None and not rate_locked),
			}
		)
		row = {
			"item_code": item["item_code"],
			"qty": item["qty"],
			"rate": effective_rate,
		}
		if doctype == "Sales Order":
			row["delivery_date"] = doc.delivery_date
		if warehouse:
			row["warehouse"] = warehouse
		child = doc.append("items", row)
		apply_manual_item_discount(
			child,
			item,
			index=index,
			rate_locked=rate_locked,
			lock_reason=str(resolved.get("rate_change_lock_reason") or "").strip(),
			price_list_rate=resolved.get("price_list_rate"),
		)
	return doc


def _set_branch(doc, branch: str) -> None:
	branch = str(branch or "").strip()
	if not branch:
		return
	for fieldname in ("retailedge_branch", "branch"):
		if doc.meta.has_field(fieldname):
			doc.set(fieldname, branch)
			return
