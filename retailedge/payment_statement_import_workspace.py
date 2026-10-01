from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from retailedge.bank_account_policy import resolve_retailedge_bank_account, search_retailedge_bank_accounts
from retailedge.operating_context import get_operational_branch_scope, validate_operating_branch

DOCTYPE = "RetailEdge Payment Statement Import"
ROW_DOCTYPE = "RetailEdge Statement Import Row"
TEMPLATE_DOCTYPE = "RetailEdge Statement Mapping Template"
MAX_LIST_ROWS = 100
MAX_DETAIL_ROWS = 100
MAX_SEARCH_RESULTS = 20


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _assert_read() -> None:
	if not frappe.has_permission(DOCTYPE, "read"):
		frappe.throw(_("You do not have permission to view Bank Statement Imports."), frappe.PermissionError)


def _validate_company(company: str) -> str:
	company = _clean(company)
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("Choose a valid Company."), frappe.ValidationError)
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have permission to use Company {0}.").format(company), frappe.PermissionError)
	return company


def _scope_branch(company: str, branch: str = "", *, require_for_restricted: bool = False) -> str:
	branch = _clean(branch)
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	allowed = {_clean(value) for value in scope.get("allowed_branches") or [] if _clean(value)}
	if branch:
		validate_operating_branch(company=company, branch=branch, user=frappe.session.user, throw=True)
		if scope.get("restricted") and branch not in allowed:
			frappe.throw(_("Branch {0} is outside your permitted operating scope.").format(branch), frappe.PermissionError)
		return branch
	if scope.get("restricted"):
		if len(allowed) == 1:
			return next(iter(allowed))
		if require_for_restricted:
			frappe.throw(_("Choose an Operating Branch before continuing."), frappe.PermissionError)
	return ""


def _scoped_filters(company: str = "", branch: str = "") -> dict[str, Any]:
	filters: dict[str, Any] = {}
	company = _clean(company)
	branch = _clean(branch)
	if company:
		company = _validate_company(company)
		branch = _scope_branch(company, branch)
		filters["company"] = company
		if branch:
			filters["branch"] = branch
	return filters


@frappe.whitelist()
def get_bank_statement_import_workspace_context() -> dict[str, Any]:
	_assert_read()
	company = _clean(frappe.defaults.get_user_default("Company"))
	if company and (not frappe.db.exists("Company", company) or not frappe.has_permission("Company", "read", doc=company)):
		company = ""
	branch = ""
	if company:
		scope = get_operational_branch_scope(company, user=frappe.session.user)
		allowed = [_clean(value) for value in scope.get("allowed_branches") or [] if _clean(value)]
		if scope.get("restricted") and len(allowed) == 1:
			branch = allowed[0]
	return {
		"defaults": {
			"company": company,
			"branch": branch,
			"statement_date": nowdate(),
			"statement_type": "Bank Transfer",
			"payment_category": "Bank Transfer",
		},
		"can_create": bool(frappe.has_permission(DOCTYPE, "create")),
		"can_write": bool(frappe.has_permission(DOCTYPE, "write")),
		"statement_types": ["Bank Transfer", "Card / POS Settlement", "Mobile Money", "Other"],
		"payment_categories": ["Bank Transfer", "Card / POS", "Mobile Money", "Other"],
		"statuses": ["Draft", "Imported", "Reviewed", "Archived"],
		"source_of_truth": DOCTYPE,
	}


@frappe.whitelist()
def get_bank_statement_imports(
	company: str = "",
	branch: str = "",
	status: str = "",
	search_text: str = "",
	page: int = 1,
	page_size: int = 25,
) -> dict[str, Any]:
	_assert_read()
	page = max(1, cint(page) or 1)
	page_size = max(1, min(cint(page_size) or 25, MAX_LIST_ROWS))
	filters = _scoped_filters(company, branch)
	status = _clean(status)
	if status and status != "All":
		filters["import_status"] = status

	or_filters = None
	search_text = _clean(search_text)
	if search_text:
		pattern = f"%{search_text}%"
		or_filters = {
			"name": ["like", pattern],
			"bank_account": ["like", pattern],
			"payment_category": ["like", pattern],
		}

	rows = frappe.get_list(
		DOCTYPE,
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "company", "branch", "statement_date", "bank_account", "statement_type",
			"payment_category", "mapping_template", "attachment", "import_status", "total_rows",
			"ready_rows", "imported_row_count", "duplicate_suspected_count",
			"failed_rows", "linked_bank_transactions", "modified",
		],
		order_by="statement_date desc, modified desc",
		start=(page - 1) * page_size,
		limit_page_length=page_size + 1,
	)
	has_more = len(rows) > page_size
	return {
		"rows": [dict(row) for row in rows[:page_size]],
		"page": page,
		"page_size": page_size,
		"has_more": has_more,
	}


@frappe.whitelist()
def get_bank_statement_import_detail(name: str) -> dict[str, Any]:
	_assert_read()
	name = _clean(name)
	if not name:
		frappe.throw(_("Bank Statement Import is required."), frappe.ValidationError)
	rows = frappe.get_list(
		DOCTYPE,
		filters={"name": name},
		fields=[
			"name", "company", "branch", "statement_date", "bank_account", "statement_type",
			"payment_category", "mapping_template", "attachment", "import_status", "total_rows",
			"ready_rows", "imported_row_count", "unique_row_count", "duplicate_suspected_count",
			"rejected_duplicate_count", "imported_rows", "duplicate_rows", "skipped_rows",
			"failed_rows", "linked_bank_transactions", "last_import_run_on", "last_import_run_by",
			"import_summary_note", "modified",
		],
		limit_page_length=1,
	)
	if not rows:
		frappe.throw(_("Bank Statement Import {0} was not found or is outside your permissions.").format(name), frappe.DoesNotExistError)
	doc = dict(rows[0])
	_validate_company(doc.get("company"))
	if doc.get("branch"):
		_scope_branch(doc.get("company"), doc.get("branch"))

	statement_rows = frappe.get_list(
		ROW_DOCTYPE,
		filters={"parent": name, "parenttype": DOCTYPE},
		fields=[
			"name", "idx", "transaction_date", "reference", "narration", "amount",
			"transaction_direction", "duplicate_status", "import_status", "match_status",
			"bank_transaction", "existing_bank_transaction", "duplicate_reason", "row_error",
		],
		order_by="idx asc",
		limit_page_length=MAX_DETAIL_ROWS,
	)
	return {
		"document": doc,
		"rows": [dict(row) for row in statement_rows],
		"rows_truncated": cint(doc.get("total_rows")) > len(statement_rows),
		"can_write": bool(frappe.has_permission(DOCTYPE, "write", doc=name)),
		"can_use_native": bool(frappe.has_permission(DOCTYPE, "read", doc=name)),
	}


@frappe.whitelist(methods=["POST"])
def create_bank_statement_import(values: dict | str | None = None) -> dict[str, Any]:
	if not frappe.has_permission(DOCTYPE, "create"):
		frappe.throw(_("You do not have permission to create Bank Statement Imports."), frappe.PermissionError)
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	if not isinstance(values, dict):
		frappe.throw(_("Bank Statement Import values are invalid."), frappe.ValidationError)

	company = _validate_company(values.get("company"))
	branch = _scope_branch(company, values.get("branch"), require_for_restricted=True)
	bank_account = _clean(values.get("bank_account"))
	if not bank_account:
		frappe.throw(_("Bank Account is required."), frappe.ValidationError)
	resolve_retailedge_bank_account(company=company, branch=branch, bank_account=bank_account)

	statement_date = _clean(values.get("statement_date")) or nowdate()
	try:
		statement_date = getdate(statement_date)
	except Exception:
		frappe.throw(_("Enter a valid Statement Date."), frappe.ValidationError)

	payment_category = _clean(values.get("payment_category"))
	if payment_category not in {"Bank Transfer", "Card / POS", "Mobile Money", "Other"}:
		frappe.throw(_("Choose a valid Payment Category."), frappe.ValidationError)
	statement_type = _clean(values.get("statement_type")) or "Bank Transfer"
	if statement_type not in {"Bank Transfer", "Card / POS Settlement", "Mobile Money", "Other"}:
		frappe.throw(_("Choose a valid Statement Type."), frappe.ValidationError)

	mapping_template = _clean(values.get("mapping_template"))
	if mapping_template:
		if not frappe.db.exists(TEMPLATE_DOCTYPE, mapping_template) or not frappe.has_permission(TEMPLATE_DOCTYPE, "read", doc=mapping_template):
			frappe.throw(_("You do not have permission to use Mapping Template {0}.").format(mapping_template), frappe.PermissionError)
		template_company = _clean(frappe.db.get_value(TEMPLATE_DOCTYPE, mapping_template, "company"))
		if template_company and template_company != company:
			frappe.throw(_("Mapping Template belongs to another Company."), frappe.ValidationError)

	doc = frappe.new_doc(DOCTYPE)
	doc.company = company
	doc.branch = branch or None
	doc.statement_date = statement_date
	doc.bank_account = bank_account
	doc.statement_type = statement_type
	doc.payment_category = payment_category
	doc.mapping_template = mapping_template or None
	doc.import_status = "Draft"
	doc.insert()
	return get_bank_statement_import_detail(doc.name)


@frappe.whitelist(methods=["POST"])
def set_bank_statement_import_attachment(name: str, file_url: str) -> dict[str, Any]:
	name = _clean(name)
	file_url = _clean(file_url)
	if not name or not file_url:
		frappe.throw(_("Bank Statement Import and uploaded File URL are required."), frappe.ValidationError)
	doc = frappe.get_doc(DOCTYPE, name)
	if not doc.has_permission("write"):
		frappe.throw(_("You do not have permission to update this Bank Statement Import."), frappe.PermissionError)
	_validate_company(doc.company)
	if doc.branch:
		_scope_branch(doc.company, doc.branch)
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name or not frappe.has_permission("File", "read", doc=file_name):
		frappe.throw(_("Uploaded file is unavailable or outside your permissions."), frappe.PermissionError)
	doc.attachment = file_url
	doc.save()
	return get_bank_statement_import_detail(doc.name)


@frappe.whitelist()
def search_bank_statement_import_options(
	fieldname: str,
	txt: str = "",
	company: str = "",
	branch: str = "",
	limit: int = 20,
) -> list[dict[str, Any]]:
	_assert_read()
	fieldname = _clean(fieldname)
	txt = _clean(txt)
	limit = max(1, min(cint(limit) or 20, MAX_SEARCH_RESULTS))

	if fieldname == "company":
		rows = frappe.get_list(
			"Company",
			filters={"name": ["like", f"%{txt}%"]} if txt else {},
			fields=["name", "company_name"],
			order_by="name asc",
			limit_page_length=limit,
		)
		return [{"value": row.name, "label": row.company_name or row.name} for row in rows]

	company = _validate_company(company)
	branch = _scope_branch(company, branch)

	if fieldname == "branch":
		scope = get_operational_branch_scope(company, user=frappe.session.user)
		allowed = [_clean(value) for value in scope.get("allowed_branches") or [] if _clean(value)]
		filters: dict[str, Any] = {}
		if frappe.get_meta("Branch").has_field("company"):
			filters["company"] = company
		if scope.get("restricted"):
			if not allowed:
				return []
			filters["name"] = ["in", allowed]
		if txt:
			filters["name"] = ["like", f"%{txt}%"] if not scope.get("restricted") else ["in", [value for value in allowed if txt.lower() in value.lower()]]
		rows = frappe.get_list("Branch", filters=filters, fields=["name"], order_by="name asc", limit_page_length=limit)
		return [{"value": row.name, "label": row.name} for row in rows]

	if fieldname == "bank_account":
		return search_retailedge_bank_accounts(company=company, branch=branch, txt=txt, limit=limit)

	if fieldname == "mapping_template":
		filters = {}
		meta = frappe.get_meta(TEMPLATE_DOCTYPE)
		if meta.has_field("company"):
			filters["company"] = ["in", ["", None, company]]
		if txt:
			filters["name"] = ["like", f"%{txt}%"]
		rows = frappe.get_list(TEMPLATE_DOCTYPE, filters=filters, fields=["name", "template_name"], order_by="modified desc", limit_page_length=limit)
		return [{"value": row.name, "label": row.template_name or row.name} for row in rows]

	frappe.throw(_("Unsupported Bank Statement Import option search."), frappe.ValidationError)


__all__ = [
	"get_bank_statement_import_workspace_context",
	"get_bank_statement_imports",
	"get_bank_statement_import_detail",
	"create_bank_statement_import",
	"set_bank_statement_import_attachment",
	"search_bank_statement_import_options",
]
