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

# ERPNext v16 Branch is not Company-bound by a native `company` column. The
# RetailEdge Branch Profile's own Company + Branch pair is therefore the binding.
COMPANY_LINK_FIELDS = {
	"default_pos_profile": ("POS Profile", "company"),
	"default_warehouse": ("Warehouse", "company"),
	"default_source_warehouse": ("Warehouse", "company"),
	"default_target_warehouse": ("Warehouse", "company"),
	"default_returns_warehouse": ("Warehouse", "company"),
	"default_cost_center": ("Cost Center", "company"),
	"default_sales_cost_center": ("Cost Center", "company"),
	"default_expense_cost_center": ("Cost Center", "company"),
	"default_pos_opening_cash_account": ("Account", "company"),
	"default_cash_account": ("Account", "company"),
	"default_bank_account": ("Account", "company"),
	"default_card_pos_account": ("Account", "company"),
	"default_mobile_money_account": ("Account", "company"),
}

LEAF_FIELDS = {
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

ACCOUNT_SEMANTICS = {
	"default_pos_opening_cash_account": {"account_types": {"Cash"}},
	"default_cash_account": {"account_types": {"Cash"}},
	"default_bank_account": {"account_types": {"Bank"}},
	# Card/POS and mobile-money settlement ledgers can be Bank/Cash typed or a
	# dedicated untyped current-asset ledger, but must never be income/expense,
	# receivable/payable or another non-asset control account.
	"default_card_pos_account": {"account_types": {"", "Bank", "Cash"}, "root_types": {"Asset"}},
	"default_mobile_money_account": {"account_types": {"", "Bank", "Cash"}, "root_types": {"Asset"}},
}


def get_branch_profile(
	company=None,
	branch=None,
	user=None,
	pos_profile=None,
	warehouse=None,
	active_only=True,
):
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


def get_exact_branch_profile(company=None, branch=None, active_only=True):
	"""Return only the exact Company + Branch setup; never fall back to company default."""
	if not company or not branch or not _has_doctype("RetailEdge Branch Profile"):
		return None
	filters = {"company": company, "branch": branch}
	if active_only:
		filters["enabled"] = 1
	return _get_profile_by_filters(filters, active_only=False)


def get_enabled_branch_profiles(company=None):
	"""Internal setup lookup used to bind ERPNext Branch to a RetailEdge Company."""
	if not _has_doctype("RetailEdge Branch Profile"):
		return []
	filters = {"enabled": 1}
	if company:
		filters["company"] = company
	return frappe.get_all(
		"RetailEdge Branch Profile",
		filters=filters,
		fields=[
			"name",
			"profile_name",
			"company",
			"branch",
			"enabled",
			"is_default_for_company",
			"default_pos_profile",
		],
		limit_page_length=0,
		order_by="company asc, branch asc",
	)


def has_enabled_branch_profiles(company=None):
	return bool(get_enabled_branch_profiles(company=company))


def get_enabled_branch_profile_companies(branch=None):
	if not branch or not _has_doctype("RetailEdge Branch Profile"):
		return []
	rows = frappe.get_all(
		"RetailEdge Branch Profile",
		filters={"branch": branch, "enabled": 1},
		fields=["company"],
		limit_page_length=0,
		order_by="company asc",
	)
	return list(dict.fromkeys(row.get("company") for row in rows if row.get("company")))


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
	if (
		not user
		or not _has_doctype("RetailEdge Branch Profile")
		or not _has_doctype("RetailEdge Branch Profile User")
	):
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
		fields=[
			"name",
			"profile_name",
			"company",
			"branch",
			"enabled",
			"is_default_for_company",
			"default_pos_profile",
		],
		limit_page_length=0,
		order_by="modified desc",
	)
	return profiles


def get_user_pos_profiles(user=None, company=None):
	"""Return enabled ERPNext POS Profiles explicitly assigned to the user.

	Generic permission to read/administer POS Profile is deliberately not treated
	as operational POS entitlement.
	"""
	user = user or getattr(frappe.session, "user", None)
	if not user or not _has_doctype("POS Profile") or not _has_doctype("POS Profile User"):
		return []
	try:
		assignments = frappe.get_all(
			"POS Profile User",
			filters={"user": user, "parenttype": "POS Profile"},
			fields=["parent", "default"],
			limit_page_length=0,
			order_by="default desc, idx asc",
		)
	except Exception:
		return []
	profile_names = [row.get("parent") for row in assignments if row.get("parent")]
	if not profile_names:
		return []

	filters = {"name": ["in", profile_names]}
	if _doctype_has_field("POS Profile", "disabled"):
		filters["disabled"] = 0
	if company and _doctype_has_field("POS Profile", "company"):
		filters["company"] = company
	try:
		return frappe.get_all(
			"POS Profile",
			filters=filters,
			fields=["name", "company", "disabled"],
			limit_page_length=0,
			order_by="name asc",
		)
	except Exception:
		return []


def user_has_pos_profile_assignment(user=None):
	return bool(get_user_pos_profiles(user=user))


def resolve_branch_pos_requirement(company=None, branch=None, user=None):
	"""Resolve the conditional POS requirement for one operating Company/Branch."""
	user = user or getattr(frappe.session, "user", None)
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	assigned_profiles = get_user_pos_profiles(user=user)
	pos_required = bool(assigned_profiles)
	result = {
		"pos_required": pos_required,
		"pos_profile": "",
		"pos_ready": True,
		"pos_message": "",
	}

	if not pos_required:
		return result
	if not company or not branch:
		result["pos_ready"] = False
		result["pos_message"] = "Choose a Company and Branch to resolve your required POS Profile."
		return result

	profile = get_exact_branch_profile(company=company, branch=branch, active_only=True)
	if not profile:
		result["pos_ready"] = False
		result["pos_message"] = f"No enabled Branch Setup exists for Branch {branch} in Company {company}."
		return result

	pos_profile = str(getattr(profile, "default_pos_profile", None) or "").strip()
	if not pos_profile:
		result["pos_ready"] = False
		result["pos_message"] = f"No POS Profile is configured for your access in Branch {branch}."
		return result
	if not frappe.db.exists("POS Profile", pos_profile):
		result["pos_ready"] = False
		result["pos_message"] = f"The POS Profile configured for Branch {branch} does not exist."
		return result
	if not frappe.has_permission("POS Profile", "read", doc=pos_profile):
		result["pos_ready"] = False
		result["pos_message"] = f"You do not have permission to use the POS Profile configured for Branch {branch}."
		return result
	if _doctype_has_field("POS Profile", "disabled") and frappe.db.get_value(
		"POS Profile", pos_profile, "disabled"
	):
		result["pos_ready"] = False
		result["pos_message"] = f"The POS Profile configured for Branch {branch} is disabled."
		return result

	profile_company = ""
	if _doctype_has_field("POS Profile", "company"):
		profile_company = str(frappe.db.get_value("POS Profile", pos_profile, "company") or "").strip()
	if profile_company and profile_company != company:
		result["pos_ready"] = False
		result["pos_message"] = f"The POS Profile configured for Branch {branch} belongs to another Company."
		return result

	assigned_names = {str(row.get("name") or "").strip() for row in assigned_profiles}
	if pos_profile not in assigned_names:
		result["pos_ready"] = False
		result["pos_message"] = f"You are not assigned to the POS Profile configured for Branch {branch}."
		return result

	result["pos_profile"] = pos_profile
	return result


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
	_validate_company_links(doc)
	_validate_leaf_defaults(doc)
	_validate_account_semantics(doc)
	if getattr(doc, "enabled", 1):
		duplicate_filters = {
			"name": ["!=", doc.name or ""],
			"company": doc.company,
			"branch": doc.branch,
			"enabled": 1,
		}
		if frappe.db.exists("RetailEdge Branch Profile", duplicate_filters):
			frappe.throw("An enabled RetailEdge Branch Profile already exists for this Company and Branch.")

		existing_company = frappe.db.get_value(
			"RetailEdge Branch Profile",
			{
				"name": ["!=", doc.name or ""],
				"branch": doc.branch,
				"enabled": 1,
			},
			"company",
		)
		if existing_company and existing_company != doc.company:
			frappe.throw(
				f"Branch {doc.branch} is already configured for Company {existing_company}. "
				"Use a distinct ERPNext Branch for each Company."
			)

		if getattr(doc, "is_default_for_company", 0):
			default_filters = {
				"name": ["!=", doc.name or ""],
				"company": doc.company,
				"is_default_for_company": 1,
				"enabled": 1,
			}
			if frappe.db.exists("RetailEdge Branch Profile", default_filters):
				frappe.throw("Only one enabled default RetailEdge Branch Profile is allowed per Company.")


def _validate_company_links(doc):
	for fieldname, (doctype, company_field) in COMPANY_LINK_FIELDS.items():
		value = getattr(doc, fieldname, None)
		if not value:
			continue
		linked_company = frappe.db.get_value(doctype, value, company_field)
		if linked_company is None:
			frappe.throw(f"{doctype} {value} does not exist.")
		if linked_company != doc.company:
			label = doc.meta.get_label(fieldname) or fieldname
			frappe.throw(f"{label} must belong to Company {doc.company}.")


def _validate_leaf_defaults(doc):
	for fieldname, doctype in LEAF_FIELDS.items():
		value = getattr(doc, fieldname, None)
		if not value:
			continue
		is_group = frappe.db.get_value(doctype, value, "is_group")
		if is_group is None:
			frappe.throw(f"{doctype} {value} does not exist.")
		if int(is_group):
			label = doc.meta.get_label(fieldname) or fieldname
			frappe.throw(f"{label} must be a leaf {doctype}.")
		if doctype in {"Warehouse", "Account", "Cost Center"} and _doctype_has_field(doctype, "disabled"):
			disabled = frappe.db.get_value(doctype, value, "disabled")
			if disabled is not None and int(disabled):
				label = doc.meta.get_label(fieldname) or fieldname
				frappe.throw(f"{label} must be enabled.")


def _validate_account_semantics(doc):
	for fieldname, rules in ACCOUNT_SEMANTICS.items():
		value = getattr(doc, fieldname, None)
		if not value:
			continue
		account_type, root_type = frappe.db.get_value("Account", value, ["account_type", "root_type"]) or ("", "")
		account_type = str(account_type or "").strip()
		root_type = str(root_type or "").strip()
		allowed_types = rules.get("account_types")
		allowed_roots = rules.get("root_types")
		label = doc.meta.get_label(fieldname) or fieldname
		if allowed_types is not None and account_type not in allowed_types:
			frappe.throw(
				f"{label} has the wrong ERPNext Account Type. Allowed: {', '.join(sorted(t or 'Untyped Asset' for t in allowed_types))}."
			)
		if allowed_roots is not None and root_type not in allowed_roots:
			frappe.throw(f"{label} must use an Asset account.")


def _has_doctype(doctype):
	try:
		return bool(frappe.db.exists("DocType", doctype))
	except Exception:
		return False


def _doctype_has_field(doctype, fieldname):
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
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
