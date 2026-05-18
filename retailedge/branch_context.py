from __future__ import annotations

import frappe

from retailedge.integrations.branch_context import (
	get_active_branch as _get_coreedge_active_branch,
	get_user_allowed_branches as _get_coreedge_allowed_branches,
)
from retailedge.integrations.coreedge import get_coreedge_status


BRANCH_FIELD_CANDIDATES = ["branch", "set_branch", "service_branch", "retail_branch", "default_branch"]
COMPANY_FIELD_CANDIDATES = ["company"]
CASHIER_FIELD_CANDIDATES = ["user", "cashier", "owner"]
POS_PROFILE_FIELD_CANDIDATES = ["pos_profile", "pos_profile_name"]
OPENING_SHIFT_LINK_CANDIDATES = ["pos_opening_shift", "opening_shift", "linked_pos_opening_shift"]
DATE_FIELD_CANDIDATES = [
	"posting_date",
	"opening_date",
	"closing_date",
	"period_start_date",
	"period_end_date",
	"transaction_date",
	"creation",
]
GLOBAL_BRANCH_ACCESS_ROLES = {
	"System Manager",
	"Accounts Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
}
SUPPORTED_RETAILEDGE_BRANCH_DOCTYPES = (
	"RetailEdge Cashier Expense",
	"RetailEdge Daily Sales Audit",
)


def has_doctype(doctype: str) -> bool:
	if not doctype:
		return False
	cache = getattr(frappe.local, "retailedge_has_doctype_cache", None)
	if cache is None:
		cache = {}
		frappe.local.retailedge_has_doctype_cache = cache
	if doctype in cache:
		return cache[doctype]
	try:
		cache[doctype] = bool(frappe.db.exists("DocType", doctype))
	except Exception:
		cache[doctype] = False
	return cache[doctype]


def has_field(doctype: str, fieldname: str) -> bool:
	if not doctype or not fieldname or not has_doctype(doctype):
		return False
	cache = getattr(frappe.local, "retailedge_has_field_cache", None)
	if cache is None:
		cache = {}
		frappe.local.retailedge_has_field_cache = cache
	cache_key = (doctype, fieldname)
	if cache_key in cache:
		return cache[cache_key]
	try:
		cache[cache_key] = bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		cache[cache_key] = False
	return cache[cache_key]


def get_first_existing_field(doctype: str, candidate_fields: list[str]) -> str | None:
	for fieldname in candidate_fields or []:
		if has_field(doctype, fieldname):
			return fieldname
	return None


def get_coreedge_branch_context(user=None, company=None):
	result = {"branch": None, "company": company, "source": None, "messages": []}
	try:
		status = get_coreedge_status()
	except Exception:
		status = {"branch_context_enabled": False}
	if not status.get("branch_context_enabled"):
		result["messages"].append("CoreEdge branch context is not enabled.")
		return result

	try:
		active = _get_coreedge_active_branch(user=user)
	except Exception:
		active = None
		result["messages"].append("CoreEdge active branch lookup failed.")

	if isinstance(active, dict):
		result["branch"] = (
			active.get("branch")
			or active.get("active_branch")
			or active.get("branch_name")
			or active.get("name")
		)
		result["company"] = active.get("company") or company
	elif isinstance(active, str):
		result["branch"] = active

	if result["branch"]:
		result["source"] = "CoreEdge"
	return result


def get_user_allowed_branches(user=None, company=None):
	user = user or _current_user()
	result = {"branches": [], "source": None, "messages": []}
	branches = []

	coreedge = get_coreedge_branch_context(user=user, company=company)
	try:
		coreedge_allowed = list(_get_coreedge_allowed_branches(user=user) or [])
	except Exception:
		coreedge_allowed = []
		result["messages"].append("CoreEdge allowed branch lookup failed.")
	if coreedge_allowed:
		branches.extend(coreedge_allowed)
		result["source"] = "CoreEdge"

	if has_doctype("User Permission"):
		try:
			user_permission_rows = frappe.get_all(
				"User Permission",
				filters={
					"user": user,
					"allow": "Branch",
					"applicable_for": ["in", [None, "", "RetailEdge Cashier Expense", "RetailEdge Daily Sales Audit"]],
				},
				fields=["for_value"],
				limit_page_length=0,
			)
		except Exception:
			user_permission_rows = []
			result["messages"].append("User Permission branch lookup failed.")
		for row in user_permission_rows:
			value = row.get("for_value")
			if value:
				branches.append(value)
				result["source"] = result["source"] or "User Permission"

	try:
		default_branch = frappe.defaults.get_user_default("Branch", user=user) or frappe.defaults.get_user_default("Branch")
	except Exception:
		default_branch = None
	if default_branch:
		branches.append(default_branch)
		result["source"] = result["source"] or "User Default"
	elif coreedge.get("branch"):
		branches.append(coreedge["branch"])
		result["source"] = result["source"] or coreedge.get("source")

	if company and has_doctype("Branch") and has_field("Branch", "company"):
		company_branches = set(
			frappe.get_all("Branch", filters={"company": company}, pluck="name", limit_page_length=0) or []
		)
		if company_branches:
			branches = [branch for branch in branches if branch in company_branches]

	result["branches"] = _dedupe(branches)
	return result


def user_has_global_branch_access(user=None):
	user = user or _current_user()
	if user == "Administrator":
		return True
	try:
		roles = set(frappe.get_roles(user))
	except Exception:
		roles = set()
	return any(role in roles for role in GLOBAL_BRANCH_ACCESS_ROLES)


def validate_user_branch_access(branch, user=None, company=None, throw=True):
	user = user or _current_user()
	if not branch:
		return {"allowed": True, "branch": branch, "user": user, "reason": "empty_branch"}
	if user_has_global_branch_access(user=user):
		return {"allowed": True, "branch": branch, "user": user, "reason": "global_access"}

	allowed_info = get_user_allowed_branches(user=user, company=company)
	allowed_branches = allowed_info.get("branches") or []
	if not allowed_branches:
		return {
			"allowed": True,
			"branch": branch,
			"user": user,
			"reason": "no_branch_restrictions_configured",
		}
	if branch in allowed_branches:
		return {"allowed": True, "branch": branch, "user": user, "reason": "allowed_branch"}

	result = {"allowed": False, "branch": branch, "user": user, "reason": "branch_not_allowed"}
	if throw:
		frappe.throw(f"You do not have access to Branch {branch}.", frappe.PermissionError)
	return result


def resolve_branch_from_pos_profile(pos_profile, company=None):
	result = {"branch": None, "company": company, "source": None, "messages": []}
	doc = _coerce_doc("POS Profile", pos_profile)
	if not doc:
		result["messages"].append("POS Profile could not be loaded.")
		return result
	branch_field = get_first_existing_field("POS Profile", BRANCH_FIELD_CANDIDATES)
	company_field = get_first_existing_field("POS Profile", COMPANY_FIELD_CANDIDATES)
	if company_field:
		result["company"] = getattr(doc, company_field, None) or company
	if branch_field:
		result["branch"] = getattr(doc, branch_field, None)
		result["source"] = f"POS Profile.{branch_field}"
	elif getattr(doc, "retailedge_branch", None):
		result["branch"] = getattr(doc, "retailedge_branch", None)
		result["source"] = getattr(doc, "retailedge_branch_source", None) or "POS Profile.retailedge_branch"
	else:
		result["messages"].append("POS Profile has no branch-like field.")
	return result


def resolve_branch_from_opening_shift(opening_shift, company=None):
	result = {
		"branch": None,
		"company": company,
		"pos_profile": None,
		"cashier": None,
		"source": None,
		"messages": [],
	}
	doc = _coerce_doc("POS Opening Shift", opening_shift)
	if not doc:
		result["messages"].append("POS Opening Shift could not be loaded.")
		return result
	branch_field = get_first_existing_field("POS Opening Shift", BRANCH_FIELD_CANDIDATES)
	company_field = get_first_existing_field("POS Opening Shift", COMPANY_FIELD_CANDIDATES)
	pos_profile_field = get_first_existing_field("POS Opening Shift", POS_PROFILE_FIELD_CANDIDATES)
	cashier_field = get_first_existing_field("POS Opening Shift", CASHIER_FIELD_CANDIDATES)
	if company_field:
		result["company"] = getattr(doc, company_field, None) or company
	if pos_profile_field:
		result["pos_profile"] = getattr(doc, pos_profile_field, None)
	if cashier_field:
		result["cashier"] = getattr(doc, cashier_field, None)
	if branch_field:
		result["branch"] = getattr(doc, branch_field, None)
		result["source"] = f"POS Opening Shift.{branch_field}"
	elif getattr(doc, "retailedge_branch", None):
		result["branch"] = getattr(doc, "retailedge_branch", None)
		result["source"] = getattr(doc, "retailedge_branch_source", None) or "POS Opening Shift.retailedge_branch"
	if not result["branch"] and result.get("pos_profile"):
		profile_result = resolve_branch_from_pos_profile(result["pos_profile"], company=result.get("company"))
		result["branch"] = profile_result.get("branch")
		result["company"] = profile_result.get("company") or result.get("company")
		result["source"] = profile_result.get("source")
		result["messages"].extend(profile_result.get("messages") or [])
	return result


def resolve_branch_from_closing_shift(closing_shift, company=None):
	result = {
		"branch": None,
		"company": company,
		"pos_profile": None,
		"cashier": None,
		"pos_opening_shift": None,
		"source": None,
		"messages": [],
	}
	doc = _coerce_doc("POS Closing Shift", closing_shift)
	if not doc:
		result["messages"].append("POS Closing Shift could not be loaded.")
		return result
	branch_field = get_first_existing_field("POS Closing Shift", BRANCH_FIELD_CANDIDATES)
	company_field = get_first_existing_field("POS Closing Shift", COMPANY_FIELD_CANDIDATES)
	pos_profile_field = get_first_existing_field("POS Closing Shift", POS_PROFILE_FIELD_CANDIDATES)
	cashier_field = get_first_existing_field("POS Closing Shift", CASHIER_FIELD_CANDIDATES)
	opening_link_field = get_first_existing_field("POS Closing Shift", OPENING_SHIFT_LINK_CANDIDATES)
	if company_field:
		result["company"] = getattr(doc, company_field, None) or company
	if pos_profile_field:
		result["pos_profile"] = getattr(doc, pos_profile_field, None)
	if cashier_field:
		result["cashier"] = getattr(doc, cashier_field, None)
	if opening_link_field:
		result["pos_opening_shift"] = getattr(doc, opening_link_field, None)
	if branch_field:
		result["branch"] = getattr(doc, branch_field, None)
		result["source"] = f"POS Closing Shift.{branch_field}"
	elif getattr(doc, "retailedge_branch", None):
		result["branch"] = getattr(doc, "retailedge_branch", None)
		result["source"] = getattr(doc, "retailedge_branch_source", None) or "POS Closing Shift.retailedge_branch"
	if not result["branch"] and result.get("pos_opening_shift"):
		opening_result = resolve_branch_from_opening_shift(
			result["pos_opening_shift"], company=result.get("company")
		)
		for key in ("branch", "company", "pos_profile", "cashier"):
			result[key] = opening_result.get(key) or result.get(key)
		result["source"] = opening_result.get("source")
		result["messages"].extend(opening_result.get("messages") or [])
	if not result["branch"] and result.get("pos_profile"):
		profile_result = resolve_branch_from_pos_profile(result["pos_profile"], company=result.get("company"))
		result["branch"] = profile_result.get("branch")
		result["company"] = profile_result.get("company") or result.get("company")
		result["source"] = profile_result.get("source") or result.get("source")
		result["messages"].extend(profile_result.get("messages") or [])
	return result


def resolve_branch_from_warehouse(warehouse, company=None):
	result = {"branch": None, "company": company, "source": None, "messages": []}
	doc = _coerce_doc("Warehouse", warehouse)
	if not doc:
		return result
	branch_field = get_first_existing_field("Warehouse", BRANCH_FIELD_CANDIDATES)
	company_field = get_first_existing_field("Warehouse", COMPANY_FIELD_CANDIDATES)
	if company_field:
		result["company"] = getattr(doc, company_field, None) or company
	if branch_field:
		result["branch"] = getattr(doc, branch_field, None)
		result["source"] = f"Warehouse.{branch_field}"
	return result


def resolve_branch_from_user(user=None, company=None):
	user = user or _current_user()
	result = {"branch": None, "company": company, "source": None, "messages": []}
	try:
		default_branch = frappe.defaults.get_user_default("Branch", user=user) or frappe.defaults.get_user_default("Branch")
	except Exception:
		default_branch = None
	if default_branch:
		result["branch"] = default_branch
		result["source"] = "User Default"
		return result

	allowed = get_user_allowed_branches(user=user, company=company)
	if len(allowed.get("branches") or []) == 1:
		result["branch"] = allowed["branches"][0]
		result["source"] = allowed.get("source") or "User Permission"
		result["messages"].extend(allowed.get("messages") or [])
		return result

	coreedge = get_coreedge_branch_context(user=user, company=company)
	result["messages"].extend(coreedge.get("messages") or [])
	if coreedge.get("branch"):
		result["branch"] = coreedge["branch"]
		result["company"] = coreedge.get("company") or company
		result["source"] = coreedge.get("source")
	return result


def resolve_branch_from_branch_profile(company=None, branch=None, user=None, pos_profile=None, warehouse=None):
	result = {
		"branch": branch,
		"company": company,
		"pos_profile": pos_profile,
		"cashier": user,
		"warehouse": warehouse,
		"source": None,
		"messages": [],
		"defaults": {},
	}
	try:
		from retailedge.branch_profile import get_branch_profile, get_branch_profile_defaults
	except Exception:
		result["messages"].append("RetailEdge Branch Profile helpers are not available.")
		return result

	profile = get_branch_profile(
		company=company,
		branch=branch,
		user=user,
		pos_profile=pos_profile,
		warehouse=warehouse,
		active_only=True,
	)
	if not profile:
		return result

	profile_dict = _as_dict(profile)
	if not any(profile_dict.get(key) for key in ("name", "profile_name", "company", "branch")):
		result["messages"].append("RetailEdge Branch Profile result did not contain profile context.")
		return result
	defaults = get_branch_profile_defaults(
		company=company,
		branch=profile_dict.get("branch") or branch,
		user=user,
		pos_profile=pos_profile,
		warehouse=warehouse,
	)
	result["branch"] = profile_dict.get("branch") or branch
	result["company"] = profile_dict.get("company") or company
	result["pos_profile"] = result.get("pos_profile") or defaults.get("default_pos_profile")
	result["warehouse"] = result.get("warehouse") or defaults.get("default_warehouse")
	result["source"] = "RetailEdge Branch Profile"
	result["defaults"] = defaults
	return result


def resolve_retailedge_branch_context(
	doc=None,
	doctype=None,
	name=None,
	company=None,
	branch=None,
	pos_profile=None,
	cashier=None,
	pos_opening_shift=None,
	pos_closing_shift=None,
	warehouse=None,
	user=None,
	prefer_coreedge=True,
):
	doc = _coerce_any_doc(doc=doc, doctype=doctype, name=name)
	result = {
		"branch": branch,
		"company": company,
		"pos_profile": pos_profile,
		"cashier": cashier,
		"pos_opening_shift": pos_opening_shift,
		"pos_closing_shift": pos_closing_shift,
		"warehouse": warehouse,
		"source": None,
		"source_map": {},
		"access": {"allowed": True, "reason": "unvalidated"},
		"messages": [],
		"defaults": {},
	}

	if doc:
		result = _seed_context_from_doc(result, doc)

	if result.get("branch"):
		result["source"] = result["source"] or "Explicit Branch"
		result["source_map"]["branch"] = result["source"]
	else:
		for resolver in (
			lambda: _resolve_branch_from_doc_field(doc),
			lambda: resolve_branch_from_closing_shift(result.get("pos_closing_shift"), company=result.get("company"))
			if result.get("pos_closing_shift")
			else None,
			lambda: resolve_branch_from_opening_shift(result.get("pos_opening_shift"), company=result.get("company"))
			if result.get("pos_opening_shift")
			else None,
			lambda: resolve_branch_from_pos_profile(result.get("pos_profile"), company=result.get("company"))
			if result.get("pos_profile")
			else None,
			lambda: resolve_branch_from_warehouse(result.get("warehouse"), company=result.get("company"))
			if result.get("warehouse")
			else None,
			lambda: get_coreedge_branch_context(user=user or result.get("cashier"), company=result.get("company"))
			if prefer_coreedge
			else None,
			lambda: resolve_branch_from_branch_profile(
				company=result.get("company"),
				branch=result.get("branch"),
				user=user or result.get("cashier"),
				pos_profile=result.get("pos_profile"),
				warehouse=result.get("warehouse"),
			),
			lambda: resolve_branch_from_user(user=user or result.get("cashier"), company=result.get("company")),
			lambda: _resolve_single_company_branch(result.get("company")),
		):
			resolution = resolver()
			if not resolution:
				continue
			_apply_resolution(result, resolution)
			if result.get("branch"):
				break

	result["access"] = validate_user_branch_access(
		result.get("branch"),
		user=user or result.get("cashier"),
		company=result.get("company"),
		throw=False,
	)
	return result


def apply_branch_context_to_doc(doc, overwrite=False, validate_access=True):
	if not getattr(doc, "doctype", None) or not doc.doctype.startswith("RetailEdge"):
		return {"branch": getattr(doc, "branch", None), "source": None, "messages": ["Unsupported doctype."]}
	if not has_field(doc.doctype, "branch"):
		return {"branch": None, "source": None, "messages": ["No branch field on document."]}

	current_branch = getattr(doc, "branch", None)
	context = resolve_retailedge_branch_context(
		doc=doc,
		company=getattr(doc, "company", None),
		branch=current_branch,
		pos_profile=getattr(doc, "pos_profile", None),
		cashier=getattr(doc, "cashier", None),
		pos_opening_shift=getattr(doc, "linked_pos_opening_shift", None) or getattr(doc, "pos_opening_shift", None),
		pos_closing_shift=getattr(doc, "linked_pos_closing_shift", None) or getattr(doc, "pos_closing_shift", None),
		warehouse=getattr(doc, "warehouse", None),
		user=getattr(doc, "cashier", None) or _current_user(),
	)
	if context.get("branch") and (not current_branch or (overwrite and _is_stronger_branch_source(context.get("source")))):
		doc.branch = context["branch"]
	if validate_access:
		context["access"] = validate_user_branch_access(
			getattr(doc, "branch", None),
			user=getattr(doc, "cashier", None) or _current_user(),
			company=getattr(doc, "company", None),
			throw=False,
		)
	return context


def get_branch_query_filters(doctype, user=None, company=None, branch=None, strict=False):
	user = user or _current_user()
	result = {"filters": {}, "messages": [], "branch": branch, "allowed_branches": []}
	branch_field = get_first_existing_field(doctype, BRANCH_FIELD_CANDIDATES)
	if not branch_field:
		return result
	if branch:
		result["filters"][branch_field] = branch
		result["branch"] = branch
		return result
	if user_has_global_branch_access(user=user):
		return result

	coreedge = get_coreedge_branch_context(user=user, company=company)
	if coreedge.get("branch"):
		result["filters"][branch_field] = coreedge["branch"]
		result["branch"] = coreedge["branch"]
		result["messages"].extend(coreedge.get("messages") or [])
		return result

	allowed = get_user_allowed_branches(user=user, company=company)
	allowed_branches = allowed.get("branches") or []
	result["allowed_branches"] = allowed_branches
	result["messages"].extend(allowed.get("messages") or [])
	if len(allowed_branches) == 1:
		result["filters"][branch_field] = allowed_branches[0]
		result["branch"] = allowed_branches[0]
	elif len(allowed_branches) > 1:
		result["filters"][branch_field] = ["in", allowed_branches]
	elif strict:
		result["filters"][branch_field] = "__never__"
	return result


def resolve_retailedge_operational_defaults(
	company=None,
	branch=None,
	user=None,
	pos_profile=None,
	warehouse=None,
):
	context = resolve_retailedge_branch_context(
		company=company,
		branch=branch,
		pos_profile=pos_profile,
		warehouse=warehouse,
		user=user,
	)
	branch_profile = resolve_branch_from_branch_profile(
		company=context.get("company") or company,
		branch=context.get("branch") or branch,
		user=user,
		pos_profile=context.get("pos_profile") or pos_profile,
		warehouse=warehouse,
	)
	defaults = dict(branch_profile.get("defaults") or {})
	defaults.update(
		{
			"branch": context.get("branch"),
			"company": context.get("company"),
			"pos_profile": context.get("pos_profile") or defaults.get("default_pos_profile"),
			"warehouse": warehouse or defaults.get("default_warehouse"),
			"source": branch_profile.get("source") or context.get("source"),
			"messages": (context.get("messages") or []) + (branch_profile.get("messages") or []),
		}
	)
	return defaults


def backfill_retailedge_branch_context(doctype=None, dry_run=True, limit=500):
	doctypes = [doctype] if doctype else [dt for dt in SUPPORTED_RETAILEDGE_BRANCH_DOCTYPES if has_doctype(dt)]
	items = []
	checked = resolved = updated = unresolved = 0
	for target_doctype in doctypes:
		if not has_field(target_doctype, "branch"):
			continue
		fields = ["name"]
		for candidate in (
			"company",
			"branch",
			"pos_profile",
			"cashier",
			"warehouse",
			"linked_pos_opening_shift",
			"linked_pos_closing_shift",
			"pos_opening_shift",
			"pos_closing_shift",
		):
			if has_field(target_doctype, candidate):
				fields.append(candidate)
		rows = frappe.get_all(
			target_doctype,
			filters={"branch": ["in", [None, ""]]},
			fields=fields,
			limit_page_length=limit,
			order_by="modified desc",
		)
		for row in rows:
			checked += 1
			context = resolve_retailedge_branch_context(
				doctype=target_doctype,
				name=row.get("name"),
				company=row.get("company"),
				pos_profile=row.get("pos_profile"),
				cashier=row.get("cashier"),
				pos_opening_shift=row.get("linked_pos_opening_shift") or row.get("pos_opening_shift"),
				pos_closing_shift=row.get("linked_pos_closing_shift") or row.get("pos_closing_shift"),
				warehouse=row.get("warehouse"),
				user=row.get("cashier"),
			)
			item = {
				"doctype": target_doctype,
				"name": row.get("name"),
				"branch": context.get("branch"),
				"source": context.get("source"),
				"messages": context.get("messages") or [],
			}
			items.append(item)
			if context.get("branch"):
				resolved += 1
				if not dry_run:
					frappe.db.set_value(target_doctype, row.get("name"), "branch", context["branch"], update_modified=False)
					updated += 1
			else:
				unresolved += 1
	return {
		"dry_run": dry_run,
		"checked": checked,
		"resolved": resolved,
		"updated": updated,
		"unresolved": unresolved,
		"items": items,
	}


def _coerce_any_doc(doc=None, doctype=None, name=None):
	if doc:
		return doc
	if doctype and name:
		return _coerce_doc(doctype, name)
	return None


def _coerce_doc(doctype, value):
	if not doctype or not value or not has_doctype(doctype):
		return None
	if getattr(value, "doctype", None) == doctype:
		return value
	try:
		return frappe.get_doc(doctype, value)
	except Exception:
		return None


def _as_dict(value):
	if not value:
		return {}
	if hasattr(value, "as_dict"):
		return value.as_dict()
	if isinstance(value, dict):
		return value
	return {
		key: getattr(value, key)
		for key in ("name", "profile_name", "company", "branch")
		if hasattr(value, key)
	}


def _resolve_branch_from_doc_field(doc):
	if not doc:
		return None
	branch_field = get_first_existing_field(doc.doctype, BRANCH_FIELD_CANDIDATES)
	if branch_field:
		branch = getattr(doc, branch_field, None)
		if branch:
			return {"branch": branch, "source": f"{doc.doctype}.{branch_field}", "messages": []}
	stored_branch = getattr(doc, "retailedge_branch", None)
	if stored_branch:
		return {
			"branch": stored_branch,
			"source": getattr(doc, "retailedge_branch_source", None) or f"{doc.doctype}.retailedge_branch",
			"messages": [],
		}
	return None


def _seed_context_from_doc(result, doc):
	result["company"] = getattr(doc, "company", None) or result.get("company")
	result["branch"] = getattr(doc, "branch", None) or getattr(doc, "retailedge_branch", None) or result.get("branch")
	result["pos_profile"] = getattr(doc, "pos_profile", None) or result.get("pos_profile")
	result["cashier"] = getattr(doc, "cashier", None) or getattr(doc, "user", None) or result.get("cashier")
	result["pos_opening_shift"] = (
		getattr(doc, "linked_pos_opening_shift", None)
		or getattr(doc, "pos_opening_shift", None)
		or result.get("pos_opening_shift")
	)
	result["pos_closing_shift"] = (
		getattr(doc, "linked_pos_closing_shift", None)
		or getattr(doc, "pos_closing_shift", None)
		or result.get("pos_closing_shift")
	)
	result["warehouse"] = getattr(doc, "warehouse", None) or result.get("warehouse")
	return result


def _apply_resolution(result, resolution):
	for key in ("branch", "company", "pos_profile", "cashier", "pos_opening_shift", "pos_closing_shift", "warehouse"):
		if resolution.get(key) and not result.get(key):
			result[key] = resolution.get(key)
			if resolution.get("source"):
				result["source_map"][key] = resolution.get("source")
	if resolution.get("defaults"):
		result.setdefault("defaults", {}).update(resolution.get("defaults") or {})
	if resolution.get("source") and resolution.get("branch"):
		result["source"] = resolution.get("source")
		result["source_map"]["branch"] = resolution.get("source")
	result["messages"].extend(resolution.get("messages") or [])


def _resolve_single_company_branch(company):
	if not company or not has_doctype("Branch") or not has_field("Branch", "company"):
		return None
	try:
		branches = frappe.get_all("Branch", filters={"company": company}, pluck="name", limit_page_length=0)
	except Exception:
		return None
	if len(branches or []) == 1:
		return {"branch": branches[0], "company": company, "source": "Single Company Branch", "messages": []}
	if len(branches or []) > 1:
		return {"branch": None, "company": company, "source": None, "messages": ["Multiple branches exist for company."]}
	return None


def _dedupe(values):
	seen = set()
	result = []
	for value in values or []:
		if value and value not in seen:
			seen.add(value)
			result.append(value)
	return result


def _current_user():
	try:
		return frappe.session.user
	except Exception:
		return "Administrator"


def _is_stronger_branch_source(source):
	return source in {
		"POS Closing Shift.branch",
		"POS Closing Shift.set_branch",
		"POS Closing Shift.service_branch",
		"POS Closing Shift.retail_branch",
		"POS Closing Shift.default_branch",
		"POS Opening Shift.branch",
		"POS Opening Shift.set_branch",
		"POS Opening Shift.service_branch",
		"POS Opening Shift.retail_branch",
		"POS Opening Shift.default_branch",
	}
