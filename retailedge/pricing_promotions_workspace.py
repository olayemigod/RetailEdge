from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.core.doctype.user_permission.user_permission import get_user_permissions
from frappe.utils import cint, getdate
from frappe.utils.user import get_user_fullname

from erpnext.stock.get_item_details import get_pos_profile

from retailedge.branch_profile import get_exact_branch_profile, get_user_pos_profiles
from retailedge.operating_context import get_operating_context

MAX_PAGE_LENGTH = 100
DEFAULT_PAGE_LENGTH = 25

AREAS: dict[str, dict[str, Any]] = {
	"price-lists": {
		"label": "Price Lists",
		"doctype": "Price List",
		"description": "Create and maintain the price lists used for selling and buying.",
		"columns": (
			("name", "Price List"),
			("enabled", "Enabled"),
			("selling", "Selling"),
			("buying", "Buying"),
			("currency", "Currency"),
			("modified", "Modified"),
		),
		"search_fields": ("name",),
		"filters": (
			{"fieldname": "enabled", "label": "Enabled", "type": "boolean"},
			{"fieldname": "selling", "label": "Selling", "type": "boolean"},
			{"fieldname": "buying", "label": "Buying", "type": "boolean"},
			{"fieldname": "currency", "label": "Currency", "type": "text"},
		),
	},
	"item-prices": {
		"label": "Item Prices",
		"doctype": "Item Price",
		"description": "Maintain item rates, price-list assignments, currencies, UOMs and validity periods.",
		"columns": (
			("name", "ID"),
			("item_code", "Item"),
			("price_list", "Price List"),
			("price_list_rate", "Rate"),
			("currency", "Currency"),
			("uom", "UOM"),
			("valid_from", "Valid From"),
			("valid_upto", "Valid Until"),
		),
		"search_fields": ("name", "item_code", "price_list"),
		"filters": (
			{"fieldname": "item_code", "label": "Item", "type": "text"},
			{"fieldname": "price_list", "label": "Price List", "type": "price_list"},
			{"fieldname": "currency", "label": "Currency", "type": "text"},
			{"fieldname": "uom", "label": "UOM", "type": "text"},
			{"fieldname": "valid_from", "label": "Valid From", "type": "date_from"},
			{"fieldname": "valid_upto", "label": "Valid Until", "type": "date_to"},
		),
	},
	"pricing-rules": {
		"label": "Pricing Rules",
		"doctype": "Pricing Rule",
		"description": "Review and maintain conditional pricing, discounts and free-item rules.",
		"columns": (
			("name", "Rule"),
			("title", "Title"),
			("apply_on", "Applies On"),
			("price_or_product_discount", "Discount Type"),
			("for_price_list", "Price List"),
			("selling", "Selling"),
			("buying", "Buying"),
			("valid_from", "Valid From"),
			("valid_upto", "Valid Until"),
			("disable", "Disabled"),
		),
		"search_fields": ("name", "title"),
		"filters": (
			{"fieldname": "apply_on", "label": "Applies On", "type": "text"},
			{"fieldname": "price_or_product_discount", "label": "Discount Type", "type": "text"},
			{"fieldname": "for_price_list", "label": "Price List", "type": "price_list"},
			{"fieldname": "selling", "label": "Selling", "type": "boolean"},
			{"fieldname": "buying", "label": "Buying", "type": "boolean"},
			{"fieldname": "disable", "label": "Disabled", "type": "boolean"},
			{"fieldname": "valid_from", "label": "Valid From", "type": "date_from"},
			{"fieldname": "valid_upto", "label": "Valid Until", "type": "date_to"},
		),
	},
	"promotional-schemes": {
		"label": "Promotional Schemes",
		"doctype": "Promotional Scheme",
		"description": "Maintain promotional schemes and the commercial conditions they govern.",
		"columns": (
			("name", "Scheme"),
			("apply_on", "Applies On"),
			("selling", "Selling"),
			("buying", "Buying"),
			("valid_from", "Valid From"),
			("valid_upto", "Valid Until"),
			("disable", "Disabled"),
		),
		"search_fields": ("name",),
		"filters": (
			{"fieldname": "apply_on", "label": "Applies On", "type": "text"},
			{"fieldname": "selling", "label": "Selling", "type": "boolean"},
			{"fieldname": "buying", "label": "Buying", "type": "boolean"},
			{"fieldname": "disable", "label": "Disabled", "type": "boolean"},
			{"fieldname": "valid_from", "label": "Valid From", "type": "date_from"},
			{"fieldname": "valid_upto", "label": "Valid Until", "type": "date_to"},
		),
		"company_scoped": True,
	},
	"coupon-codes": {
		"label": "Coupon Codes",
		"doctype": "Coupon Code",
		"description": "Maintain coupon codes, validity windows, usage limits and linked pricing rules.",
		"columns": (
			("name", "ID"),
			("coupon_code", "Coupon Code"),
			("pricing_rule", "Pricing Rule"),
			("valid_from", "Valid From"),
			("valid_upto", "Valid Until"),
			("maximum_use", "Maximum Use"),
			("used", "Used"),
		),
		"search_fields": ("name", "coupon_code", "pricing_rule"),
		"filters": (
			{"fieldname": "coupon_code", "label": "Coupon Code", "type": "text"},
			{"fieldname": "pricing_rule", "label": "Pricing Rule", "type": "text"},
			{"fieldname": "valid_from", "label": "Valid From", "type": "date_from"},
			{"fieldname": "valid_upto", "label": "Valid Until", "type": "date_to"},
		),
	},
	"loyalty-programs": {
		"label": "Loyalty Programs",
		"doctype": "Loyalty Program",
		"description": "Maintain loyalty programme dates, customer targeting and points conversion settings.",
		"columns": (
			("name", "Programme"),
			("company", "Company"),
			("customer_group", "Customer Group"),
			("from_date", "From Date"),
			("to_date", "To Date"),
			("conversion_factor", "Conversion Factor"),
			("expiry_duration", "Expiry Duration"),
		),
		"search_fields": ("name", "customer_group"),
		"filters": (
			{"fieldname": "customer_group", "label": "Customer Group", "type": "text"},
			{"fieldname": "from_date", "label": "From Date", "type": "date_from"},
			{"fieldname": "to_date", "label": "To Date", "type": "date_to"},
		),
		"company_scoped": True,
	},
}


def _area(area: str) -> dict[str, Any]:
	key = str(area or "").strip()
	config = AREAS.get(key)
	if not config:
		frappe.throw(_("Unsupported pricing and promotions area."))
	return config


def _native_readable_price_lists(*, user: str) -> list[dict[str, Any]]:
	if not frappe.has_permission("Price List", "read", user=user):
		return []
	return [
		dict(row)
		for row in frappe.get_list(
			"Price List",
			fields=["name", "enabled", "selling", "buying", "currency", "owner"],
			order_by="name asc",
			limit_page_length=0,
		)
	]


PRICE_MASTER_ROLES = {"Sales Master Manager", "Purchase Master Manager", "System Manager"}


def _has_price_master_scope(user: str) -> bool:
	return user == "Administrator" or bool(PRICE_MASTER_ROLES.intersection(set(frappe.get_roles(user) or [])))


def _raw_assigned_price_lists(
	*,
	user: str,
	company: str,
	branch: str,
) -> tuple[set[str], dict[str, list[str]], bool]:
	candidates: set[str] = set()
	has_assignment_boundary = False
	sources: dict[str, list[str]] = {
		"user_permission": [],
		"pos_profile": [],
		"branch_pos_profile": [],
		"effective_pos_profile": [],
	}

	price_permissions = get_user_permissions(user).get("Price List", []) or []
	if price_permissions:
		has_assignment_boundary = True
	for row in price_permissions:
		name = str(row.get("doc") or "").strip()
		if name:
			candidates.add(name)
			sources["user_permission"].append(name)

	assigned_profiles = get_user_pos_profiles(user=user, company=company or None)
	profile_names = [str(row.get("name") or "").strip() for row in assigned_profiles if row.get("name")]
	if profile_names:
		has_assignment_boundary = True
		for row in frappe.get_all(
			"POS Profile",
			filters={"name": ["in", profile_names], "disabled": 0},
			fields=["name", "selling_price_list"],
			limit_page_length=0,
		):
			name = str(row.get("selling_price_list") or "").strip()
			if name:
				candidates.add(name)
				sources["pos_profile"].append(name)

	if company and frappe.has_permission("POS Profile", "read", user=user):
		try:
			effective_pos = get_pos_profile(company, user=user)
		except Exception:
			effective_pos = None
		effective_name = ""
		if effective_pos:
			effective_name = str(
				effective_pos.get("name")
				if isinstance(effective_pos, dict)
				else getattr(effective_pos, "name", "")
			).strip()
		if effective_name:
			pos = frappe.db.get_value(
				"POS Profile",
				effective_name,
				["disabled", "company", "selling_price_list"],
				as_dict=True,
			)
			if pos and not pos.get("disabled") and (not pos.get("company") or pos.get("company") == company):
				user_rows = frappe.db.count("POS Profile User", {"parent": effective_name})
				if not user_rows or frappe.db.exists(
					"POS Profile User",
					{"parent": effective_name, "user": user},
				):
					has_assignment_boundary = True
					name = str(pos.get("selling_price_list") or "").strip()
					if name:
						candidates.add(name)
						sources["effective_pos_profile"].append(name)

	if company and branch:
		profile = get_exact_branch_profile(company=company, branch=branch, active_only=True)
		pos_profile = str(getattr(profile, "default_pos_profile", None) or "").strip() if profile else ""
		if pos_profile:
			pos = frappe.db.get_value(
				"POS Profile",
				pos_profile,
				["name", "company", "disabled", "selling_price_list"],
				as_dict=True,
			)
			if pos and not pos.get("disabled") and (not pos.get("company") or pos.get("company") == company):
				user_rows = frappe.db.count("POS Profile User", {"parent": pos_profile})
				if not user_rows or frappe.db.exists(
					"POS Profile User",
					{"parent": pos_profile, "user": user},
				):
					has_assignment_boundary = True
					name = str(pos.get("selling_price_list") or "").strip()
					if name:
						candidates.add(name)
						sources["branch_pos_profile"].append(name)

	for source, values in sources.items():
		sources[source] = sorted({name for name in values if name})
	return candidates, sources, has_assignment_boundary


def _candidate_assigned_price_lists(
	*,
	user: str,
	company: str,
	branch: str,
	native_rows: list[dict[str, Any]],
) -> tuple[set[str], dict[str, list[str]], bool]:
	candidates, sources, has_assignment_boundary = _raw_assigned_price_lists(
		user=user,
		company=company,
		branch=branch,
	)
	native_names = {str(row.get("name") or "").strip() for row in native_rows}
	candidates.intersection_update(native_names)
	for source, values in sources.items():
		sources[source] = sorted({name for name in values if name in native_names})
	return candidates, sources, has_assignment_boundary


def _permission_assignment_scope(user: str | None = None) -> dict[str, Any]:
	user = user or frappe.session.user
	if not user or user == "Guest" or _has_price_master_scope(user):
		return {"restricted": False, "names": []}
	is_session_user = user == frappe.session.user
	operating = (get_operating_context() or {}) if is_session_user else {}
	company = str(operating.get("company") or "").strip()
	branch = str(operating.get("branch") or "").strip()
	names, _sources, has_assignment_boundary = _raw_assigned_price_lists(
		user=user,
		company=company,
		branch=branch,
	)
	return {
		"restricted": has_assignment_boundary,
		"names": sorted(names),
		"company": company,
		"branch": branch,
	}


def _sql_in_condition(field: str, names: list[str]) -> str:
	if not names:
		return "1=0"
	values = ", ".join(frappe.db.escape(name) for name in names)
	return f"{field} in ({values})"


def get_price_list_permission_query_conditions(user: str | None = None) -> str:
	scope = _permission_assignment_scope(user)
	if not scope.get("restricted"):
		return ""
	return _sql_in_condition("`tabPrice List`.`name`", list(scope.get("names") or []))


def get_item_price_permission_query_conditions(user: str | None = None) -> str:
	scope = _permission_assignment_scope(user)
	if not scope.get("restricted"):
		return ""
	return _sql_in_condition("`tabItem Price`.`price_list`", list(scope.get("names") or []))


def has_price_list_permission(
	doc: Any,
	user: str | None = None,
	ptype: str | None = None,
	debug: bool = False,
	**_kwargs: Any,
) -> bool:
	user = user or frappe.session.user
	if ptype == "create" or getattr(doc, "is_new", lambda: False)():
		return True
	scope = _permission_assignment_scope(user)
	if not scope.get("restricted"):
		return True
	name = str(getattr(doc, "name", "") or "").strip()
	return name in set(scope.get("names") or [])


def has_item_price_permission(
	doc: Any,
	user: str | None = None,
	ptype: str | None = None,
	debug: bool = False,
	**_kwargs: Any,
) -> bool:
	user = user or frappe.session.user
	if ptype == "create" or getattr(doc, "is_new", lambda: False)():
		return True
	scope = _permission_assignment_scope(user)
	if not scope.get("restricted"):
		return True
	price_list = str(getattr(doc, "price_list", "") or "").strip()
	return price_list in set(scope.get("names") or [])


def _resolve_price_list_scope() -> dict[str, Any]:
	user = frappe.session.user
	operating = get_operating_context() or {}
	company = str(operating.get("company") or "").strip()
	branch = str(operating.get("branch") or "").strip()
	native_rows = _native_readable_price_lists(user=user)
	native_names = {str(row.get("name") or "").strip() for row in native_rows if row.get("name")}

	if _has_price_master_scope(user):
		allowed = native_names
		mode = "native"
		sources: dict[str, list[str]] = {}
	else:
		assigned, sources, has_assignment_boundary = _candidate_assigned_price_lists(
			user=user,
			company=company,
			branch=branch,
			native_rows=native_rows,
		)
		if has_assignment_boundary:
			allowed = assigned
			mode = "assigned"
		else:
			allowed = native_names
			mode = "native"

	return {
		"mode": mode,
		"names": sorted(allowed),
		"sources": sources,
		"company": company,
		"branch": branch,
		"message": (
			_("Showing price lists assigned to your account and current operating setup.")
			if mode == "assigned"
			else _("Showing price lists available to your account.")
		),
	}


def _apply_price_list_scope(
	*,
	doctype: str,
	meta: Any,
	filters: dict[str, Any],
	scope: dict[str, Any],
) -> None:
	allowed = list(scope.get("names") or [])
	if doctype == "Price List":
		filters["name"] = ["in", allowed] if allowed else "__never__"
	elif doctype == "Item Price" and meta.has_field("price_list") and "price_list" not in filters:
		filters["price_list"] = ["in", allowed] if allowed else "__never__"


def _allowed_pricing_rule_names(scope: dict[str, Any]) -> list[str]:
	if not frappe.db.exists("DocType", "Pricing Rule") or not frappe.has_permission("Pricing Rule", "read"):
		return []
	meta = frappe.get_meta("Pricing Rule")
	fields = ["name"]
	if meta.has_field("company"):
		fields.append("company")
	if meta.has_field("for_price_list"):
		fields.append("for_price_list")
	rows = frappe.get_list(
		"Pricing Rule",
		fields=fields,
		order_by="modified desc",
		limit_page_length=0,
	)
	company = str(scope.get("company") or "").strip()
	allowed_price_lists = set(scope.get("names") or [])
	allowed: list[str] = []
	for row in rows:
		row_company = str(row.get("company") or "").strip()
		if company and row_company and row_company != company:
			continue
		price_list = str(row.get("for_price_list") or "").strip()
		if price_list and price_list not in allowed_price_lists:
			continue
		name = str(row.get("name") or "").strip()
		if name:
			allowed.append(name)
	return allowed


def _allowed_coupon_names(scope: dict[str, Any]) -> list[str]:
	if not frappe.db.exists("DocType", "Coupon Code") or not frappe.has_permission("Coupon Code", "read"):
		return []
	meta = frappe.get_meta("Coupon Code")
	if not meta.has_field("pricing_rule"):
		return frappe.get_list("Coupon Code", pluck="name", limit_page_length=0)
	allowed_rules = set(_allowed_pricing_rule_names(scope))
	rows = frappe.get_list(
		"Coupon Code",
		fields=["name", "pricing_rule"],
		order_by="modified desc",
		limit_page_length=0,
	)
	return [
		str(row.get("name") or "")
		for row in rows
		if row.get("name")
		and (
			not str(row.get("pricing_rule") or "").strip()
			or str(row.get("pricing_rule") or "").strip() in allowed_rules
		)
	]


def _apply_related_pricing_scope(
	*,
	doctype: str,
	filters: dict[str, Any],
	scope: dict[str, Any],
) -> None:
	if doctype == "Pricing Rule":
		allowed = _allowed_pricing_rule_names(scope)
		filters["name"] = ["in", allowed] if allowed else "__never__"
	elif doctype == "Coupon Code":
		allowed = _allowed_coupon_names(scope)
		filters["name"] = ["in", allowed] if allowed else "__never__"


def _available_area(key: str, config: dict[str, Any]) -> dict[str, Any] | None:
	doctype = config["doctype"]
	if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
		return None
	meta = frappe.get_meta(doctype)
	columns = [
		{"fieldname": fieldname, "label": _(label)}
		for fieldname, label in config["columns"]
		if fieldname == "name" or fieldname == "modified" or meta.has_field(fieldname)
	]
	filters = [
		dict(filter_config)
		for filter_config in config.get("filters", ())
		if meta.has_field(filter_config["fieldname"])
	]
	return {
		"key": key,
		"label": _(config["label"]),
		"doctype": doctype,
		"description": _(config["description"]),
		"can_create": int(bool(frappe.has_permission(doctype, "create"))),
		"can_write": int(bool(frappe.has_permission(doctype, "write"))),
		"columns": columns,
		"filters": filters,
	}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def allowed_price_list_query(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict[str, Any] | None = None,
) -> list[list[str]]:
	scope = _resolve_price_list_scope()
	allowed = list(scope.get("names") or [])
	if not allowed:
		return []
	query_filters: list[list[Any]] = [["Price List", "name", "in", allowed]]
	if txt:
		query_filters.append(["Price List", "name", "like", f"%{txt}%"])
	rows = frappe.get_list(
		"Price List",
		filters=query_filters,
		fields=["name"],
		order_by="name asc",
		limit_start=max(0, cint(start)),
		limit_page_length=max(1, min(cint(page_len) or 20, 50)),
	)
	return [[str(row.get("name") or "")] for row in rows if row.get("name")]


def validate_item_price_assignment(doc: Any, method: str | None = None) -> None:
	"""Prevent Item Price writes outside an explicitly assigned operational price-list scope."""
	if frappe.session.user in (None, "", "Guest"):
		return
	scope = _resolve_price_list_scope()
	if scope.get("mode") != "assigned":
		return
	price_list = str(getattr(doc, "price_list", None) or "").strip()
	if not price_list or price_list in set(scope.get("names") or []):
		return
	frappe.throw(
		_("Price List {0} is not assigned to your account or current operating setup.").format(
			frappe.bold(price_list)
		),
		frappe.PermissionError,
	)


@frappe.whitelist()
def get_pricing_promotions_workspace() -> dict[str, Any]:
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Sign in to open Pricing & Promotions."), frappe.PermissionError)

	operating = get_operating_context() or {}
	price_list_scope = _resolve_price_list_scope()
	areas = [
		resolved
		for key, config in AREAS.items()
		if (resolved := _available_area(key, config))
	]
	if not price_list_scope["names"]:
		for area in areas:
			if area.get("doctype") == "Item Price":
				area["can_create"] = 0
	if not areas:
		frappe.throw(
			_("You do not have permission to view pricing and promotions setup."),
			frappe.PermissionError,
		)
	return {
		"title": _("Pricing & Promotions"),
		"description": _(
			"Manage price lists, item prices, pricing rules, promotions, coupons and loyalty programmes "
			"from one workspace."
		),
		"company": str(operating.get("company") or ""),
		"branch": str(operating.get("branch") or ""),
		"user_name": get_user_fullname(frappe.session.user),
		"areas": areas,
		"price_list_scope": {
			"mode": price_list_scope["mode"],
			"message": price_list_scope["message"],
			"names": price_list_scope["names"],
		},
		"price_list_options": [
			{"value": name, "label": name}
			for name in price_list_scope["names"]
		],
		"default_page_length": DEFAULT_PAGE_LENGTH,
	}


def _coerce_filters(value: dict | str | None) -> dict[str, Any]:
	if isinstance(value, str):
		value = frappe.parse_json(value)
	return dict(value or {})


def _boolean_filter(value: Any) -> int | None:
	text = str(value or "").strip().lower()
	if text in {"yes", "1", "true"}:
		return 1
	if text in {"no", "0", "false"}:
		return 0
	return None


def _build_filters(config: dict[str, Any], meta: Any, supplied: dict[str, Any]) -> dict[str, Any]:
	filters: dict[str, Any] = {}
	allowed = {row["fieldname"]: row for row in config.get("filters", ())}
	for fieldname, raw in supplied.items():
		spec = allowed.get(fieldname)
		if not spec or not meta.has_field(fieldname):
			continue
		value = str(raw or "").strip()
		if not value:
			continue
		kind = spec.get("type")
		if kind == "boolean":
			resolved = _boolean_filter(value)
			if resolved is not None:
				filters[fieldname] = resolved
		elif kind == "date_from":
			filters[fieldname] = [">=", getdate(value)]
		elif kind == "date_to":
			filters[fieldname] = ["<=", getdate(value)]
		elif kind == "price_list":
			filters[fieldname] = value
		else:
			filters[fieldname] = ["like", f"%{value}%"]

	if config.get("company_scoped") and meta.has_field("company"):
		operating = get_operating_context() or {}
		company = str(operating.get("company") or "").strip()
		if not company:
			filters["name"] = "__never__"
		else:
			filters["company"] = company
	return filters


@frappe.whitelist()
def get_pricing_promotions_records(
	area: str,
	search: str = "",
	filters: dict | str | None = None,
	start: int = 0,
	page_length: int = DEFAULT_PAGE_LENGTH,
	sort_by: str = "modified",
	sort_order: str = "desc",
) -> dict[str, Any]:
	config = _area(area)
	doctype = config["doctype"]
	if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
		frappe.throw(
			_("You do not have permission to view {0}.").format(_(config["label"])),
			frappe.PermissionError,
		)

	meta = frappe.get_meta(doctype)
	supplied = _coerce_filters(filters)
	price_list_scope = _resolve_price_list_scope()
	query_filters = _build_filters(config, meta, supplied)
	_apply_price_list_scope(
		doctype=doctype,
		meta=meta,
		filters=query_filters,
		scope=price_list_scope,
	)
	_apply_related_pricing_scope(
		doctype=doctype,
		filters=query_filters,
		scope=price_list_scope,
	)
	if doctype in {"Item Price", "Pricing Rule"}:
		requested_price_list = str(
			supplied.get("price_list")
			or supplied.get("for_price_list")
			or ""
		).strip()
		if requested_price_list and requested_price_list not in set(price_list_scope["names"]):
			frappe.throw(
				_("You do not have access to the selected Price List."),
				frappe.PermissionError,
			)
	search_text = str(search or "").strip()
	or_filters: list[list[Any]] = []
	if search_text:
		for fieldname in config.get("search_fields", ("name",)):
			if fieldname == "name" or meta.has_field(fieldname):
				or_filters.append([fieldname, "like", f"%{search_text}%"])

	fields = ["name"]
	for fieldname, _label in config["columns"]:
		if fieldname not in fields and (fieldname == "modified" or meta.has_field(fieldname)):
			fields.append(fieldname)

	start = max(0, cint(start))
	page_length = max(10, min(cint(page_length) or DEFAULT_PAGE_LENGTH, MAX_PAGE_LENGTH))
	allowed_sort_fields = {
		fieldname
		for fieldname, _label in config["columns"]
		if fieldname == "name" or fieldname == "modified" or meta.has_field(fieldname)
	}
	allowed_sort_fields.update({"name", "modified"})
	sort_by = str(sort_by or "modified").strip()
	if sort_by not in allowed_sort_fields:
		sort_by = "modified"
	sort_order = "asc" if str(sort_order or "").lower() == "asc" else "desc"
	rows = frappe.get_list(
		doctype,
		filters=query_filters,
		or_filters=or_filters,
		fields=fields,
		order_by=f"{sort_by} {sort_order}",
		limit_start=start,
		limit_page_length=page_length + 1,
	)
	has_more = len(rows) > page_length
	rows = rows[:page_length]
	return {
		"area": area,
		"doctype": doctype,
		"rows": [dict(row) for row in rows],
		"has_more": has_more,
		"next_start": start + len(rows),
		"page_length": page_length,
		"can_create": int(bool(frappe.has_permission(doctype, "create"))),
		"sort_by": sort_by,
		"sort_order": sort_order,
	}
