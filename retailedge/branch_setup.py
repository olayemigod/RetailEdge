from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint

from retailedge.retailedge.doctype.retailedge_branch_profile.retailedge_branch_profile import (
	get_branch_profile_reassignment_state,
)


BRANCH_SETUP_DOCTYPE = "RetailEdge Branch Profile"
MAX_LINK_RESULTS = 20
MAX_LIST_RESULTS = 200

EDITABLE_FIELDS = (
	"profile_name",
	"enabled",
	"company",
	"branch",
	"is_default_for_company",
	"default_pos_profile",
	"default_pos_opening_cash_account",
	"default_cash_mode_of_payment",
	"default_warehouse",
	"default_source_warehouse",
	"default_target_warehouse",
	"default_returns_warehouse",
	"default_cost_center",
	"default_sales_cost_center",
	"default_expense_cost_center",
	"default_cash_account",
	"default_bank_account",
	"default_card_pos_account",
	"default_mobile_money_account",
	"enable_cashier_expense_control",
	"enable_daily_sales_audit",
	"enable_transaction_branch_attribution",
	"require_pos_closing_shift_for_audit",
	"variance_tolerance",
	"notes",
)

LIST_FIELDS = (
	"name",
	"profile_name",
	"enabled",
	"company",
	"branch",
	"is_default_for_company",
	"default_pos_profile",
	"default_warehouse",
	"modified",
)

LEAF_DEFAULT_FIELDS = {
	"default_warehouse": "Warehouse",
	"default_source_warehouse": "Warehouse",
	"default_target_warehouse": "Warehouse",
	"default_returns_warehouse": "Warehouse",
	"default_cost_center": "Cost Center",
	"default_sales_cost_center": "Cost Center",
	"default_expense_cost_center": "Cost Center",
	"default_pos_opening_cash_account": "Account",
	"default_cash_account": "Account",
	"default_bank_account": "Account",
	"default_card_pos_account": "Account",
	"default_mobile_money_account": "Account",
}


@frappe.whitelist()
def get_branch_setup_context(filters=None, limit: int = MAX_LIST_RESULTS) -> dict[str, Any]:
	_assert_read_permission()
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	query_filters: dict[str, Any] = {}
	for fieldname in ("company", "branch"):
		value = str(filters.get(fieldname) or "").strip()
		if value:
			query_filters[fieldname] = value
	enabled = str(filters.get("enabled") or "").strip().lower()
	if enabled in {"1", "yes", "true", "enabled"}:
		query_filters["enabled"] = 1
	elif enabled in {"0", "no", "false", "disabled"}:
		query_filters["enabled"] = 0
	query_filters = _scope_branch_setup_filters(query_filters)

	limit = min(max(cint(limit) or MAX_LIST_RESULTS, 1), MAX_LIST_RESULTS)
	rows = frappe.get_list(
		BRANCH_SETUP_DOCTYPE,
		filters=query_filters,
		fields=list(LIST_FIELDS),
		order_by="company asc, branch asc, modified desc",
		limit_page_length=limit,
	)
	return {
		"profiles": [dict(row) for row in rows],
		"can_create": bool(frappe.has_permission(BRANCH_SETUP_DOCTYPE, "create")),
		"can_write": bool(frappe.has_permission(BRANCH_SETUP_DOCTYPE, "write")),
		"can_create_branch": _can_create_branch(),
		"user": frappe.session.user,
		"user_name": frappe.utils.get_fullname(frappe.session.user),
	}


@frappe.whitelist()
def get_branch_setup(name: str) -> dict[str, Any]:
	doc = frappe.get_doc(BRANCH_SETUP_DOCTYPE, name)
	doc.check_permission("read")
	_assert_branch_setup_scope(doc)
	state = get_branch_profile_reassignment_state(doc.name)
	serialised_doc, configuration_issues = _serialise_for_edgesuite(doc)
	if configuration_issues:
		state = dict(state or {})
		state["configuration_issues"] = configuration_issues
		frappe.msgprint(
			_(
				"This Branch Setup contains older defaults that are no longer valid. "
				"EdgeSuite has left the affected fields blank for correction before the next save: {0}"
			).format(", ".join(issue["label"] for issue in configuration_issues)),
			title=_("Branch Setup needs correction"),
			indicator="orange",
		)
	return {
		"doc": serialised_doc,
		"state": state,
		"can_write": bool(doc.has_permission("write")),
		"can_create_branch": _can_create_branch(),
		"native_route": f"/app/retailedge-branch-profile/{doc.name}",
	}


@frappe.whitelist(methods=["POST"])
def save_branch_setup(values=None) -> dict[str, Any]:
	values = _coerce_values(values)
	name = str(values.get("name") or "").strip()
	if name:
		doc = frappe.get_doc(BRANCH_SETUP_DOCTYPE, name)
		doc.check_permission("write")
		_assert_branch_setup_scope(doc)
	else:
		if not frappe.has_permission(BRANCH_SETUP_DOCTYPE, "create"):
			frappe.throw(_("You do not have permission to create Branch Setup records."), frappe.PermissionError)
		doc = frappe.new_doc(BRANCH_SETUP_DOCTYPE)

	for fieldname in EDITABLE_FIELDS:
		if fieldname not in values:
			continue
		value = values.get(fieldname)
		if fieldname in {
			"enabled",
			"is_default_for_company",
			"enable_cashier_expense_control",
			"enable_daily_sales_audit",
			"enable_transaction_branch_attribution",
			"require_pos_closing_shift_for_audit",
		}:
			value = cint(value)
		setattr(doc, fieldname, value)

	if doc.is_new():
		doc.insert()
	else:
		doc.save()
	return {
		"name": doc.name,
		"doc": _serialise_doc(doc),
		"state": get_branch_profile_reassignment_state(doc.name),
		"native_route": f"/app/retailedge-branch-profile/{doc.name}",
	}


@frappe.whitelist(methods=["POST"])
def quick_create_branch(branch_name: str, company: str) -> dict[str, Any]:
	"""Create the ERPNext Branch master without leaving the EdgeSuite setup flow."""
	branch_name = str(branch_name or "").strip()
	company = str(company or "").strip()
	if not company:
		frappe.throw(_("Select a Company before creating a Branch."))
	if not branch_name:
		frappe.throw(_("Branch name is required."))
	if not _can_create_branch():
		frappe.throw(_("You do not have permission to create ERPNext Branch records."), frappe.PermissionError)
	if not (
		frappe.has_permission(BRANCH_SETUP_DOCTYPE, "create")
		or frappe.has_permission(BRANCH_SETUP_DOCTYPE, "write")
	):
		frappe.throw(_("You do not have permission to configure RetailEdge Branch Setup."), frappe.PermissionError)

	company_doc = frappe.get_doc("Company", company)
	company_doc.check_permission("read")
	if frappe.db.exists("Branch", branch_name):
		frappe.throw(_("Branch {0} already exists. Select the existing Branch instead.").format(branch_name))

	branch = frappe.new_doc("Branch")
	branch.branch = branch_name
	branch.insert()
	return {
		"value": branch.name,
		"label": branch.name,
		"description": _("ERPNext Branch created. Save Branch Setup to assign it to Company {0}.").format(company),
		"raw": {"name": branch.name, "branch": branch.branch},
	}


@frappe.whitelist()
def search_branch_setup_options(
	fieldname: str,
	txt: str = "",
	values=None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	_assert_read_permission()
	values = _coerce_values(values)
	limit = min(max(cint(limit) or MAX_LINK_RESULTS, 1), MAX_LINK_RESULTS)
	company = str(values.get("company") or "").strip()
	profile_name = str(values.get("name") or "").strip()

	if fieldname == "company":
		return search_link(
			"Company",
			txt or "",
			page_length=limit,
			reference_doctype=BRANCH_SETUP_DOCTYPE,
			link_fieldname="company",
		)
	if fieldname == "branch":
		if not company:
			return []
		return search_link(
			"Branch",
			txt or "",
			query="retailedge.branch_profile_queries.search_available_branch_setup_branches",
			filters={"company": company, "profile_name": profile_name},
			page_length=limit,
			reference_doctype=BRANCH_SETUP_DOCTYPE,
			link_fieldname="branch",
		)
	if fieldname == "reassignment_branch":
		if not company:
			return []
		return search_link(
			"Branch",
			txt or "",
			query="retailedge.branch_profile_queries.search_reassignment_target_branches",
			filters={"company": company, "profile_name": profile_name},
			page_length=limit,
			reference_doctype=BRANCH_SETUP_DOCTYPE,
			link_fieldname="branch",
		)
	if fieldname == "filter_branch":
		if not company:
			return []
		return search_link(
			"Branch",
			txt or "",
			query="retailedge.branch_profile_queries.search_configured_company_branches",
			filters={"company": company},
			page_length=limit,
			reference_doctype=BRANCH_SETUP_DOCTYPE,
			link_fieldname="branch",
		)

	search_config = {
		"default_pos_profile": ("POS Profile", {"company": company, "disabled": 0}),
		"default_warehouse": ("Warehouse", {"company": company, "is_group": 0, "disabled": 0}),
		"default_source_warehouse": ("Warehouse", {"company": company, "is_group": 0, "disabled": 0}),
		"default_target_warehouse": ("Warehouse", {"company": company, "is_group": 0, "disabled": 0}),
		"default_returns_warehouse": ("Warehouse", {"company": company, "is_group": 0, "disabled": 0}),
		"default_cost_center": ("Cost Center", {"company": company, "is_group": 0, "disabled": 0}),
		"default_sales_cost_center": ("Cost Center", {"company": company, "is_group": 0, "disabled": 0}),
		"default_expense_cost_center": ("Cost Center", {"company": company, "is_group": 0, "disabled": 0}),
		"default_pos_opening_cash_account": ("Account", {"company": company, "is_group": 0, "disabled": 0, "account_type": "Cash"}),
		"default_cash_account": ("Account", {"company": company, "is_group": 0, "disabled": 0, "account_type": "Cash"}),
		"default_bank_account": ("Account", {"company": company, "is_group": 0, "disabled": 0, "account_type": "Bank"}),
		"default_card_pos_account": ("Account", {"company": company, "is_group": 0, "disabled": 0, "root_type": "Asset", "account_type": ["in", ["", "Bank", "Cash"]]}),
		"default_mobile_money_account": ("Account", {"company": company, "is_group": 0, "disabled": 0, "root_type": "Asset", "account_type": ["in", ["", "Bank", "Cash"]]}),
		"default_cash_mode_of_payment": ("Mode of Payment", {}),
	}
	if fieldname not in search_config:
		frappe.throw(_("Unsupported Branch Setup search field: {0}").format(fieldname))
	if fieldname != "default_cash_mode_of_payment" and not company:
		return []
	doctype, filters = search_config[fieldname]
	return search_link(
		doctype,
		txt or "",
		filters={key: value for key, value in filters.items() if value not in (None, "")},
		page_length=limit,
		reference_doctype=BRANCH_SETUP_DOCTYPE,
		link_fieldname=fieldname,
	)


def _serialise_for_edgesuite(doc) -> tuple[dict[str, Any], list[dict[str, str]]]:
	result = _serialise_doc(doc)
	issues = _get_legacy_default_issues(doc)
	for issue in issues:
		result[issue["fieldname"]] = ""
	return result, issues


def _get_legacy_default_issues(doc) -> list[dict[str, str]]:
	issues: list[dict[str, str]] = []
	company = str(getattr(doc, "company", None) or "").strip()
	for fieldname, doctype in LEAF_DEFAULT_FIELDS.items():
		value = str(getattr(doc, fieldname, None) or "").strip()
		if not value:
			continue
		label = doc.meta.get_label(fieldname) or fieldname
		if not frappe.db.exists(doctype, value):
			issues.append({"fieldname": fieldname, "label": label, "reason": _("record no longer exists")})
			continue
		linked_company = frappe.db.get_value(doctype, value, "company")
		if company and linked_company is not None and linked_company != company:
			issues.append({"fieldname": fieldname, "label": label, "reason": _("belongs to another Company")})
			continue
		is_group = frappe.db.get_value(doctype, value, "is_group")
		if is_group is not None and cint(is_group):
			issues.append({"fieldname": fieldname, "label": label, "reason": _("must be a leaf record")})
			continue
		if doctype in {"Warehouse", "Account", "Cost Center"} and frappe.get_meta(doctype).has_field("disabled"):
			disabled = frappe.db.get_value(doctype, value, "disabled")
			if disabled is not None and cint(disabled):
				issues.append({"fieldname": fieldname, "label": label, "reason": _("is disabled")})
				continue
		if doctype == "Account" and not _account_matches_semantics(fieldname, value):
			issues.append({"fieldname": fieldname, "label": label, "reason": _("has an incompatible Account Type")})
	return issues


def _account_matches_semantics(fieldname: str, account: str) -> bool:
	account_type, root_type = frappe.db.get_value("Account", account, ["account_type", "root_type"]) or ("", "")
	account_type = str(account_type or "").strip()
	root_type = str(root_type or "").strip()
	if fieldname in {"default_pos_opening_cash_account", "default_cash_account"}:
		return account_type == "Cash"
	if fieldname == "default_bank_account":
		return account_type == "Bank"
	if fieldname in {"default_card_pos_account", "default_mobile_money_account"}:
		return root_type == "Asset" and account_type in {"", "Bank", "Cash"}
	return True


def _serialise_doc(doc) -> dict[str, Any]:
	result = {"name": doc.name}
	for fieldname in EDITABLE_FIELDS:
		result[fieldname] = getattr(doc, fieldname, None)
	return result


def _coerce_values(values) -> dict[str, Any]:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	return dict(values or {})


def _scope_branch_setup_filters(filters: dict[str, Any]) -> dict[str, Any]:
	from retailedge.branch_assignment import get_assignment_branches, has_branch_assignments
	from retailedge.branch_context import get_user_allowed_branches, user_has_global_branch_access
	from retailedge.operating_context import get_allowed_operating_branches

	user = frappe.session.user
	if user_has_global_branch_access(user=user):
		return filters
	company = str(filters.get("company") or "").strip()
	if company:
		branches = get_allowed_operating_branches(company=company, user=user)
	elif has_branch_assignments(user=user):
		branches = get_assignment_branches(user=user)
	else:
		branches = get_user_allowed_branches(user=user).get("branches") or []
	requested_branch = filters.get("branch")
	if requested_branch and requested_branch not in branches:
		filters["name"] = "__no_visible_branch_setup__"
	elif branches:
		filters["branch"] = ["in", list(dict.fromkeys(branches))]
	else:
		filters["name"] = "__no_visible_branch_setup__"
	return filters


def _assert_branch_setup_scope(doc) -> None:
	from retailedge.branch_context import user_has_global_branch_access
	from retailedge.operating_context import get_allowed_operating_branches

	user = frappe.session.user
	if user_has_global_branch_access(user=user):
		return
	if doc.branch not in get_allowed_operating_branches(company=doc.company, user=user):
		frappe.throw(_("You do not have access to this Branch Setup."), frappe.PermissionError)


def _can_create_branch() -> bool:
	try:
		return bool(frappe.db.exists("DocType", "Branch") and frappe.has_permission("Branch", "create"))
	except Exception:
		return False


def _assert_read_permission() -> None:
	if not frappe.has_permission(BRANCH_SETUP_DOCTYPE, "read"):
		frappe.throw(_("You do not have permission to view Branch Setup."), frappe.PermissionError)
