from __future__ import annotations

import frappe


PROFILE_DEFAULT_FIELDS = [
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
]


def get_branch_profile(company=None, branch=None, user=None, pos_profile=None, warehouse=None, active_only=True):
	if not _has_doctype("RetailEdge Branch Profile"):
		return None
	if not any([company, branch, user, pos_profile, warehouse]):
		return None

	candidates = []
	if company and branch:
		candidates.append({"company": company, "branch": branch})
	elif branch:
		candidates.append({"branch": branch})
	if company:
		candidates.append({"company": company, "is_default_for_company": 1})
	if user:
		for row in get_user_branch_profiles(user=user, company=company):
			if row.get("name"):
				candidates.append({"name": row.get("name")})

	for filters in candidates:
		profile = _get_profile_by_filters(filters, active_only=active_only)
		if not profile:
			continue
		if pos_profile and getattr(profile, "default_pos_profile", None) not in (None, "", pos_profile):
			continue
		if warehouse and not _profile_matches_warehouse(profile, warehouse):
			continue
		return profile

	if pos_profile or warehouse:
		scan_filters = {"enabled": 1} if active_only else {}
		if company:
			scan_filters["company"] = company
		for row in frappe.get_all(
			"RetailEdge Branch Profile",
			filters=scan_filters,
			fields=["name"],
			limit_page_length=50,
			order_by="is_default_for_company desc, modified desc",
		):
			profile = frappe.get_doc("RetailEdge Branch Profile", row.get("name"))
			if user and not _profile_has_user(profile, user):
				continue
			if pos_profile and getattr(profile, "default_pos_profile", None) not in (None, "", pos_profile):
				continue
			if warehouse and not _profile_matches_warehouse(profile, warehouse):
				continue
			return profile
	return None


def get_branch_profile_defaults(company=None, branch=None, user=None, pos_profile=None, warehouse=None):
	profile = get_branch_profile(
		company=company,
		branch=branch,
		user=user,
		pos_profile=pos_profile,
		warehouse=warehouse,
		active_only=True,
	)
	if not profile:
		return {}
	return {fieldname: getattr(profile, fieldname, None) for fieldname in PROFILE_DEFAULT_FIELDS}


def get_user_branch_profiles(user=None, company=None):
	if not user or not _has_doctype("RetailEdge Branch Profile") or not _has_doctype("RetailEdge Branch Profile User"):
		return []
	rows = frappe.get_all(
		"RetailEdge Branch Profile User",
		filters={"user": user, "parenttype": "RetailEdge Branch Profile"},
		fields=["parent", "role_type", "is_default"],
		limit_page_length=0,
		order_by="idx asc, creation asc",
	)
	profile_names = [row.get("parent") for row in rows if row.get("parent")]
	if not profile_names:
		return []
	profile_filters = {"name": ["in", profile_names]}
	if company:
		profile_filters["company"] = company
	profiles = frappe.get_all(
		"RetailEdge Branch Profile",
		filters=profile_filters,
		fields=["name", "profile_name", "company", "branch", "enabled", "is_default_for_company", "default_pos_profile"],
		limit_page_length=0,
		order_by="modified desc",
	)
	return profiles


def get_default_branch_for_user(user=None, company=None):
	profiles = get_user_branch_profiles(user=user, company=company)
	if not profiles:
		return None
	default_profiles = [row for row in profiles if row.get("is_default_for_company")]
	if len(default_profiles) == 1:
		return default_profiles[0].get("branch")
	if len(profiles) == 1:
		return profiles[0].get("branch")
	return None


def validate_branch_profile(doc):
	if not getattr(doc, "company", None):
		frappe.throw("Company is required.")
	if not getattr(doc, "branch", None):
		frappe.throw("Branch is required.")
	if getattr(doc, "enabled", 1):
		duplicate_filters = {
			"name": ["!=", doc.name or ""],
			"company": doc.company,
			"branch": doc.branch,
			"enabled": 1,
		}
		if frappe.db.exists("RetailEdge Branch Profile", duplicate_filters):
			frappe.throw("An enabled RetailEdge Branch Profile already exists for this Company and Branch.")
		if getattr(doc, "is_default_for_company", 0):
			default_filters = {
				"name": ["!=", doc.name or ""],
				"company": doc.company,
				"is_default_for_company": 1,
				"enabled": 1,
			}
			if frappe.db.exists("RetailEdge Branch Profile", default_filters):
				frappe.throw("Only one enabled default RetailEdge Branch Profile is allowed per Company.")


def _has_doctype(doctype):
	try:
		return bool(frappe.db.exists("DocType", doctype))
	except Exception:
		return False


def _get_profile_by_filters(filters, active_only=True):
	query_filters = dict(filters or {})
	if active_only and _has_doctype("RetailEdge Branch Profile"):
		query_filters["enabled"] = 1
	name = frappe.db.get_value("RetailEdge Branch Profile", query_filters, "name")
	if not name:
		return None
	try:
		return frappe.get_doc("RetailEdge Branch Profile", name)
	except Exception:
		return None


def _profile_has_user(profile, user):
	for table_field in ("default_cashiers", "default_managers", "default_auditors"):
		for row in getattr(profile, table_field, []) or []:
			row_user = getattr(row, "user", None) or (row.get("user") if isinstance(row, dict) else None)
			if row_user == user:
				return True
	return False


def _profile_matches_warehouse(profile, warehouse):
	return warehouse in {
		getattr(profile, "default_warehouse", None),
		getattr(profile, "default_source_warehouse", None),
		getattr(profile, "default_target_warehouse", None),
		getattr(profile, "default_returns_warehouse", None),
	}
