from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, getdate
from frappe.utils.user import get_user_fullname

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
			{"fieldname": "price_list", "label": "Price List", "type": "text"},
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
		"columns": columns,
		"filters": filters,
	}


@frappe.whitelist()
def get_pricing_promotions_workspace() -> dict[str, Any]:
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Sign in to open Pricing & Promotions."), frappe.PermissionError)

	operating = get_operating_context() or {}
	areas = [
		resolved
		for key, config in AREAS.items()
		if (resolved := _available_area(key, config))
	]
	if not areas:
		frappe.throw(
			_("You do not have permission to view pricing and promotions setup."),
			frappe.PermissionError,
		)
	return {
		"title": _("Pricing & Promotions"),
		"description": _("Manage price lists, item prices, pricing rules, promotions, coupons and loyalty programmes from one workspace."),
		"company": str(operating.get("company") or ""),
		"branch": str(operating.get("branch") or ""),
		"user_name": get_user_fullname(frappe.session.user),
		"areas": areas,
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
) -> dict[str, Any]:
	config = _area(area)
	doctype = config["doctype"]
	if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
		frappe.throw(_("You do not have permission to view {0}.").format(_(config["label"])), frappe.PermissionError)

	meta = frappe.get_meta(doctype)
	supplied = _coerce_filters(filters)
	query_filters = _build_filters(config, meta, supplied)
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
	rows = frappe.get_list(
		doctype,
		filters=query_filters,
		or_filters=or_filters,
		fields=fields,
		order_by="modified desc",
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
	}
