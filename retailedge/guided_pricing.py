from __future__ import annotations

from typing import Any, Literal

import frappe
from frappe import _
from frappe.core.doctype.user_permission.user_permission import get_user_permissions
from frappe.utils import flt, getdate, nowdate

from erpnext.stock.get_item_details import get_item_details, get_pos_profile

from retailedge.branch_profile import get_branch_profile

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


def resolve_price_list_context(
	*,
	mode: PriceMode,
	company: str,
	branch: str = "",
	party: str = "",
	user: str | None = None,
) -> dict[str, Any]:
	"""Resolve the effective guided-entry Price List for the current user.

	The client never supplies or authorises its own Price List. Selection is made
	from current-user defaults/permissions and trusted ERPNext/RetailEdge setup.
	"""
	user = user or frappe.session.user
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	party = str(party or "").strip()
	if mode not in ("selling", "buying"):
		frappe.throw(_("Unsupported guided pricing mode."))
	if not company:
		frappe.throw(_("Company is required to resolve pricing."))

	for key in USER_DEFAULT_KEYS[mode]:
		candidate = str(frappe.defaults.get_user_default(key) or "").strip()
		if _valid_price_list(candidate, mode=mode, user=user):
			return _price_context(candidate, mode=mode, source="user_default")

	permission_candidate = _default_user_permission_price_list(user=user, mode=mode)
	if permission_candidate:
		return _price_context(permission_candidate, mode=mode, source="user_permission")

	if mode == "selling":
		pos = _resolve_user_pos_profile(company=company, branch=branch, user=user)
		if pos and _valid_price_list(pos.get("selling_price_list"), mode="selling", user=user):
			context = _price_context(
				pos.get("selling_price_list"), mode="selling", source="pos_profile"
			)
			context.update(
				{
					"pos_profile": pos.get("name") or "",
					"allow_rate_change": bool(pos.get("allow_rate_change")),
				}
			)
			return context

		party_price_list = _party_price_list(mode=mode, party=party)
		if _valid_price_list(party_price_list, mode=mode, user=user):
			return _price_context(party_price_list, mode=mode, source="party_default")

	settings_doctype, settings_field = SETTINGS_PRICE_LIST[mode]
	candidate = str(frappe.db.get_single_value(settings_doctype, settings_field) or "").strip()
	if _valid_price_list(candidate, mode=mode, user=user):
		return _price_context(candidate, mode=mode, source="erpnext_default")

	candidate = STANDARD_PRICE_LIST[mode]
	if _valid_price_list(candidate, mode=mode, user=user):
		return _price_context(candidate, mode=mode, source="standard_price_list")

	return {
		"price_list": "",
		"currency": "",
		"source": "item_fallback",
		"mode": mode,
		"pos_profile": "",
		"allow_rate_change": True,
	}


def resolve_sales_item_pricing(
	*,
	item_code: str,
	company: str,
	customer: str,
	branch: str = "",
	warehouse: str = "",
	posting_date: str | None = None,
	qty: float = 1,
	user: str | None = None,
) -> dict[str, Any]:
	user = user or frappe.session.user
	_assert_read_permission("Item", item_code, user=user)
	_assert_read_permission("Customer", customer, user=user)
	context = resolve_price_list_context(
		mode="selling", company=company, branch=branch, party=customer, user=user
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
	user: str | None = None,
) -> dict[str, Any]:
	user = user or frappe.session.user
	_assert_read_permission("Item", item_code, user=user)
	_assert_read_permission("Supplier", supplier, user=user)
	context = resolve_price_list_context(
		mode="buying", company=company, branch=branch, party=supplier, user=user
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
	if ordered and int(ordered[0].get("is_default") or 0) and valid[0]:
		return valid[0]
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
