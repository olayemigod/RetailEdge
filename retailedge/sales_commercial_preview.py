from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from erpnext.accounts.doctype.pricing_rule.utils import apply_pricing_rule_on_transaction

from retailedge.guided_entry_context import get_guided_branch_names
from retailedge.guided_pricing import resolve_price_list_context, resolve_sales_item_pricing
from retailedge.guided_sales_invoice import (
	SALES_INVOICE_DOCTYPE,
	_assert_read_permission,
	_coerce_values,
	_normalise_items,
	_validate_transaction_context,
)
from retailedge.professional_draft_items import update_draft_items
from retailedge.sales_commercial_terms import (
	apply_sales_commercial_terms,
	get_sales_commercial_term_capabilities,
)
from retailedge.standard_sales_invoice_completion import (
	_build_preview as _build_completion_preview,
	_validate_invoice_context,
)
from retailedge.utils.settings import get_retailedge_settings


@frappe.whitelist(methods=["POST"])
def get_sales_invoice_commercial_preview(
	values: dict | str | None = None,
	document_name: str | None = None,
) -> dict[str, Any]:
	"""Return a persistence-free ERPNext Sales Invoice commercial preview.

	New sales are calculated from a new in-memory Sales Invoice. Existing draft
	edits are calculated from an in-memory clone of the stored draft so accepted
	commercial terms (tax templates, coupons, additional discounts, source links,
	and the stored Price List) are preserved exactly as the real draft update path
	would preserve them. No preview document is inserted, saved, submitted or
	committed.
	"""
	values = _coerce_values(values)
	document_name = str(document_name or "").strip()
	if document_name:
		return _preview_existing_draft(document_name, values)

	_assert_can_preview_sales_invoice()
	return _preview_new_sale(values)


def _preview_new_sale(values: dict[str, Any]) -> dict[str, Any]:
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
	apply_sales_commercial_terms(doc, values)
	_prepare_preview_document(doc)
	return _serialize_preview(doc, branch=branch, pricing_context=pricing_context)


def _preview_existing_draft(document_name: str, values: dict[str, Any]) -> dict[str, Any]:
	stored = _get_editable_sales_invoice(document_name)
	company, invoice_branch = _validate_invoice_context(stored)
	completion = _build_completion_preview(stored)
	if not completion.get("can_edit"):
		message = next(iter(completion.get("blockers") or []), _("This Sales Invoice draft is not editable here."))
		frappe.throw(message, frappe.PermissionError)

	effective_branch = str(completion.get("branch") or invoice_branch or "").strip()
	default_warehouse = str(completion.get("default_warehouse") or "").strip()
	display_price_list = str(completion.get("selling_price_list") or stored.get("selling_price_list") or "").strip()
	customer = str(stored.get("customer") or "").strip()
	_assert_read_permission("Customer", customer)
	_validate_saved_preview_identity(
		stored,
		values,
		branch=effective_branch,
		default_warehouse=default_warehouse,
		display_price_list=display_price_list,
	)

	doc = frappe.get_doc(stored.as_dict())
	posting_date = getdate(values.get("posting_date") or stored.get("posting_date") or nowdate())
	doc.set("posting_date", posting_date)

	requested_items = values.get("items")
	if requested_items is not None:
		update_draft_items(
			doc,
			requested_items,
			company=company,
			branch=invoice_branch,
			customer=customer,
			posting_date=str(posting_date),
			default_warehouse=default_warehouse,
			selected_price_list=str(stored.get("selling_price_list") or "").strip(),
		)

	apply_sales_commercial_terms(doc, values)
	_prepare_preview_document(doc)
	return _serialize_preview(
		doc,
		branch=effective_branch,
		pricing_context={
			"price_list": display_price_list,
			"currency": str(stored.get("currency") or "").strip(),
		},
	)


def _get_editable_sales_invoice(name: str):
	if not name or not frappe.db.exists(SALES_INVOICE_DOCTYPE, name):
		frappe.throw(_("Sales Invoice {0} does not exist.").format(name or "(blank)"))
	doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, name)
	if cint(doc.docstatus) != 0:
		frappe.throw(_("Only draft Sales Invoices can be calculated here."), frappe.ValidationError)
	if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "read", doc=doc):
		frappe.throw(_("You do not have permission to read this Sales Invoice."), frappe.PermissionError)
	if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "write", doc=doc):
		frappe.throw(_("You do not have permission to edit this Sales Invoice."), frappe.PermissionError)
	return doc


def _assert_can_preview_sales_invoice() -> None:
	if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "create"):
		frappe.throw(
			_("You do not have permission to calculate a new Sales Invoice."),
			frappe.PermissionError,
		)


def _validate_saved_preview_identity(
	doc,
	values: dict[str, Any],
	*,
	branch: str,
	default_warehouse: str,
	display_price_list: str | None = None,
) -> None:
	protected = {
		"company": str(doc.get("company") or "").strip(),
		"customer": str(doc.get("customer") or "").strip(),
		"branch": str(branch or "").strip(),
		"price_list": str(
			display_price_list if display_price_list is not None else doc.get("selling_price_list") or ""
		).strip(),
		"warehouse": str(default_warehouse or "").strip(),
	}
	for fieldname, authoritative in protected.items():
		requested = str(values.get(fieldname) or "").strip()
		if requested and requested != authoritative:
			frappe.throw(
				_("The saved Sales Invoice {0} is fixed while editing this draft. Refresh before continuing.").format(
					fieldname.replace("_", " ").title()
				),
				frappe.ValidationError,
			)

	if "update_stock" in values and bool(cint(values.get("update_stock") or 0)) != bool(cint(doc.get("update_stock") or 0)):
		frappe.throw(
			_("The saved Sales Invoice stock mode is fixed while editing this draft. Refresh before continuing."),
			frappe.ValidationError,
		)


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
			frappe.throw(_("No selling price could be resolved for Item {0}.").format(item["item_code"]))
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
	"""Use ERPNext commercial calculation methods without persistence side effects."""
	doc.run_method("set_missing_values")
	doc.run_method("set_taxes_and_charges")
	doc.run_method("calculate_taxes_and_totals")
	if not cint(doc.get("ignore_pricing_rule") or 0):
		apply_pricing_rule_on_transaction(doc)


def _set_branch(doc, branch: str) -> None:
	for fieldname in ("branch", "retailedge_branch"):
		if doc.meta.has_field(fieldname):
			doc.set(fieldname, branch)
			return
	doc.branch = branch


def _serialize_preview(doc, *, branch: str, pricing_context: dict[str, Any]) -> dict[str, Any]:
	item_rows = [_serialize_item(row) for row in list(doc.get("items") or [])]
	item_savings = sum(_item_savings(row) for row in list(doc.get("items") or []))
	tax_rows = [_serialize_tax(row) for row in list(doc.get("taxes") or [])]
	promotions = _promotion_names(doc)
	items_total = flt(doc.get("total") or 0)
	rounded_total = flt(doc.get("rounded_total") or 0)
	grand_total = flt(doc.get("grand_total") or 0)
	invoice_total = rounded_total or grand_total
	net_total = flt(doc.get("net_total") or 0)

	return {
		"doctype": SALES_INVOICE_DOCTYPE,
		"company": doc.get("company") or "",
		"branch": doc.get("branch") or doc.get("retailedge_branch") or branch,
		"customer": doc.get("customer") or "",
		"currency": doc.get("currency") or pricing_context.get("currency") or "",
		"selling_price_list": doc.get("selling_price_list") or pricing_context.get("price_list") or "",
		"coupon_code": doc.get("coupon_code") or "",
		"tax_category": doc.get("tax_category") or "",
		"taxes_and_charges": doc.get("taxes_and_charges") or "",
		"items": item_rows,
		"list_value": flt(items_total + item_savings),
		"items_total": items_total,
		"subtotal": items_total,
		"net_total": net_total,
		"item_discount_total": flt(item_savings),
		"additional_discount_percentage": flt(doc.get("additional_discount_percentage") or 0),
		"additional_discount": flt(doc.get("discount_amount") or 0),
		"apply_discount_on": doc.get("apply_discount_on") or "",
		"promotions": promotions,
		"promotion_count": len(promotions),
		"taxes": tax_rows,
		"total_taxes_and_charges": flt(doc.get("total_taxes_and_charges") or 0),
		"all_taxes_included": bool(tax_rows and all(row["included_in_print_rate"] for row in tax_rows)),
		"rounding_adjustment": flt(doc.get("rounding_adjustment") or 0),
		"grand_total": grand_total,
		"rounded_total": rounded_total,
		"invoice_total": invoice_total,
		"has_discount": bool(item_savings or flt(doc.get("discount_amount") or 0)),
		"has_tax": bool(flt(doc.get("total_taxes_and_charges") or 0) or tax_rows),
		"commercial_term_capabilities": get_sales_commercial_term_capabilities(),
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


def _promotion_names(doc) -> list[str]:
	result: list[str] = []
	for row in list(doc.get("pricing_rules") or []):
		name = str(row.get("pricing_rule") or "").strip()
		if name and name not in result:
			result.append(name)
	return result


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
