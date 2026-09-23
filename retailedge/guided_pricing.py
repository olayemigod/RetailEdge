from __future__ import annotations

from typing import Any, Literal

import frappe
from frappe import _
from frappe.core.doctype.user_permission.user_permission import get_user_permissions
from frappe.utils import flt, getdate, nowdate
from frappe.utils.caching import request_cache

from erpnext.stock.get_item_details import get_item_details, get_pos_profile

from retailedge.branch_assignment import get_branch_assignment_price_lists
from retailedge.branch_profile import get_branch_profile, get_exact_branch_profile

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
	"""Resolve governed Price List context for EdgeSuite transactions.

	Precedence is explicit:
	1. exact Branch Setup default
	2. a valid user-selected Price List from the current assignment scope
	3. user's existing default Price List when it remains allowed
	4. single/default assigned Price List
	5. POS / party / ERPNext / standard fallbacks

	A Branch default is mandatory for the Branch when configured and cannot be
	overridden by browser input. Multiple explicitly assigned lists require the
	user to choose unless an existing valid user default resolves the choice.
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

	branch_default = _branch_default_price_list(
		mode=mode,
		company=company,
		branch=branch,
		user=user,
	)
	assignment_scope = _assignment_price_list_scope(
		mode=mode,
		company=company,
		branch=branch,
		user=user,
	)
	selectable = assignment_scope["names"]
	has_assignment_boundary = bool(assignment_scope["restricted"])

	if branch_default:
		context = _price_context(branch_default, mode=mode, source="branch_default")
		context.update(
			{
				"branch_default": branch_default,
				"locked": True,
				"can_select": False,
				"selection_required": False,
				"allowed_price_lists": selectable,
			}
		)
		return context

	if selected_price_list:
		if has_assignment_boundary and selected_price_list not in selectable:
			frappe.throw(
				_("Price List {0} is not assigned to you for Branch {1}.").format(
					frappe.bold(selected_price_list),
					frappe.bold(branch or _("current context")),
				),
				frappe.PermissionError,
			)
		if not _valid_price_list(selected_price_list, mode=mode, user=user):
			frappe.throw(
				_("Price List {0} is not available for this {1} transaction.").format(
					frappe.bold(selected_price_list),
					mode,
				),
				frappe.PermissionError,
			)
		context = _price_context(selected_price_list, mode=mode, source="user_selected")
		context.update(
			{
				"branch_default": "",
				"locked": False,
				"can_select": bool(selectable),
				"selection_required": False,
				"allowed_price_lists": selectable,
			}
		)
		return context

	for key in USER_DEFAULT_KEYS[mode]:
		candidate = str(frappe.defaults.get_user_default(key) or "").strip()
		if (
			candidate
			and (not has_assignment_boundary or candidate in selectable)
			and _valid_price_list(candidate, mode=mode, user=user)
		):
			context = _price_context(candidate, mode=mode, source="user_default")
			context.update(
				{
					"branch_default": "",
					"locked": False,
					"can_select": bool(selectable),
					"selection_required": False,
					"allowed_price_lists": selectable,
				}
			)
			return context

	permission_candidate = _default_user_permission_price_list(user=user, mode=mode)
	if (
		permission_candidate
		and (not has_assignment_boundary or permission_candidate in selectable)
	):
		context = _price_context(permission_candidate, mode=mode, source="user_permission")
		context.update(
			{
				"branch_default": "",
				"locked": False,
				"can_select": bool(selectable),
				"selection_required": False,
				"allowed_price_lists": selectable,
			}
		)
		return context

	if has_assignment_boundary:
		if len(selectable) == 1:
			context = _price_context(selectable[0], mode=mode, source="branch_assignment")
			context.update(
				{
					"branch_default": "",
					"locked": False,
					"can_select": False,
					"selection_required": False,
					"allowed_price_lists": selectable,
				}
			)
			return context
		if len(selectable) > 1:
			return {
				"price_list": "",
				"currency": "",
				"source": "branch_assignment",
				"mode": mode,
				"pos_profile": "",
				"allow_rate_change": True,
				"branch_default": "",
				"locked": False,
				"can_select": True,
				"selection_required": True,
				"allowed_price_lists": selectable,
			}

	if mode == "selling":
		pos = _resolve_user_pos_profile(company=company, branch=branch, user=user)
		pos_price_list = str(pos.get("selling_price_list") or "").strip() if pos else ""
		if pos and pos_price_list and _valid_price_list(pos_price_list, mode="selling", user=user):
			context = _price_context(pos_price_list, mode="selling", source="pos_profile")
			context.update(
				{
					"pos_profile": pos.get("name") or "",
					"allow_rate_change": bool(pos.get("allow_rate_change")),
					"branch_default": "",
					"locked": not bool(pos.get("allow_rate_change")),
					"can_select": False,
					"selection_required": False,
					"allowed_price_lists": [],
				}
			)
			return context

	party_price_list = _party_price_list(mode=mode, party=party)
	if party_price_list and _valid_price_list(party_price_list, mode=mode, user=user):
		context = _price_context(party_price_list, mode=mode, source="party_default")
		context.update(_open_pricing_metadata())
		return context

	settings_doctype, settings_field = SETTINGS_PRICE_LIST[mode]
	candidate = str(frappe.db.get_single_value(settings_doctype, settings_field) or "").strip()
	if candidate and _valid_price_list(candidate, mode=mode, user=user):
		context = _price_context(candidate, mode=mode, source="erpnext_default")
		context.update(_open_pricing_metadata())
		return context

	candidate = STANDARD_PRICE_LIST[mode]
	if _valid_price_list(candidate, mode=mode, user=user):
		context = _price_context(candidate, mode=mode, source="standard_price_list")
		context.update(_open_pricing_metadata())
		return context

	return {
		"price_list": "",
		"currency": "",
		"source": "item_fallback",
		"mode": mode,
		"pos_profile": "",
		"allow_rate_change": True,
		**_open_pricing_metadata(),
	}


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
	if candidate and _valid_price_list(candidate, mode=mode, user=user):
		return candidate
	return ""


def _assignment_price_list_scope(
	*,
	mode: PriceMode,
	company: str,
	branch: str,
	user: str,
) -> dict[str, Any]:
	scope = get_branch_assignment_price_lists(
		user=user,
		company=company,
		branch=branch or None,
	)
	raw_names = [str(name or "").strip() for name in scope.get("names") or [] if str(name or "").strip()]
	valid = [
		name
		for name in dict.fromkeys(raw_names)
		if _valid_price_list(name, mode=mode, user=user)
	]
	return {
		"names": valid,
		"restricted": bool(raw_names),
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
	return [
		{
			"value": name,
			"label": name,
			"description": _("Branch default") if name == context.get("branch_default") else _("Assigned Price List"),
		}
		for name in names[: max(1, min(int(limit or 20), 50))]
	]


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


def _valid_price_list(name: str | None, *, mode: PriceMode, user: str) -> bool:
	name = str(name or "").strip()
	if not name:
		return False
	row = frappe.db.get_value("Price List", name, ["enabled", mode], as_dict=True)
	if not row or not row.get("enabled") or not row.get(mode):
		return False
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
