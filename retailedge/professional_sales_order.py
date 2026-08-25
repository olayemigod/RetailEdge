from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from erpnext.selling.doctype.quotation.quotation import make_sales_order as erpnext_make_sales_order

from retailedge.branch_context import validate_user_branch_access
from retailedge.guided_pricing import resolve_price_list_context, resolve_sales_item_pricing
from retailedge.professional_quotation import _normalise_items, _validate_shipping_rule
from retailedge.professional_selling import _assert_read, _coerce_values, _permission, _validate_context


def _set_branch_if_supported(doc, branch: str) -> None:
	branch = str(branch or "").strip()
	if not branch:
		return
	for fieldname in ("branch", "retailedge_branch"):
		if doc.meta.has_field(fieldname) and not doc.get(fieldname):
			doc.set(fieldname, branch)
			return


def _assert_mapped_sales_order_context(doc) -> tuple[str, str]:
	"""Validate mapped source truth without rewriting values from Operating Context."""
	company = str(doc.get("company") or "").strip()
	if not company:
		frappe.throw(_("The mapped Sales Order has no Company."))
	_assert_read("Company", company)

	branch = str(doc.get("branch") or doc.get("retailedge_branch") or "").strip()
	if branch:
		validate_user_branch_access(branch, user=frappe.session.user, company=company, throw=True)

	operating = frappe.call("retailedge.operating_context.get_operating_context") or {}
	operating_company = str(operating.get("company") or "").strip()
	operating_branch = str(operating.get("branch") or "").strip()
	if operating_company and operating_company != company:
		frappe.throw(_("The Quotation belongs to another Company. Change Operating Context before creating its Sales Order."))
	if operating_branch and branch and operating_branch != branch:
		frappe.throw(_("The Quotation/Sales Order Branch does not match the current Operating Branch."))
	return company, branch


def _apply_shipping_rule_to_draft(doc) -> None:
	if doc.get("shipping_rule"):
		doc.apply_shipping_rule()
		doc.save()


@frappe.whitelist(methods=["POST"])
def create_professional_sales_order_draft(values: dict | str | None = None) -> dict[str, Any]:
	"""Create a standalone ERPNext Sales Order draft using server-authoritative pricing."""
	if not _permission("Sales Order", "create"):
		frappe.throw(_("You do not have permission to create Sales Order."), frappe.PermissionError)

	values = _coerce_values(values)
	company, branch, warehouse = _validate_context(values)
	customer = str(values.get("customer") or "").strip()
	if not customer:
		frappe.throw(_("Customer is required."))
	_assert_read("Customer", customer)
	items = _normalise_items(values.get("items"))
	shipping_rule = _validate_shipping_rule(values.get("shipping_rule"), company=company)

	transaction_date = getdate(values.get("transaction_date") or nowdate())
	delivery_date = getdate(values.get("delivery_date") or transaction_date)
	if delivery_date < transaction_date:
		frappe.throw(_("Delivery Date cannot be before the Order Date."))

	pricing_context = resolve_price_list_context(
		mode="selling",
		company=company,
		branch=branch,
		party=customer,
		user=frappe.session.user,
	)

	doc = frappe.new_doc("Sales Order")
	doc.company = company
	doc.customer = customer
	doc.transaction_date = transaction_date
	doc.delivery_date = delivery_date
	if warehouse:
		doc.set_warehouse = warehouse
	if pricing_context.get("price_list"):
		doc.selling_price_list = pricing_context["price_list"]
	if shipping_rule:
		doc.shipping_rule = shipping_rule
	if values.get("po_no") and doc.meta.has_field("po_no"):
		doc.po_no = str(values.get("po_no") or "").strip()
	if values.get("terms") and doc.meta.has_field("terms"):
		doc.terms = str(values.get("terms") or "").strip()
	_set_branch_if_supported(doc, branch)

	for item in items:
		_assert_read("Item", item["item_code"])
		resolved = resolve_sales_item_pricing(
			item_code=item["item_code"],
			company=company,
			customer=customer,
			branch=branch,
			warehouse=warehouse,
			posting_date=str(transaction_date),
			qty=item["qty"],
			user=frappe.session.user,
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
			"delivery_date": delivery_date,
		}
		if warehouse:
			row["warehouse"] = warehouse
		doc.append("items", row)

	# Draft-only. Normal ERPNext validation runs on insert.
	doc.insert()
	_apply_shipping_rule_to_draft(doc)
	return _sales_order_response(doc, branch=branch)


@frappe.whitelist(methods=["POST"])
def create_sales_order_from_quotation(quotation: str) -> dict[str, Any]:
	"""Map one submitted Customer Quotation to a new Sales Order draft using ERPNext's native mapper."""
	if not _permission("Sales Order", "create"):
		frappe.throw(_("You do not have permission to create Sales Order."), frappe.PermissionError)
	quotation = str(quotation or "").strip()
	_assert_read("Quotation", quotation)
	source = frappe.get_doc("Quotation", quotation)
	if source.docstatus != 1:
		frappe.throw(_("Submit the Quotation before creating a Sales Order from it."))
	if str(source.get("quotation_to") or "") != "Customer":
		frappe.throw(_("Only Customer Quotations can be converted to Sales Orders in Professional Selling."))

	# ERPNext owns source-to-target field/item mapping, ordered-quantity checks and
	# expired-quotation policy. The submitted source is never changed here.
	target = erpnext_make_sales_order(source.name)
	if not target or target.doctype != "Sales Order":
		frappe.throw(_("ERPNext could not prepare a Sales Order from this Quotation."))
	if target.docstatus != 0:
		frappe.throw(_("ERPNext returned a non-draft Sales Order mapping; creation was stopped."))
	_company, branch = _assert_mapped_sales_order_context(target)

	# The mapper may carry the source Shipping Rule. Validate it again before insert.
	if target.get("shipping_rule"):
		_validate_shipping_rule(target.shipping_rule, company=target.company)

	target.insert()
	_apply_shipping_rule_to_draft(target)
	return _sales_order_response(target, branch=branch, source_quotation=source.name)


def _sales_order_response(doc, *, branch: str = "", source_quotation: str = "") -> dict[str, Any]:
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"customer": doc.customer,
		"company": doc.company,
		"branch": doc.get("branch") or doc.get("retailedge_branch") or branch,
		"selling_price_list": doc.get("selling_price_list") or "",
		"shipping_rule": doc.get("shipping_rule") or "",
		"grand_total": doc.grand_total,
		"currency": doc.currency,
		"source_quotation": source_quotation,
		"route": f"/app/sales-order/{doc.name}",
	}
