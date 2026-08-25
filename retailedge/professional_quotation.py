from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from retailedge.guided_pricing import resolve_price_list_context, resolve_sales_item_pricing
from retailedge.professional_selling import _assert_read, _coerce_values, _permission, _validate_context


MAX_ITEMS = 50


def _normalise_items(items: Any) -> list[dict[str, Any]]:
	if isinstance(items, str):
		items = frappe.parse_json(items)
	if not isinstance(items, list) or not items:
		frappe.throw(_("Add at least one quotation item."))
	if len(items) > MAX_ITEMS:
		frappe.throw(_("A Professional Quotation can contain at most {0} items.").format(MAX_ITEMS))

	normalised: list[dict[str, Any]] = []
	for index, item in enumerate(items, start=1):
		if not isinstance(item, dict):
			frappe.throw(_("Quotation item row {0} is invalid.").format(index))
		item_code = str(item.get("item_code") or "").strip()
		if not item_code:
			frappe.throw(_("Item is required on row {0}.").format(index))
		qty = flt(item.get("qty"))
		if qty <= 0:
			frappe.throw(_("Quantity on row {0} must be greater than zero.").format(index))
		rate_value = item.get("rate")
		rate = None if rate_value in (None, "") else flt(rate_value)
		if rate is not None and rate < 0:
			frappe.throw(_("Selling Rate on row {0} cannot be negative.").format(index))
		normalised.append({"item_code": item_code, "qty": qty, "rate": rate})
	return normalised


def _validate_shipping_rule(shipping_rule: str, *, company: str) -> str:
	shipping_rule = str(shipping_rule or "").strip()
	if not shipping_rule:
		return ""
	_assert_read("Shipping Rule", shipping_rule)
	rule = frappe.db.get_value(
		"Shipping Rule",
		shipping_rule,
		["company", "disabled", "shipping_rule_type"],
		as_dict=True,
	) or {}
	if rule.get("disabled"):
		frappe.throw(_("Shipping Rule {0} is disabled.").format(shipping_rule))
	if str(rule.get("shipping_rule_type") or "") != "Selling":
		frappe.throw(_("Shipping Rule {0} is not a Selling rule.").format(shipping_rule))
	if rule.get("company") and rule.get("company") != company:
		frappe.throw(_("Shipping Rule {0} does not belong to Company {1}.").format(shipping_rule, company))
	return shipping_rule


@frappe.whitelist(methods=["POST"])
def create_professional_quotation_draft(values: dict | str | None = None) -> dict[str, Any]:
	"""Create a Customer Quotation draft without bypassing ERPNext controls.

	The effective Price List and item rates are resolved again on the server.
	Shipping charges, when requested, are applied by ERPNext's native
	``apply_shipping_rule`` implementation. This endpoint never submits.
	"""
	if not _permission("Quotation", "create"):
		frappe.throw(_("You do not have permission to create Quotation."), frappe.PermissionError)

	values = _coerce_values(values)
	company, branch, warehouse = _validate_context(values)
	customer = str(values.get("customer") or values.get("party_name") or "").strip()
	if not customer:
		frappe.throw(_("Customer is required."))
	_assert_read("Customer", customer)
	items = _normalise_items(values.get("items"))
	shipping_rule = _validate_shipping_rule(values.get("shipping_rule"), company=company)

	transaction_date = getdate(values.get("transaction_date") or nowdate())
	valid_till_value = values.get("valid_till")
	valid_till = getdate(valid_till_value) if valid_till_value else None
	if valid_till and valid_till < transaction_date:
		frappe.throw(_("Valid Till cannot be before the Quotation Date."))

	pricing_context = resolve_price_list_context(
		mode="selling",
		company=company,
		branch=branch,
		party=customer,
		user=frappe.session.user,
	)

	doc = frappe.new_doc("Quotation")
	doc.company = company
	doc.quotation_to = "Customer"
	doc.party_name = customer
	doc.transaction_date = transaction_date
	if valid_till:
		doc.valid_till = valid_till
	if pricing_context.get("price_list"):
		doc.selling_price_list = pricing_context["price_list"]
	if shipping_rule:
		doc.shipping_rule = shipping_rule
	if values.get("terms") and doc.meta.has_field("terms"):
		doc.terms = str(values.get("terms") or "").strip()

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
			frappe.throw(
				_("No selling price could be resolved for Item {0}. Set an Item Price or Standard Rate before saving.").format(item["item_code"])
			)
		if resolved.get("source") == "pos_profile" and not resolved.get("allow_rate_change", True):
			effective_rate = resolved_rate
		else:
			effective_rate = manual_rate if manual_rate is not None else resolved_rate
		if effective_rate is None:
			frappe.throw(_("Selling Rate is required for Item {0}.").format(item["item_code"]))
		row = {"item_code": item["item_code"], "qty": item["qty"], "rate": effective_rate}
		if warehouse:
			row["warehouse"] = warehouse
		doc.append("items", row)

	# Draft-only. ERPNext validation/pricing remains authoritative on insert.
	doc.insert()
	if shipping_rule:
		# Use ERPNext's native Shipping Rule implementation; do not calculate or
		# maintain a RetailEdge delivery-charge row/ledger.
		doc.apply_shipping_rule()
		doc.save()

	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"customer": customer,
		"company": doc.company,
		"branch": branch,
		"selling_price_list": getattr(doc, "selling_price_list", None) or pricing_context.get("price_list"),
		"shipping_rule": getattr(doc, "shipping_rule", None) or "",
		"grand_total": doc.grand_total,
		"currency": doc.currency,
		"route": f"/app/quotation/{doc.name}",
	}
