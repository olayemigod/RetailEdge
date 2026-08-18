from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

DOCTYPE = "RetailEdge Expense Category"
MAX_LINK_RESULTS = 20


@frappe.whitelist()
def get_simple_expense_category_context() -> dict[str, Any]:
	_assert_can_create()
	return {
		"title": _("Simple Expense Category"),
		"subtitle": _("Create a RetailEdge expense category with safe accounting defaults."),
		"submit_label": _("Create Expense Category"),
		"full_form_doctype": DOCTYPE,
		"defaults": {
			"category_name": "",
			"category_code": "",
			"company": frappe.defaults.get_user_default("Company") or "",
			"expense_account": "",
			"default_cost_center": "",
			"description": "",
		},
		"limits": {"link_results": MAX_LINK_RESULTS},
		"capabilities": {"native_form_fallback": True},
	}


@frappe.whitelist()
def search_simple_expense_category_options(
	fieldname: str,
	txt: str = "",
	company: str = "",
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_can_create()
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	company = str(company or "").strip()
	if fieldname == "company":
		return search_link("Company", txt or "", page_length=limit, reference_doctype=DOCTYPE, link_fieldname="company")
	if fieldname == "expense_account":
		filters: dict[str, Any] = {"is_group": 0, "disabled": 0, "root_type": "Expense"}
		if company:
			filters["company"] = company
		return search_link("Account", txt or "", filters=filters, page_length=limit, reference_doctype=DOCTYPE, link_fieldname="expense_account")
	if fieldname == "default_cost_center":
		filters = {"is_group": 0}
		if company:
			filters["company"] = company
		return search_link("Cost Center", txt or "", filters=filters, page_length=limit, reference_doctype=DOCTYPE, link_fieldname="default_cost_center")
	frappe.throw(_("Unsupported Simple Expense Category search field: {0}").format(fieldname))
	return []


@frappe.whitelist(methods=["POST"])
def create_simple_expense_category(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_create()
	values = _coerce_values(values)
	category_name = str(values.get("category_name") or "").strip()
	if not category_name:
		frappe.throw(_("Category Name is required."))

	doc = frappe.new_doc(DOCTYPE)
	doc.category_name = category_name
	doc.category_code = str(values.get("category_code") or "").strip() or None
	doc.company = str(values.get("company") or frappe.defaults.get_user_default("Company") or "").strip() or None
	doc.expense_account = str(values.get("expense_account") or "").strip() or None
	doc.default_cost_center = str(values.get("default_cost_center") or "").strip() or None
	doc.description = str(values.get("description") or "").strip() or None
	doc.is_active = 1
	doc.insert()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"category_name": doc.category_name,
		"company": doc.company,
		"expense_account": doc.expense_account,
		"default_cost_center": doc.default_cost_center,
		"route": f"/app/retailedge-expense-category/{doc.name}",
	}


def _assert_can_create() -> None:
	if not frappe.has_permission(DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Expense Categories."), frappe.PermissionError)


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	return dict(values or {})
