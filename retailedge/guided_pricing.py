from __future__ import annotations

from typing import Any, Literal

import frappe
from frappe import _
from frappe.core.doctype.user_permission.user_permission import get_user_permissions
from frappe.utils import cint, flt, getdate, nowdate
from frappe.utils.caching import request_cache

from erpnext.stock.get_item_details import get_item_details, get_pos_profile

from retailedge.branch_assignment import get_branch_assignment_price_lists
from retailedge.branch_context import validate_user_branch_access
from retailedge.branch_profile import get_branch_profile, get_exact_branch_profile
from retailedge.utils.settings import get_retailedge_settings

PriceMode = Literal["selling", "buying"]


USER_DEFAULT_KEYS: dict[PriceMode, tuple[str, ...]] = {
	"selling": ("Selling Price List", "selling_price_list"),
	"buying": ("Buying Price List", "buying_price_list"),
}
SETTINGS_PRICE_LIST: dict[PriceMode, tuple[str, str]] = {
	"selling": ("Selling Settings", "selling_price_list"),
	"buying": ("Buying Settings", "buying_price_list"),
}
STANDARD_PRICE_LIST: dict[PriceMode, str] = {
	"selling": "Standard Selling",
	"buying": "Standard Buying",
}
PRICE_SOURCE_KEYS: dict[PriceMode, tuple[str, ...]] = {
	"selling": (
		"party_default",
		"pos_profile",
		"branch_default",
		"user_default",
		"user_permission",
		"erpnext_default",
		"standard_price_list",
	),
	"buying": (
		"party_default",
		"branch_default",
		"user_default",
		"user_permission",
		"erpnext_default",
		"standard_price_list",
	),
}
DEFAULT_PRICE_PRECEDENCE: dict[PriceMode, tuple[str, ...]] = {
	"selling": PRICE_SOURCE_KEYS["selling"],
	"buying": PRICE_SOURCE_KEYS["buying"],
}


@request_cache
def resolve_price_list_context(
	*,
	mode: PriceMode,
	company: str,
	branch: str = "",
	party: str = "",
	selected_price_list: str = "",
	user: str | None = None,
) -> dict[str, Any]:
	"""Resolve one effective Price List from the merchant's governance policy.

	Branch Assignment Price Lists are selectable alternatives/fallbacks, not a
	hard-coded source of precedence. The configured policy decides which default
	source wins and whether the user may switch from it to an assigned alternative.
	"""
	user = user or frappe.session.user
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	party = str(party or "").strip()
	selected_price_list = str(selected_price_list or "").strip()
	if mode not in ("selling", "buying"):
		frappe.throw(_("Unsupported guided pricing mode."))
	if not company:
		frappe.throw(_("Company is required to resolve pricing."))

	policy = _price_list_governance_policy(mode=mode)
	assignment_scope = _assignment_price_list_scope(
		mode=mode,
		company=company,
		branch=branch,
		user=user,
	)
	assigned_price_lists = list(assignment_scope["names"])
	default_candidate = _resolve_default_price_list_candidate(
		mode=mode,
		company=company,
		branch=branch,
		party=party,
		user=user,
		precedence=policy["precedence"],
	)
	default_name = str((default_candidate or {}).get("price_list") or "").strip()
	default_source = str((default_candidate or {}).get("source") or "").strip()
	switch_allowed = bool(
		policy["enabled"]
		and policy["enable_assigned_switching"]
		and assigned_price_lists
		and _source_allows_switch(default_source, policy=policy)
	)
	selectable = (
		list(dict.fromkeys([*([default_name] if default_name else []), *assigned_price_lists]))
		if switch_allowed
		else ([default_name] if default_name else [])
	)

	if selected_price_list:
		if default_name and selected_price_list == default_name:
			selected_price_list = ""
		elif not switch_allowed or selected_price_list not in assigned_price_lists:
			frappe.throw(
				_("Price List {0} is not selectable under the current Price List Governance policy.").format(
					frappe.bold(selected_price_list)
				),
				frappe.PermissionError,
			)
		else:
			context = _price_context(selected_price_list, mode=mode, source="user_selected")
			context.update(
				{
					"branch_default": _branch_default_price_list(
						mode=mode, company=company, branch=branch, user=user
					),
					"resolved_default": default_name,
					"resolved_default_source": default_source,
					"locked": False,
					"can_select": True,
					"selection_required": False,
					"allowed_price_lists": selectable,
					"governance": _public_governance_context(policy),
				}
			)
			return context

	if default_candidate:
		context = _price_context(default_name, mode=mode, source=default_source)
		context.update(
			{
				"pos_profile": default_candidate.get("pos_profile") or "",
				"allow_rate_change": bool(default_candidate.get("allow_rate_change", True)),
				"branch_default": (
					default_name if default_source == "branch_default" else _branch_default_price_list(
						mode=mode, company=company, branch=branch, user=user
					)
				),
				"resolved_default": default_name,
				"resolved_default_source": default_source,
				"locked": not switch_allowed,
				"can_select": switch_allowed,
				"selection_required": False,
				"allowed_price_lists": selectable,
				"governance": _public_governance_context(policy),
			}
		)
		return context

	if policy["enabled"] and policy["enable_assigned_switching"] and assigned_price_lists:
		if len(assigned_price_lists) == 1:
			context = _price_context(assigned_price_lists[0], mode=mode, source="branch_assignment")
			context.update(
				{
					"branch_default": "",
					"resolved_default": "",
					"resolved_default_source": "",
					"locked": False,
					"can_select": False,
					"selection_required": False,
					"allowed_price_lists": assigned_price_lists,
					"governance": _public_governance_context(policy),
				}
			)
			return context
		return {
			"price_list": "",
			"currency": "",
			"source": "branch_assignment",
			"mode": mode,
			"pos_profile": "",
			"allow_rate_change": True,
			"branch_default": "",
			"resolved_default": "",
			"resolved_default_source": "",
			"locked": False,
			"can_select": True,
			"selection_required": True,
			"allowed_price_lists": assigned_price_lists,
			"governance": _public_governance_context(policy),
		}

	return {
		"price_list": "",
		"currency": "",
		"source": "item_fallback",
		"mode": mode,
		"pos_profile": "",
		"allow_rate_change": True,
		"resolved_default": "",
		"resolved_default_source": "",
		"governance": _public_governance_context(policy),
		**_open_pricing_metadata(),
	}


def _price_list_governance_policy(*, mode: PriceMode) -> dict[str, Any]:
	settings = get_retailedge_settings()
	enabled = _setting_bool(settings, "enable_price_list_governance", True)
	fieldname = "selling_price_list_precedence" if mode == "selling" else "buying_price_list_precedence"
	precedence = (
		_parse_precedence(
			getattr(settings, fieldname, None),
			allowed=PRICE_SOURCE_KEYS[mode],
			fallback=DEFAULT_PRICE_PRECEDENCE[mode],
		)
		if enabled
		else list(DEFAULT_PRICE_PRECEDENCE[mode])
	)
	return {
		"enabled": enabled,
		"precedence": precedence,
		"enable_assigned_switching": (
			_setting_bool(settings, "enable_assigned_price_list_switching", True)
			if enabled
			else False
		),
		"allow_switch_from_party_default": _setting_bool(
			settings, "allow_price_list_switch_from_party_default", False
		),
		"allow_switch_from_pos_profile": _setting_bool(
			settings, "allow_price_list_switch_from_pos_default", False
		),
		"allow_switch_from_branch_default": _setting_bool(
			settings, "allow_price_list_switch_from_branch_default", True
		),
		"allow_switch_from_user_default": _setting_bool(
			settings, "allow_price_list_switch_from_user_default", True
		),
		"allow_switch_from_system_default": _setting_bool(
			settings, "allow_price_list_switch_from_system_default", True
		),
	}


def _setting_bool(settings, fieldname: str, default: bool) -> bool:
	value = getattr(settings, fieldname, None)
	if value in (None, ""):
		return bool(default)
	return bool(cint(value))


def _parse_precedence(
	value,
	*,
	allowed: tuple[str, ...],
	fallback: tuple[str, ...],
) -> list[str]:
	raw = str(value or "").replace(">", "\n").replace(",", "\n")
	keys: list[str] = []
	for line in raw.splitlines():
		key = line.strip()
		if key and key in allowed and key not in keys:
			keys.append(key)
	return keys or list(fallback)


def _public_governance_context(policy: dict[str, Any]) -> dict[str, Any]:
	return {
		"enabled": bool(policy.get("enabled")),
		"precedence": list(policy.get("precedence") or []),
		"enable_assigned_switching": bool(policy.get("enable_assigned_switching")),
	}


def _source_allows_switch(source: str, *, policy: dict[str, Any]) -> bool:
	if not source:
		return True
	if source == "party_default":
		return bool(policy.get("allow_switch_from_party_default"))
	if source == "pos_profile":
		return bool(policy.get("allow_switch_from_pos_profile"))
	if source == "branch_default":
		return bool(policy.get("allow_switch_from_branch_default"))
	if source in {"user_default", "user_permission"}:
		return bool(policy.get("allow_switch_from_user_default"))
	if source in {"erpnext_default", "standard_price_list"}:
		return bool(policy.get("allow_switch_from_system_default"))
	return True


def _resolve_default_price_list_candidate(
	*,
	mode: PriceMode,
	company: str,
	branch: str,
	party: str,
	user: str,
	precedence: list[str],
) -> dict[str, Any] | None:
	for source in precedence:
		row = _price_source_candidate(
			source=source,
			mode=mode,
			company=company,
			branch=branch,
			party=party,
			user=user,
		)
		if row:
			return row
	return None


def _price_source_candidate(
	*,
	source: str,
	mode: PriceMode,
	company: str,
	branch: str,
	party: str,
	user: str,
) -> dict[str, Any] | None:
	def candidate(
		name: str,
		*,
		pos_profile: str = "",
		allow_rate_change: bool = True,
	) -> dict[str, Any] | None:
		name = str(name or "").strip()
		if not name or not _valid_price_list(name, mode=mode, user=user, require_read=False):
			return None
		return {
			"price_list": name,
			"source": source,
			"pos_profile": pos_profile,
			"allow_rate_change": allow_rate_change,
		}

	if source == "party_default":
		return candidate(_party_price_list(mode=mode, party=party))
	if source == "pos_profile":
		if mode != "selling":
			return None
		pos = _resolve_user_pos_profile(company=company, branch=branch, user=user)
		if not pos:
			return None
		return candidate(
			str(pos.get("selling_price_list") or "").strip(),
			pos_profile=str(pos.get("name") or "").strip(),
			allow_rate_change=bool(pos.get("allow_rate_change")),
		)
	if source == "branch_default":
		return candidate(_branch_default_price_list(mode=mode, company=company, branch=branch, user=user))
	if source == "user_default":
		for key in USER_DEFAULT_KEYS[mode]:
			row = candidate(str(frappe.defaults.get_user_default(key) or "").strip())
			if row:
				return row
		return None
	if source == "user_permission":
		return candidate(_default_user_permission_price_list(user=user, mode=mode))
	if source == "erpnext_default":
		settings_doctype, settings_field = SETTINGS_PRICE_LIST[mode]
		return candidate(str(frappe.db.get_single_value(settings_doctype, settings_field) or "").strip())
	if source == "standard_price_list":
		return candidate(STANDARD_PRICE_LIST[mode])
	return None


def _open_pricing_metadata() -> dict[str, Any]:
	return {
		"branch_default": "",
		"locked": False,
		"can_select": False,
		"selection_required": False,
		"allowed_price_lists": [],
	}


def _branch_default_price_list(
	*,
	mode: PriceMode,
	company: str,
	branch: str,
	user: str,
) -> str:
	if not branch:
		return ""
	profile = get_exact_branch_profile(company=company, branch=branch, active_only=True)
	if not profile:
		return ""
	fieldname = "default_selling_price_list" if mode == "selling" else "default_buying_price_list"
	candidate = str(getattr(profile, fieldname, None) or "").strip()
	if candidate and _valid_price_list(candidate, mode=mode, user=user, require_read=False):
		return candidate
	return ""


def _assignment_price_list_scope(
	*,
	mode: PriceMode,
	company: str,
	branch: str,
	user: str,
) -> dict[str, Any]:
	if not branch:
		return {"names": [], "restricted": False, "assignment_names": []}
	scope = get_branch_assignment_price_lists(
		user=user,
		company=company,
		branch=branch or None,
	)
	raw_names = [str(name or "").strip() for name in scope.get("names") or [] if str(name or "").strip()]
	valid = [
		name
		for name in dict.fromkeys(raw_names)
		if _valid_price_list(name, mode=mode, user=user, require_read=False)
	]
	return {
		"names": valid,
		"restricted": bool(valid),
		"assignment_names": scope.get("assignment_names") or [],
	}


@frappe.whitelist()
def get_allowed_price_list_context(
	mode: PriceMode,
	company: str,
	branch: str = "",
	party: str = "",
	selected_price_list: str = "",
) -> dict[str, Any]:
	_assert_whitelisted_pricing_context_access(
		mode=mode,
		company=company,
		branch=branch,
		party=party,
		user=frappe.session.user,
	)
	return resolve_price_list_context(
		mode=mode,
		company=company,
		branch=branch,
		party=party,
		selected_price_list=selected_price_list,
		user=frappe.session.user,
	)


@frappe.whitelist()
def search_allowed_price_lists(
	mode: PriceMode,
	company: str,
	branch: str = "",
	txt: str = "",
	party: str = "",
	limit: int = 20,
) -> list[dict[str, Any]]:
	_assert_whitelisted_pricing_context_access(
		mode=mode,
		company=company,
		branch=branch,
		party=party,
		user=frappe.session.user,
	)
	context = resolve_price_list_context(
		mode=mode,
		company=company,
		branch=branch,
		party=party,
		user=frappe.session.user,
	)
	names = list(context.get("allowed_price_lists") or [])
	if context.get("locked") and context.get("price_list"):
		names = [context["price_list"]]
	txt = str(txt or "").strip().lower()
	if txt:
		names = [name for name in names if txt in name.lower()]
	resolved_default = str(context.get("resolved_default") or context.get("price_list") or "").strip()
	resolved_source = str(context.get("resolved_default_source") or context.get("source") or "").strip()
	return [
		{
			"value": name,
			"label": name,
			"description": (
				_("Current default ({0})").format(_price_source_label(resolved_source))
				if name == resolved_default
				else _("Branch-assigned alternative")
			),
		}
		for name in names[: max(1, min(int(limit or 20), 50))]
	]


def _price_source_label(source: str) -> str:
	return {
		"party_default": _("Customer / Supplier"),
		"pos_profile": _("POS Profile"),
		"branch_default": _("Branch"),
		"user_default": _("User"),
		"user_permission": _("User Permission"),
		"erpnext_default": _("ERPNext Settings"),
		"standard_price_list": _("Standard"),
		"branch_assignment": _("Branch Assignment"),
		"user_selected": _("Selected"),
	}.get(str(source or ""), _("Default"))


def _assert_whitelisted_pricing_context_access(
	*,
	mode: PriceMode,
	company: str,
	branch: str,
	party: str,
	user: str,
) -> None:
	if mode not in ("selling", "buying"):
		frappe.throw(_("Unsupported guided pricing mode."))
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	party = str(party or "").strip()
	if not company:
		frappe.throw(_("Company is required to resolve pricing."))
	_assert_read_permission("Company", company, user=user)
	if branch:
		_assert_read_permission("Branch", branch, user=user)
		validate_user_branch_access(branch, user=user, company=company, throw=True)
	if party:
		_assert_read_permission("Customer" if mode == "selling" else "Supplier", party, user=user)


def resolve_sales_item_pricing(
	*,
	item_code: str,
	company: str,
	customer: str,
	branch: str = "",
	warehouse: str = "",
	posting_date: str | None = None,
	qty: float = 1,
	selected_price_list: str = "",
	user: str | None = None,
) -> dict[str, Any]:
	user = user or frappe.session.user
	_assert_read_permission("Item", item_code, user=user)
	_assert_read_permission("Customer", customer, user=user)
	context = resolve_price_list_context(
		mode="selling",
		company=company,
		branch=branch,
		party=customer,
		selected_price_list=selected_price_list,
		user=user,
	)
	if context.get("selection_required"):
		frappe.throw(_("Choose a Selling Price List before pricing items."))
	details = _erpnext_item_details(
		mode="selling",
		item_code=item_code,
		company=company,
		party=customer,
		price_list=context.get("price_list") or "",
		warehouse=warehouse,
		posting_date=posting_date,
		qty=qty,
	)
	rate = _first_rate(details.get("rate"), details.get("price_list_rate"))
	rate_source = "erpnext_pricing"
	if rate is None:
		standard_rate = frappe.get_cached_value("Item", item_code, "standard_rate")
		if standard_rate is not None:
			rate = flt(standard_rate)
			rate_source = "item_standard_rate"

	return {
		**context,
		"item_code": item_code,
		"rate": rate,
		"price_list_rate": _rate_or_none(details.get("price_list_rate")),
		"rate_source": rate_source if rate is not None else "unresolved",
	}


def resolve_purchase_item_pricing(
	*,
	item_code: str,
	company: str,
	supplier: str,
	branch: str = "",
	warehouse: str = "",
	posting_date: str | None = None,
	qty: float = 1,
	selected_price_list: str = "",
	user: str | None = None,
) -> dict[str, Any]:
	user = user or frappe.session.user
	_assert_read_permission("Item", item_code, user=user)
	_assert_read_permission("Supplier", supplier, user=user)
	context = resolve_price_list_context(
		mode="buying",
		company=company,
		branch=branch,
		party=supplier,
		selected_price_list=selected_price_list,
		user=user,
	)
	if context.get("selection_required"):
		frappe.throw(_("Choose a Buying Price List before pricing items."))
	details = _erpnext_item_details(
		mode="buying",
		item_code=item_code,
		company=company,
		party=supplier,
		price_list=context.get("price_list") or "",
		warehouse=warehouse,
		posting_date=posting_date,
		qty=qty,
	)
	rate = _first_rate(
		details.get("rate"),
		details.get("price_list_rate"),
		details.get("last_purchase_rate"),
	)
	rate_source = "erpnext_pricing"
	if rate is None:
		last_purchase_rate = frappe.get_cached_value("Item", item_code, "last_purchase_rate")
		if last_purchase_rate not in (None, ""):
			rate = flt(last_purchase_rate)
			rate_source = "item_last_purchase_rate"

	return {
		**context,
		"item_code": item_code,
		"rate": rate,
		"price_list_rate": _rate_or_none(details.get("price_list_rate")),
		"rate_source": rate_source if rate is not None else "unresolved",
	}


def _erpnext_item_details(
	*,
	mode: PriceMode,
	item_code: str,
	company: str,
	party: str,
	price_list: str,
	warehouse: str,
	posting_date: str | None,
	qty: float,
) -> frappe._dict:
	company_currency = frappe.get_cached_value("Company", company, "default_currency") or ""
	ctx = frappe._dict(
		{
			"doctype": "Sales Invoice" if mode == "selling" else "Purchase Invoice",
			"parenttype": "Sales Invoice" if mode == "selling" else "Purchase Invoice",
			"item_code": item_code,
			"company": company,
			"customer": party if mode == "selling" else None,
			"supplier": party if mode == "buying" else None,
			"selling_price_list": price_list if mode == "selling" else None,
			"buying_price_list": price_list if mode == "buying" else None,
			"price_list": price_list or None,
			"currency": company_currency,
			"conversion_rate": 1,
			"plc_conversion_rate": 1,
			"transaction_date": getdate(posting_date or nowdate()),
			"posting_date": getdate(posting_date or nowdate()),
			"warehouse": warehouse or None,
			"set_warehouse": warehouse or None,
			"qty": flt(qty) or 1,
			"is_pos": 0,
		}
	)
	return frappe._dict(get_item_details(ctx) or {})


def _resolve_user_pos_profile(*, company: str, branch: str, user: str) -> frappe._dict | None:
	if branch:
		profile = get_branch_profile(company=company, branch=branch, user=user, active_only=True)
		configured = str(getattr(profile, "default_pos_profile", None) or "").strip() if profile else ""
		if configured:
			pos = _permitted_pos_profile(configured, company=company, user=user)
			if pos:
				return pos

	if not frappe.has_permission("POS Profile", "read", user=user):
		return None
	try:
		standard = get_pos_profile(company, user=user)
	except Exception:
		standard = None
	if not standard:
		return None
	name = standard.get("name") if isinstance(standard, dict) else getattr(standard, "name", None)
	return _permitted_pos_profile(str(name or ""), company=company, user=user)


def _permitted_pos_profile(name: str, *, company: str, user: str) -> frappe._dict | None:
	if not name:
		return None
	pos = frappe.db.get_value(
		"POS Profile",
		name,
		["name", "company", "disabled", "selling_price_list", "allow_rate_change"],
		as_dict=True,
	)
	if not pos or pos.get("disabled") or pos.get("company") != company:
		return None

	user_rows = frappe.db.count("POS Profile User", {"parent": name})
	if user_rows and not frappe.db.exists("POS Profile User", {"parent": name, "user": user}):
		return None
	return frappe._dict(pos)


def _default_user_permission_price_list(*, user: str, mode: PriceMode) -> str:
	permissions = get_user_permissions(user).get("Price List", []) or []
	ordered = sorted(permissions, key=lambda row: int(row.get("is_default") or 0), reverse=True)
	valid = [
		str(row.get("doc") or "").strip()
		for row in ordered
		if _valid_price_list(str(row.get("doc") or "").strip(), mode=mode, user=user)
	]
	if not valid:
		return ""
	default_valid = next(
		(
			str(row.get("doc") or "").strip()
			for row in ordered
			if int(row.get("is_default") or 0)
			and _valid_price_list(str(row.get("doc") or "").strip(), mode=mode, user=user)
		),
		"",
	)
	if default_valid:
		return default_valid
	return valid[0] if len(valid) == 1 else ""


def _party_price_list(*, mode: PriceMode, party: str) -> str:
	if not party:
		return ""
	if mode == "selling":
		customer = frappe.db.get_value(
			"Customer", party, ["default_price_list", "customer_group"], as_dict=True
		) or {}
		return str(
			customer.get("default_price_list")
			or frappe.db.get_value("Customer Group", customer.get("customer_group"), "default_price_list")
			or ""
		).strip()
	return str(frappe.db.get_value("Supplier", party, "default_price_list") or "").strip()


def _valid_price_list(
	name: str | None,
	*,
	mode: PriceMode,
	user: str,
	require_read: bool = True,
) -> bool:
	name = str(name or "").strip()
	if not name:
		return False
	row = frappe.db.get_value("Price List", name, ["enabled", mode], as_dict=True)
	if not row or not row.get("enabled") or not row.get(mode):
		return False
	if not require_read:
		return True
	return bool(frappe.has_permission("Price List", "read", doc=name, user=user))


def _price_context(name: str, *, mode: PriceMode, source: str) -> dict[str, Any]:
	currency = frappe.db.get_value("Price List", name, "currency") or ""
	return {
		"price_list": name,
		"currency": currency,
		"source": source,
		"mode": mode,
		"pos_profile": "",
		"allow_rate_change": True,
	}


def _assert_read_permission(doctype: str, name: str, *, user: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name, user=user):
		frappe.throw(
			_("You do not have permission to use {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)


def _first_rate(*values: Any) -> float | None:
	for value in values:
		if value not in (None, ""):
			return flt(value)
	return None


def _rate_or_none(value: Any) -> float | None:
	return None if value in (None, "") else flt(value)
