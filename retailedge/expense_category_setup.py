from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, get_datetime

EXPENSE_CATEGORY_DOCTYPE = "RetailEdge Expense Category"
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
MAX_SEARCH_RESULTS = 20
MAX_CATEGORY_ROWS = 1000


@frappe.whitelist()
def get_expense_category_manager_context() -> dict[str, Any]:
	_assert_read_access()
	user = frappe.session.user
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	if company and not _has_doc_permission("Company", company, "read"):
		company = ""
	return {
		"default_filters": {
			"company": company,
			"active_status": "Active",
			"search_text": "",
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"can_create": bool(frappe.has_permission(EXPENSE_CATEGORY_DOCTYPE, "create")),
		"can_write": bool(frappe.has_permission(EXPENSE_CATEGORY_DOCTYPE, "write")),
		"limits": {
			"page_size": MAX_PAGE_SIZE,
			"search_results": MAX_SEARCH_RESULTS,
		},
	}


@frappe.whitelist()
def get_expense_categories(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	_assert_read_access()
	filters = _coerce_filters(filters)
	query_filters: dict[str, Any] = {}
	company = str(filters.get("company") or "").strip()
	if company:
		_assert_named_permission("Company", company, "read")
		query_filters["company"] = company

	active_status = str(filters.get("active_status") or "").strip()
	if active_status == "Active":
		query_filters["is_active"] = 1
	elif active_status == "Inactive":
		query_filters["is_active"] = 0
	elif active_status not in {"", "All"}:
		frappe.throw(_("Unsupported Expense Category status filter."))

	search_text = str(filters.get("search_text") or "").strip()
	or_filters = None
	if search_text:
		like = f"%{search_text}%"
		or_filters = {
			"name": ["like", like],
			"category_name": ["like", like],
			"category_code": ["like", like],
			"description": ["like", like],
		}

	page = max(1, cint(page) or 1)
	page_size = max(
		1,
		min(
			cint(page_size)
			or cint(filters.get("page_size"))
			or DEFAULT_PAGE_SIZE,
			MAX_PAGE_SIZE,
		),
	)
	matching = frappe.get_list(
		EXPENSE_CATEGORY_DOCTYPE,
		filters=query_filters,
		or_filters=or_filters,
		fields=["name"],
		order_by="name asc",
		limit_page_length=MAX_CATEGORY_ROWS + 1,
	)
	if len(matching) > MAX_CATEGORY_ROWS:
		frappe.throw(
			_(
				"More than {0} Expense Categories match this view. Narrow Company, status, or search filters first."
			).format(MAX_CATEGORY_ROWS)
		)
	total = len(matching)
	total_pages = max(1, ceil(total / page_size)) if total else 1
	page = min(page, total_pages)
	rows = frappe.get_list(
		EXPENSE_CATEGORY_DOCTYPE,
		filters=query_filters,
		or_filters=or_filters,
		fields=[
			"name",
			"category_name",
			"category_code",
			"company",
			"expense_account",
			"default_cost_center",
			"is_active",
			"description",
			"modified",
		],
		order_by="is_active desc, category_name asc, name asc",
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)
	return {
		"rows": [_serialise_category(row) for row in rows],
		"summary": {
			"count": total,
			"active_filter": active_status or "All",
		},
		"pagination": {
			"page": page,
			"page_size": page_size,
			"total_rows": total,
			"total_pages": total_pages,
			"has_previous": page > 1,
			"has_next": page < total_pages,
		},
	}


@frappe.whitelist()
def get_expense_category(name: str) -> dict[str, Any]:
	_assert_read_access()
	doc = _get_category(name)
	if not doc.has_permission("read"):
		frappe.throw(
			_("You do not have permission to read this Expense Category."),
			frappe.PermissionError,
		)
	return _category_payload(doc)


@frappe.whitelist()
def search_expense_category_manager_options(
	kind: str,
	txt: str = "",
	company: str = "",
) -> list[dict[str, str]]:
	_assert_read_access()
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or "").strip()

	if kind == "company":
		rows = frappe.get_list(
			"Company",
			filters={"name": ["like", f"%{txt}%"]},
			fields=["name"],
			order_by="name asc",
			limit_page_length=MAX_SEARCH_RESULTS,
		)
		return [{"value": row.name, "label": row.name} for row in rows]

	if not company:
		frappe.throw(_("Select Company before choosing accounting defaults."))
	_assert_named_permission("Company", company, "read")

	if kind == "expense_account":
		rows = frappe.get_list(
			"Account",
			filters={
				"company": company,
				"root_type": "Expense",
				"is_group": 0,
				"disabled": 0,
			},
			or_filters={
				"name": ["like", f"%{txt}%"],
				"account_name": ["like", f"%{txt}%"],
			},
			fields=["name", "account_name"],
			order_by="account_name asc, name asc",
			limit_page_length=MAX_SEARCH_RESULTS,
		)
		return [
			{
				"value": row.name,
				"label": row.account_name or row.name,
				"description": row.name,
			}
			for row in rows
		]

	if kind == "cost_center":
		rows = frappe.get_list(
			"Cost Center",
			filters={
				"company": company,
				"is_group": 0,
			},
			or_filters={
				"name": ["like", f"%{txt}%"],
				"cost_center_name": ["like", f"%{txt}%"],
			},
			fields=["name", "cost_center_name"],
			order_by="cost_center_name asc, name asc",
			limit_page_length=MAX_SEARCH_RESULTS,
		)
		return [
			{
				"value": row.name,
				"label": row.cost_center_name or row.name,
				"description": row.name,
			}
			for row in rows
		]

	frappe.throw(_("Unsupported Expense Category option search."))


@frappe.whitelist(methods=["POST"])
def save_expense_category(
	values: dict[str, Any] | str,
	name: str = "",
	expected_modified: str | None = None,
) -> dict[str, Any]:
	values = frappe.parse_json(values) if isinstance(values, str) else values
	if not isinstance(values, dict):
		frappe.throw(_("Expense Category values are required."))

	name = str(name or "").strip()
	if name:
		doc = _get_category(name)
		if not doc.has_permission("write"):
			frappe.throw(
				_("You do not have permission to edit this Expense Category."),
				frappe.PermissionError,
			)
		_assert_modified(doc, expected_modified)
		requested_name = str(values.get("category_name") or doc.category_name or "").strip()
		if requested_name and requested_name != str(doc.category_name or "").strip():
			frappe.throw(
				_(
					"Category Name is stable after creation in RetailEdge Setup. Use an explicit administrator rename process when a master-key rename is required."
				)
			)
	else:
		if not frappe.has_permission(EXPENSE_CATEGORY_DOCTYPE, "create"):
			frappe.throw(
				_("You do not have permission to create Expense Categories."),
				frappe.PermissionError,
			)
		company = str(values.get("company") or "").strip()
		if not company:
			frappe.throw(_("Company is required when creating an Expense Category in RetailEdge Setup."))
		doc = frappe.new_doc(EXPENSE_CATEGORY_DOCTYPE)

	_apply_values(doc, values)
	_validate_link_permissions(doc)

	if name:
		doc.save()
	else:
		doc.insert()
	return _category_payload(doc)


def _apply_values(doc, values: dict[str, Any]) -> None:
	allowed = (
		"category_name",
		"category_code",
		"company",
		"expense_account",
		"default_cost_center",
		"is_active",
		"description",
		"notes",
	)
	for fieldname in allowed:
		if fieldname not in values:
			continue
		value = values.get(fieldname)
		if fieldname == "is_active":
			value = cint(value)
		elif isinstance(value, str):
			value = value.strip()
		setattr(doc, fieldname, value)


def _validate_link_permissions(doc) -> None:
	company = str(getattr(doc, "company", None) or "").strip()
	if company:
		_assert_named_permission("Company", company, "read")
	expense_account = str(getattr(doc, "expense_account", None) or "").strip()
	if expense_account:
		_assert_named_permission("Account", expense_account, "read")
		account_company = frappe.db.get_value("Account", expense_account, "company")
		if company and account_company and account_company != company:
			frappe.throw(_("Expense Account belongs to another Company."))
	default_cost_center = str(getattr(doc, "default_cost_center", None) or "").strip()
	if default_cost_center:
		_assert_named_permission("Cost Center", default_cost_center, "read")
		cost_center_company = frappe.db.get_value(
			"Cost Center",
			default_cost_center,
			"company",
		)
		if company and cost_center_company and cost_center_company != company:
			frappe.throw(_("Default Cost Center belongs to another Company."))


def _get_category(name: str):
	name = str(name or "").strip()
	if not name or not frappe.db.exists(EXPENSE_CATEGORY_DOCTYPE, name):
		frappe.throw(_("Expense Category {0} does not exist.").format(name or ""))
	return frappe.get_doc(EXPENSE_CATEGORY_DOCTYPE, name)


def _assert_modified(doc, expected_modified: str | None) -> None:
	if not expected_modified:
		return
	try:
		expected = get_datetime(expected_modified)
		current = get_datetime(doc.modified)
	except Exception:
		frappe.throw(_("Invalid Expense Category version."))
	if expected != current:
		frappe.throw(
			_(
				"This Expense Category changed after you opened it. Reload before saving your changes."
			)
		)


def _assert_read_access() -> None:
	if not frappe.db.exists("DocType", EXPENSE_CATEGORY_DOCTYPE):
		frappe.throw(_("Expense Category is unavailable on this site."))
	if not frappe.has_permission(EXPENSE_CATEGORY_DOCTYPE, "read"):
		frappe.throw(
			_("You do not have permission to view Expense Categories."),
			frappe.PermissionError,
		)


def _has_doc_permission(doctype: str, name: str, ptype: str) -> bool:
	try:
		return bool(frappe.has_permission(doctype, ptype, doc=name))
	except Exception:
		return False


def _assert_named_permission(doctype: str, name: str, ptype: str) -> None:
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not _has_doc_permission(doctype, name, ptype):
		frappe.throw(
			_("You do not have permission to use {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)


def _serialise_category(row) -> dict[str, Any]:
	return {
		"name": row.name,
		"category_name": row.category_name or row.name,
		"category_code": row.category_code or "",
		"company": row.company or "",
		"expense_account": row.expense_account or "",
		"default_cost_center": row.default_cost_center or "",
		"is_active": cint(row.is_active),
		"description": row.description or "",
		"modified": row.modified,
	}


def _category_payload(doc) -> dict[str, Any]:
	return {
		"name": doc.name,
		"category_name": doc.category_name or doc.name,
		"category_code": doc.category_code or "",
		"company": doc.company or "",
		"expense_account": doc.expense_account or "",
		"default_cost_center": doc.default_cost_center or "",
		"is_active": cint(doc.is_active),
		"description": doc.description or "",
		"notes": doc.notes or "",
		"modified": doc.modified,
		"can_edit": bool(doc.has_permission("write")),
	}
