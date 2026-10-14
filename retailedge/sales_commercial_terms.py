from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint, flt, getdate, nowdate

from erpnext.accounts.doctype.pricing_rule.utils import validate_coupon_code

try:
	from erpnext.accounts.services.taxes import get_taxes_and_charges
except ImportError:
	# Earlier ERPNext v16 releases expose the same helper from AccountsController.
	# RetailEdge's upgrade matrix must remain importable before ERPNext introduced
	# accounts.services.taxes. Permission/company checks stay in this module.
	from erpnext.controllers.accounts_controller import (
		_get_taxes_and_charges as get_taxes_and_charges,
	)


SALES_INVOICE_DOCTYPE = "Sales Invoice"
COUPON_DOCTYPE = "Coupon Code"
TAX_CATEGORY_DOCTYPE = "Tax Category"
TAX_TEMPLATE_DOCTYPE = "Sales Taxes and Charges Template"
MAX_SEARCH_RESULTS = 20
ALLOWED_DISCOUNT_TARGETS = {"Grand Total", "Net Total"}


def get_sales_commercial_term_capabilities(doc=None) -> dict[str, bool]:
	"""Return ERPNext-permission-backed commercial term capabilities."""
	if doc is None:
		can_edit = bool(frappe.has_permission(SALES_INVOICE_DOCTYPE, "create"))
	else:
		can_edit = bool(
			cint(doc.docstatus) == 0
			and frappe.has_permission(SALES_INVOICE_DOCTYPE, "write", doc=doc)
		)
	return {
		"can_edit_additional_discount": can_edit,
		"can_use_coupon": bool(can_edit and _can_select(COUPON_DOCTYPE)),
		"can_select_tax_category": bool(can_edit and _can_select(TAX_CATEGORY_DOCTYPE)),
		"can_select_tax_template": bool(can_edit and _can_select(TAX_TEMPLATE_DOCTYPE)),
	}


@frappe.whitelist()
def get_sales_commercial_edit_context(name: str) -> dict[str, Any]:
	"""Return the exact saved draft terms a permitted Make Sale user may edit."""
	doc = _assert_invoice_term_search_access(name)
	if doc is None:
		frappe.throw(_("Sales Invoice is required."), frappe.ValidationError)
	return {
		"document_name": doc.name,
		"company": str(doc.get("company") or "").strip(),
		"customer": str(doc.get("customer") or "").strip(),
		"terms": sales_commercial_terms_from_doc(doc),
		"capabilities": get_sales_commercial_term_capabilities(doc),
	}


@frappe.whitelist()
def search_sales_commercial_term_options(
	fieldname: str,
	txt: str = "",
	values: dict | str | None = None,
	limit: int = MAX_SEARCH_RESULTS,
) -> list[dict[str, Any]]:
	"""Search only the ERPNext commercial masters the current user may select."""
	values = _coerce_values(values)
	doc = _assert_invoice_term_search_access(values.get("document_name"))
	if doc is not None:
		values["company"] = str(doc.get("company") or "").strip()
		values["customer"] = str(doc.get("customer") or "").strip()
		if "tax_category" not in values:
			values["tax_category"] = str(doc.get("tax_category") or "").strip()
	limit = max(1, min(cint(limit) or MAX_SEARCH_RESULTS, MAX_SEARCH_RESULTS))
	query = str(txt or "").strip()

	if fieldname == "tax_category":
		if not _can_select(TAX_CATEGORY_DOCTYPE):
			return []
		return search_link(
			TAX_CATEGORY_DOCTYPE,
			query,
			filters={"disabled": 0},
			page_length=limit,
			reference_doctype=SALES_INVOICE_DOCTYPE,
			link_fieldname="tax_category",
		)

	if fieldname == "taxes_and_charges":
		if not _can_select(TAX_TEMPLATE_DOCTYPE):
			return []
		company = str(values.get("company") or "").strip()
		if not company:
			return []
		return _search_sales_tax_templates(
			query,
			company=company,
			tax_category=str(values.get("tax_category") or "").strip(),
			limit=limit,
		)

	if fieldname == "coupon_code":
		if not _can_select(COUPON_DOCTYPE):
			return []
		return _search_coupon_codes(query, values=values, limit=limit)

	frappe.throw(_("Unsupported sales commercial field: {0}").format(fieldname))
	return []


def normalise_sales_commercial_terms(values: dict | str | None) -> dict[str, Any]:
	"""Validate user-editable commercial fields without calculating totals."""
	values = _coerce_values(values)
	result: dict[str, Any] = {}

	if "coupon_code" in values:
		result["coupon_code"] = str(values.get("coupon_code") or "").strip()

	if "tax_category" in values:
		result["tax_category"] = str(values.get("tax_category") or "").strip()

	if "taxes_and_charges" in values:
		result["taxes_and_charges"] = str(values.get("taxes_and_charges") or "").strip()

	percentage_present = "additional_discount_percentage" in values
	amount_present = "discount_amount" in values
	percentage = flt(values.get("additional_discount_percentage") or 0) if percentage_present else None
	amount = flt(values.get("discount_amount") or 0) if amount_present else None

	if percentage is not None:
		if percentage < 0 or percentage > 100:
			frappe.throw(_("Additional Discount % must be between 0 and 100."), frappe.ValidationError)
		result["additional_discount_percentage"] = percentage
	if amount is not None:
		if amount < 0:
			frappe.throw(_("Additional Discount Amount cannot be negative."), frappe.ValidationError)
		result["discount_amount"] = amount
	if percentage and amount:
		frappe.throw(
			_("Use either Additional Discount % or Additional Discount Amount, not both."),
			frappe.ValidationError,
		)

	if "apply_discount_on" in values:
		apply_on = str(values.get("apply_discount_on") or "").strip()
		if apply_on and apply_on not in ALLOWED_DISCOUNT_TARGETS:
			frappe.throw(_("Choose Net Total or Grand Total for the additional discount."), frappe.ValidationError)
		result["apply_discount_on"] = apply_on

	return result


def apply_sales_commercial_terms(doc, values: dict | str | None) -> dict[str, Any]:
	"""Apply bounded ERPNext Sales Invoice commercial terms in memory.

	A blank tax-template input means "automatic": the current/default ERPNext
	tax resolution is preserved unless Tax Category itself changes. A category
	change clears the prior template and tax rows so ERPNext can resolve the new
	tax treatment rather than retaining a stale category/template combination.
	"""
	terms = normalise_sales_commercial_terms(values)
	if not terms:
		return sales_commercial_terms_from_doc(doc)

	if "coupon_code" in terms:
		coupon = terms["coupon_code"]
		if coupon:
			_assert_select_permission(COUPON_DOCTYPE, coupon)
			validate_coupon_code(coupon)
		doc.set("coupon_code", coupon)

	if "tax_category" in terms:
		tax_category = terms["tax_category"]
		if tax_category:
			_validate_tax_category(tax_category)
		category_changed = tax_category != str(doc.get("tax_category") or "").strip()
		doc.set("tax_category", tax_category)
		if category_changed:
			doc.set("taxes_and_charges", "")
			doc.set("taxes", [])

	if "taxes_and_charges" in terms:
		tax_template = terms["taxes_and_charges"]
		if tax_template:
			_validate_sales_tax_template(doc, tax_template)
			doc.set("taxes_and_charges", tax_template)
			doc.set("taxes", [])
			for row in get_taxes_and_charges(TAX_TEMPLATE_DOCTYPE, tax_template) or []:
				doc.append("taxes", row)

	percentage_supplied = "additional_discount_percentage" in terms
	amount_supplied = "discount_amount" in terms
	if percentage_supplied:
		doc.set("additional_discount_percentage", terms["additional_discount_percentage"])
		if terms["additional_discount_percentage"]:
			doc.set("discount_amount", 0)
	if amount_supplied:
		doc.set("discount_amount", terms["discount_amount"])
		if terms["discount_amount"]:
			doc.set("additional_discount_percentage", 0)
	if "apply_discount_on" in terms:
		apply_on = terms["apply_discount_on"] or "Grand Total"
		doc.set("apply_discount_on", apply_on)
	elif (percentage_supplied or amount_supplied) and not doc.get("apply_discount_on"):
		doc.set("apply_discount_on", "Grand Total")

	return sales_commercial_terms_from_doc(doc)


def sales_commercial_terms_from_doc(doc) -> dict[str, Any]:
	return {
		"coupon_code": str(doc.get("coupon_code") or "").strip(),
		"tax_category": str(doc.get("tax_category") or "").strip(),
		"taxes_and_charges": str(doc.get("taxes_and_charges") or "").strip(),
		"apply_discount_on": str(doc.get("apply_discount_on") or "").strip(),
		"additional_discount_percentage": flt(doc.get("additional_discount_percentage") or 0),
		"discount_amount": flt(doc.get("discount_amount") or 0),
	}


def _validate_tax_category(name: str) -> None:
	_assert_select_permission(TAX_CATEGORY_DOCTYPE, name)
	disabled = frappe.db.get_value(TAX_CATEGORY_DOCTYPE, name, "disabled")
	if disabled is None:
		frappe.throw(_("Tax Category {0} does not exist.").format(name))
	if cint(disabled):
		frappe.throw(_("Tax Category {0} is disabled.").format(name), frappe.ValidationError)


def _validate_sales_tax_template(doc, name: str) -> None:
	_assert_select_permission(TAX_TEMPLATE_DOCTYPE, name)
	row = frappe.db.get_value(
		TAX_TEMPLATE_DOCTYPE,
		name,
		["company", "disabled", "tax_category"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Sales Taxes and Charges Template {0} does not exist.").format(name))
	if cint(row.get("disabled")):
		frappe.throw(_("Sales Taxes and Charges Template {0} is disabled.").format(name), frappe.ValidationError)
	company = str(doc.get("company") or "").strip()
	if row.get("company") and company and row.get("company") != company:
		frappe.throw(
			_("Sales Taxes and Charges Template {0} does not belong to Company {1}.").format(name, company),
			frappe.PermissionError,
		)
	template_category = str(row.get("tax_category") or "").strip()
	document_category = str(doc.get("tax_category") or "").strip()
	if template_category and document_category and template_category != document_category:
		frappe.throw(
			_("Sales Taxes and Charges Template {0} is for Tax Category {1}, not {2}.").format(
				name,
				template_category,
				document_category,
			),
			frappe.ValidationError,
		)


def _search_sales_tax_templates(
	query: str,
	*,
	company: str,
	tax_category: str,
	limit: int,
) -> list[dict[str, Any]]:
	base_filters: dict[str, Any] = {"company": company, "disabled": 0}
	if not tax_category:
		return search_link(
			TAX_TEMPLATE_DOCTYPE,
			query,
			filters=base_filters,
			page_length=limit,
			reference_doctype=SALES_INVOICE_DOCTYPE,
			link_fieldname="taxes_and_charges",
		)

	result: list[dict[str, Any]] = []
	seen: set[str] = set()
	for category_filter in (tax_category, ["is", "not set"]):
		filters = {**base_filters, "tax_category": category_filter}
		for row in search_link(
			TAX_TEMPLATE_DOCTYPE,
			query,
			filters=filters,
			page_length=limit,
			reference_doctype=SALES_INVOICE_DOCTYPE,
			link_fieldname="taxes_and_charges",
		):
			value = str(row.get("value") or row.get("name") or "").strip() if isinstance(row, dict) else str(row or "").strip()
			if not value or value in seen:
				continue
			seen.add(value)
			result.append(row)
			if len(result) >= limit:
				return result
	return result


def _search_coupon_codes(query: str, *, values: dict[str, Any], limit: int) -> list[dict[str, Any]]:
	like = f"%{query}%" if query else "%"
	rows = frappe.get_list(
		COUPON_DOCTYPE,
		filters={},
		or_filters={
			"name": ["like", like],
			"coupon_code": ["like", like],
			"coupon_name": ["like", like],
		},
		fields=[
			"name",
			"coupon_name",
			"coupon_code",
			"customer",
			"valid_from",
			"valid_upto",
			"maximum_use",
			"used",
		],
		order_by="modified desc",
		limit_page_length=max(limit * 3, limit),
	)
	customer = str(values.get("customer") or "").strip()
	today = getdate(nowdate())
	result: list[dict[str, Any]] = []
	for row in rows:
		row_customer = str(row.get("customer") or "").strip()
		if row_customer and row_customer != customer:
			continue
		if row.get("valid_from") and getdate(row.get("valid_from")) > today:
			continue
		if row.get("valid_upto") and getdate(row.get("valid_upto")) < today:
			continue
		maximum_use = cint(row.get("maximum_use") or 0)
		if maximum_use and cint(row.get("used") or 0) >= maximum_use:
			continue
		label = str(row.get("coupon_code") or row.get("coupon_name") or row.get("name") or "").strip()
		description = str(row.get("coupon_name") or row.get("name") or "").strip()
		result.append({"value": row.get("name"), "label": label, "description": description})
		if len(result) >= limit:
			break
	return result


def _assert_invoice_term_search_access(document_name: Any):
	name = str(document_name or "").strip()
	if not name:
		if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "create"):
			frappe.throw(_("You do not have permission to prepare a Sales Invoice."), frappe.PermissionError)
		return None
	if not frappe.db.exists(SALES_INVOICE_DOCTYPE, name):
		frappe.throw(_("Sales Invoice {0} does not exist.").format(name))
	doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, name)
	if cint(doc.docstatus) != 0:
		frappe.throw(_("Only draft Sales Invoices can change commercial terms."), frappe.ValidationError)
	if not frappe.has_permission(SALES_INVOICE_DOCTYPE, "read", doc=doc) or not frappe.has_permission(
		SALES_INVOICE_DOCTYPE,
		"write",
		doc=doc,
	):
		frappe.throw(_("You do not have permission to edit this Sales Invoice."), frappe.PermissionError)
	return doc


def _can_select(doctype: str) -> bool:
	return bool(
		frappe.has_permission(doctype, "select")
		or frappe.has_permission(doctype, "read")
	)


def _assert_select_permission(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not (
		frappe.has_permission(doctype, "select", doc=name)
		or frappe.has_permission(doctype, "read", doc=name)
	):
		frappe.throw(_("You do not have permission to use {0} {1}.").format(doctype, name), frappe.PermissionError)


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if not values:
		return {}
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if isinstance(values, frappe._dict):
		return dict(values)
	if isinstance(values, dict):
		return dict(values)
	frappe.throw(_("Invalid sales commercial terms."), frappe.ValidationError)
	return {}
