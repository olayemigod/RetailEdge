from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from retailedge.cashier_context import get_cashier_expense_entry_context
from retailedge.retailedge.doctype.retailedge_cashier_expense.retailedge_cashier_expense import today

EXPENSE_DOCTYPE = "RetailEdge Cashier Expense"
CATEGORY_DOCTYPE = "RetailEdge Expense Category"
MAX_LINK_RESULTS = 20


@frappe.whitelist()
def get_guided_cashier_expense_context() -> dict[str, Any]:
	_assert_can_create_expense()
	context = get_cashier_expense_entry_context(user=frappe.session.user)
	settings = context.get("settings") or {}
	blocking_reasons: list[str] = []
	if settings.get("require_open_shift_for_cashier_expense") and not context.get(
		"linked_pos_opening_shift"
	):
		blocking_reasons.append(_("Open a POS shift before recording a cashier expense."))
	if (
		not settings.get("allow_cashier_expense_without_cash_account")
		and not context.get("payment_account")
	):
		blocking_reasons.append(_("RetailEdge could not resolve a cash payment account for this shift."))

	return {
		"title": _("Record Cashier Expense"),
		"subtitle": _(
			"Record a controlled cash expense against the current RetailEdge cashier context."
		),
		"submit_label": _("Save Draft"),
		"full_form_doctype": EXPENSE_DOCTYPE,
		"ready": not blocking_reasons,
		"blocking_reasons": blocking_reasons,
		"defaults": {
			"expense_category": "",
			"amount": "",
			"description": "",
			"expense_date": today(),
		},
		"context": {
			"cashier": context.get("cashier") or context.get("user") or frappe.session.user,
			"company": context.get("company") or "",
			"branch": context.get("branch") or "",
			"pos_profile": context.get("pos_profile") or "",
			"opening_shift": context.get("linked_pos_opening_shift") or "",
			"payment_account": context.get("payment_account") or "",
			"cost_center": context.get("cost_center") or "",
			"available_cash": flt(context.get("available_shift_cash_before_expense")),
			"opening_cash": flt(context.get("shift_opening_cash_amount")),
			"cash_sales": flt(context.get("shift_cash_sales_amount")),
			"prior_expenses": flt(context.get("prior_shift_expense_amount")),
			"cash_control_message": context.get("cash_control_message") or "",
		},
		"capabilities": {
			"allow_expense_date_edit": bool(settings.get("allow_cashier_expense_date_edit")),
			"native_form_fallback": True,
		},
		"limits": {"link_results": MAX_LINK_RESULTS},
	}


@frappe.whitelist()
def search_guided_expense_categories(
	txt: str = "",
	company: str | None = None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_can_create_expense()
	limit = max(1, min(cint(limit) or MAX_LINK_RESULTS, MAX_LINK_RESULTS))
	company = company or frappe.defaults.get_user_default("Company") or ""
	if company:
		_assert_company_read_access(company)

	filters: list[list[Any]] = [[CATEGORY_DOCTYPE, "is_active", "=", 1]]
	if txt:
		filters.append([CATEGORY_DOCTYPE, "category_name", "like", f"%{txt}%"])
	or_filters: list[list[Any]] = []
	if company:
		or_filters = [
			[CATEGORY_DOCTYPE, "company", "=", company],
			[CATEGORY_DOCTYPE, "company", "is", "not set"],
		]

	rows = frappe.get_list(
		CATEGORY_DOCTYPE,
		filters=filters,
		or_filters=or_filters or None,
		fields=["name", "category_name", "category_code", "description"],
		order_by="category_name asc",
		limit_page_length=limit,
	)
	return [
		{
			"value": row.name,
			"label": row.category_name or row.name,
			"description": row.description
			or (_("Code {0}").format(row.category_code) if row.category_code else ""),
		}
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def create_guided_cashier_expense_draft(values: dict | str | None = None) -> dict[str, Any]:
	_assert_can_create_expense()
	values = _coerce_values(values)
	category = str(values.get("expense_category") or "").strip()
	if not category:
		frappe.throw(_("Expense Category is required."))
	_assert_active_category(category)

	amount = flt(values.get("amount"))
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero."))

	doc = frappe.new_doc(EXPENSE_DOCTYPE)
	doc.expense_category = category
	doc.amount = amount
	if values.get("description"):
		doc.description = str(values.get("description")).strip()
	if values.get("expense_date"):
		doc.expense_date = getdate(values.get("expense_date"))

	# The existing RetailEdge Cashier Expense controller resolves cashier/company/
	# branch/POS/accounting context, refreshes shift cash, validates the selected
	# category against the resolved company, validates available cash, derives the
	# expense account and posting readiness, and remains authoritative.
	doc.insert()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"docstatus": doc.docstatus,
		"expense_status": doc.expense_status,
		"company": doc.company,
		"branch": doc.branch,
		"cashier": doc.cashier,
		"expense_category": doc.expense_category,
		"amount": doc.amount,
		"available_cash_after": flt(doc.available_shift_cash_after_expense),
		"route": f"/app/retailedge-cashier-expense/{doc.name}",
	}


def _assert_active_category(category: str) -> None:
	if not frappe.db.exists(CATEGORY_DOCTYPE, category):
		frappe.throw(_("Expense Category {0} does not exist.").format(category))
	if not frappe.has_permission(CATEGORY_DOCTYPE, "read", doc=category):
		frappe.throw(
			_("You do not have permission to use Expense Category {0}.").format(category),
			frappe.PermissionError,
		)
	row = frappe.db.get_value(
		CATEGORY_DOCTYPE,
		category,
		["is_active"],
		as_dict=True,
	)
	if not row or not cint(row.is_active):
		frappe.throw(_("Expense Category {0} is inactive.").format(category))


def _assert_company_read_access(company: str) -> None:
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(
			_("You do not have permission to use Company {0}.").format(company),
			frappe.PermissionError,
		)


def _assert_can_create_expense() -> None:
	if not frappe.db.exists("DocType", EXPENSE_DOCTYPE) or not frappe.has_permission(
		EXPENSE_DOCTYPE, "create"
	):
		frappe.throw(
			_("You do not have permission to create Cashier Expenses."),
			frappe.PermissionError,
		)


def _coerce_values(values: dict | str | None) -> dict[str, Any]:
	if not values:
		return {}
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if isinstance(values, frappe._dict):
		return dict(values)
	if isinstance(values, dict):
		return dict(values)
	frappe.throw(_("Invalid Cashier Expense values."))
	return {}
