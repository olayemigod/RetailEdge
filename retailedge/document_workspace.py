from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from retailedge.api.permission import has_app_permission
from retailedge.branch_context import (
	get_user_allowed_branches,
	has_field,
	user_has_global_branch_access,
	validate_user_branch_access,
)
from retailedge.ui_identity import get_retailedge_ui_identity


PAGE_LENGTH_MAX = 100
LINK_PAGE_LENGTH_MAX = 30
LAYOUT_FIELDTYPES = {"Tab Break", "Section Break", "Column Break"}
SYSTEM_FIELDS = {
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
	"idx",
	"parent",
	"parentfield",
	"parenttype",
	"amended_from",
}
COMPANY_DEPENDENT_FIELDS = [
	"branch",
	"default_pos_profile",
	"default_pos_opening_cash_account",
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
	"expense_account",
	"default_account",
]
BRANCH_DEPENDENT_FIELDS = [
	"default_pos_profile",
	"default_warehouse",
	"default_source_warehouse",
	"default_target_warehouse",
	"default_returns_warehouse",
]
COMPANY_SCOPED_LINKS = {
	"Branch",
	"POS Profile",
	"Account",
	"Warehouse",
	"Cost Center",
}
CHILD_ROLE_BY_FIELD = {
	"default_cashiers": "Cashier",
	"default_managers": "Manager",
	"default_auditors": "Auditor",
}


RESOURCE_CONFIG: dict[str, dict[str, Any]] = {
	"branch-profiles": {
		"doctype": "RetailEdge Branch Profile",
		"title": _("Branch Profiles"),
		"singular": _("Branch Profile"),
		"subtitle": _("Maintain branch-safe POS, warehouse, account, staff and audit defaults."),
		"icon": "building",
		"list_fields": [
			"name",
			"profile_name",
			"enabled",
			"company",
			"branch",
			"default_pos_profile",
			"is_default_for_company",
			"modified",
		],
		"search_fields": ["name", "profile_name", "company", "branch", "default_pos_profile"],
		"filter_fields": ["enabled", "company", "branch"],
		"branch_field": "branch",
		"allow_create": True,
		"allow_delete": False,
	},
	"expense-categories": {
		"doctype": "RetailEdge Expense Category",
		"title": _("Expense Categories"),
		"singular": _("Expense Category"),
		"subtitle": _("Maintain controlled retail expense classifications and their accounting defaults."),
		"icon": "wallet",
		"list_fields": [
			"name",
			"category_name",
			"category_code",
			"company",
			"expense_account",
			"default_cost_center",
			"is_active",
			"modified",
		],
		"search_fields": ["name", "category_name", "category_code", "company", "expense_account"],
		"filter_fields": ["is_active", "company"],
		"allow_create": True,
		"allow_delete": False,
	},
	"statement-mapping-templates": {
		"doctype": "RetailEdge Statement Mapping Template",
		"title": _("Statement Mapping Templates"),
		"singular": _("Statement Mapping Template"),
		"subtitle": _("Define reusable bank, POS and mobile-money statement column mappings."),
		"icon": "list",
		"list_fields": [
			"name",
			"template_name",
			"enabled",
			"company",
			"statement_type",
			"payment_category",
			"bank_or_provider_name",
			"default_account",
			"modified",
		],
		"search_fields": [
			"name",
			"template_name",
			"company",
			"statement_type",
			"payment_category",
			"bank_or_provider_name",
		],
		"filter_fields": ["enabled", "company", "statement_type", "payment_category"],
		"allow_create": True,
		"allow_delete": False,
	},
	"settings": {
		"doctype": "RetailEdge Settings",
		"title": _("RetailEdge Settings"),
		"singular": _("RetailEdge Settings"),
		"subtitle": _("Configure POS, cost visibility, expense, audit, branch and bank-matching controls."),
		"icon": "settings",
		"is_single": True,
		"allow_create": False,
		"allow_delete": False,
	},
}


def _require_internal_user() -> None:
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to use RetailEdge."), frappe.PermissionError)
	if not has_app_permission():
		frappe.throw(_("You do not have access to RetailEdge."), frappe.PermissionError)


def _require_resource(resource: str) -> dict[str, Any]:
	_require_internal_user()
	key = str(resource or "").strip().lower()
	config = RESOURCE_CONFIG.get(key)
	if not config:
		frappe.throw(_("This RetailEdge document workspace is not available."), frappe.PermissionError)
	if not frappe.db.exists("DocType", config["doctype"]):
		frappe.throw(_("{0} is not installed on this site.").format(config["doctype"]))
	return {"key": key, **config}


def _parse_json_object(value: str | dict | None) -> dict:
	if not value:
		return {}
	if isinstance(value, dict):
		return value
	parsed = frappe.parse_json(value)
	if not isinstance(parsed, dict):
		frappe.throw(_("Expected a JSON object."), frappe.ValidationError)
	return parsed


def _field_label(field) -> str:
	return field.label or field.fieldname.replace("_", " ").title()


def _field_clear_fields(resource: str, fieldname: str) -> list[str]:
	if fieldname != "company":
		if resource == "branch-profiles" and fieldname == "branch":
			return BRANCH_DEPENDENT_FIELDS
		return []
	if resource == "branch-profiles":
		return COMPANY_DEPENDENT_FIELDS
	if resource == "expense-categories":
		return ["expense_account", "default_cost_center"]
	if resource == "statement-mapping-templates":
		return ["default_account"]
	return []


def _serialize_field(field, *, resource: str, child: bool = False) -> dict[str, Any]:
	payload = {
		"fieldname": field.fieldname,
		"fieldtype": field.fieldtype,
		"label": _field_label(field),
		"options": field.options or "",
		"description": field.description or "",
		"default": field.default,
		"reqd": cint(field.reqd),
		"read_only": cint(field.read_only),
		"hidden": cint(field.hidden),
		"depends_on": field.depends_on or "",
		"mandatory_depends_on": field.mandatory_depends_on or "",
		"read_only_depends_on": field.read_only_depends_on or "",
		"in_list_view": cint(field.in_list_view),
	}
	clear_fields = _field_clear_fields(resource, field.fieldname)
	if clear_fields:
		payload["clear_fields"] = clear_fields
	if child:
		payload["columns"] = cint(getattr(field, "columns", 0))
	return payload


def _child_fields(resource: str, options: str) -> list[dict[str, Any]]:
	if not options or not frappe.db.exists("DocType", options):
		return []
	meta = frappe.get_meta(options)
	fields = []
	for field in meta.fields:
		if not field.fieldname or field.fieldname in SYSTEM_FIELDS or field.fieldtype in LAYOUT_FIELDTYPES:
			continue
		if field.hidden and not field.depends_on:
			continue
		fields.append(_serialize_field(field, resource=resource, child=True))
	return fields


def _build_form_schema(config: dict[str, Any], meta) -> dict[str, Any]:
	tabs: list[dict[str, Any]] = []
	current_tab: dict[str, Any] | None = None
	current_section: dict[str, Any] | None = None

	def ensure_tab() -> dict[str, Any]:
		nonlocal current_tab
		if current_tab is None:
			current_tab = {"key": "general", "label": _("General"), "description": "", "sections": []}
			tabs.append(current_tab)
		return current_tab

	def ensure_section() -> dict[str, Any]:
		nonlocal current_section
		tab = ensure_tab()
		if current_section is None:
			current_section = {
				"key": f"section-{len(tab['sections']) + 1}",
				"label": "",
				"description": "",
				"columns": 1,
				"fields": [],
			}
			tab["sections"].append(current_section)
		return current_section

	for field in meta.fields:
		if not field.fieldname:
			continue
		if field.fieldtype == "Tab Break":
			current_tab = {
				"key": field.fieldname,
				"label": _field_label(field),
				"description": field.description or "",
				"sections": [],
			}
			tabs.append(current_tab)
			current_section = None
			continue
		if field.fieldtype == "Section Break":
			tab = ensure_tab()
			current_section = {
				"key": field.fieldname,
				"label": _field_label(field),
				"description": field.description or "",
				"depends_on": field.depends_on or "",
				"collapsible": cint(getattr(field, "collapsible", 0)),
				"columns": 1,
				"fields": [],
			}
			tab["sections"].append(current_section)
			continue
		if field.fieldtype == "Column Break":
			section = ensure_section()
			section["columns"] = min(3, cint(section.get("columns")) + 1)
			continue
		if field.fieldname in SYSTEM_FIELDS:
			continue
		if field.hidden and not field.depends_on:
			continue
		serialized = _serialize_field(field, resource=config["key"])
		if field.fieldtype == "Table":
			serialized["child_fields"] = _child_fields(config["key"], field.options)
		ensure_section()["fields"].append(serialized)

	return {
		"tabs": [
			{**tab, "sections": [section for section in tab["sections"] if section["fields"]]}
			for tab in tabs
			if any(section["fields"] for section in tab["sections"])
		]
	}


def _column_schema(meta, fieldnames: list[str]) -> list[dict[str, Any]]:
	columns = []
	for fieldname in fieldnames:
		if fieldname == "name":
			columns.append({"fieldname": "name", "label": _("ID"), "fieldtype": "Data"})
			continue
		if fieldname == "modified":
			columns.append({"fieldname": "modified", "label": _("Modified"), "fieldtype": "Datetime"})
			continue
		field = meta.get_field(fieldname)
		if not field:
			continue
		columns.append(
			{
				"fieldname": fieldname,
				"label": _field_label(field),
				"fieldtype": field.fieldtype,
				"status": fieldname in {"enabled", "is_active", "status", "workflow_state"},
			}
		)
	return columns


def _filter_schema(config: dict[str, Any], meta, fieldnames: list[str]) -> list[dict[str, Any]]:
	fields = []
	for fieldname in fieldnames:
		field = meta.get_field(fieldname)
		if not field:
			continue
		serialized = _serialize_field(field, resource=config["key"])
		serialized["reqd"] = 0
		serialized["read_only"] = 0
		fields.append(serialized)
	return fields


def _permissions(config: dict[str, Any], doc=None) -> dict[str, bool]:
	doctype = config["doctype"]
	if doc is None:
		return {
			"read": bool(frappe.has_permission(doctype, ptype="read")),
			"create": bool(config.get("allow_create") and frappe.has_permission(doctype, ptype="create")),
			"write": bool(frappe.has_permission(doctype, ptype="write")),
			"delete": False,
		}
	return {
		"read": bool(doc.has_permission("read")),
		"create": bool(config.get("allow_create") and frappe.has_permission(doctype, ptype="create")),
		"write": bool(doc.has_permission("write")),
		"delete": False,
	}


def _allowed_branch_filters(company: str | None = None) -> dict[str, Any]:
	if user_has_global_branch_access(user=frappe.session.user):
		return {}
	allowed = get_user_allowed_branches(user=frappe.session.user, company=company).get("branches") or []
	return {"branch": ["in", allowed]} if allowed else {}


def _resource_list_filters(config: dict[str, Any], requested: dict[str, Any]) -> dict[str, Any]:
	if config["key"] == "branch-profiles":
		return _allowed_branch_filters(requested.get("company"))
	return {}


def _assert_branch_profile_scope(doc) -> None:
	validate_user_branch_access(
		doc.get("branch"),
		user=frappe.session.user,
		company=doc.get("company"),
		throw=True,
	)


def _document_values(doc, schema: dict[str, Any]) -> dict[str, Any]:
	values: dict[str, Any] = {}
	for tab in schema.get("tabs") or []:
		for section in tab.get("sections") or []:
			for field in section.get("fields") or []:
				fieldname = field["fieldname"]
				if field["fieldtype"] == "Password":
					values[fieldname] = ""
					field["has_value"] = bool(doc.get(fieldname))
					continue
				value = doc.get(fieldname)
				if field["fieldtype"] == "Table":
					values[fieldname] = [row.as_dict(no_nulls=False) for row in value or []]
				else:
					values[fieldname] = value
	return values


def _writable_fieldnames(meta) -> set[str]:
	return {
		field.fieldname
		for field in meta.fields
		if field.fieldname
		and field.fieldname not in SYSTEM_FIELDS
		and field.fieldtype not in LAYOUT_FIELDTYPES
		and not field.read_only
		and not getattr(field, "virtual", False)
	}


def _apply_values(doc, meta, values: dict[str, Any]) -> None:
	allowed = _writable_fieldnames(meta)
	for fieldname, value in values.items():
		if fieldname not in allowed:
			continue
		field = meta.get_field(fieldname)
		if field.fieldtype == "Password" and value in (None, "", "********"):
			continue
		if field.fieldtype == "Table":
			rows = value if isinstance(value, list) else []
			doc.set(fieldname, [])
			child_meta = frappe.get_meta(field.options)
			child_allowed = _writable_fieldnames(child_meta)
			for row in rows:
				if not isinstance(row, dict):
					continue
				payload = {key: item for key, item in row.items() if key in child_allowed or key == "name"}
				if fieldname in CHILD_ROLE_BY_FIELD:
					payload["role_type"] = CHILD_ROLE_BY_FIELD[fieldname]
				doc.append(fieldname, payload)
			continue
		doc.set(fieldname, value)


def _check_readable_link(doctype: str, name: str) -> None:
	if not name:
		return
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	linked = frappe.get_doc(doctype, name)
	linked.check_permission("read")
	if has_field(doctype, "disabled") and cint(linked.get("disabled")):
		frappe.throw(_("{0} {1} is disabled.").format(doctype, name))
	if has_field(doctype, "enabled") and not cint(linked.get("enabled")):
		frappe.throw(_("{0} {1} is disabled.").format(doctype, name))


def _validate_company_link(
	doctype: str,
	name: str,
	company: str | None,
	*,
	require_non_group: bool = False,
	required_root_type: str | None = None,
) -> None:
	if not name:
		return
	_check_readable_link(doctype, name)
	if company and has_field(doctype, "company"):
		linked_company = frappe.db.get_value(doctype, name, "company")
		if linked_company and linked_company != company:
			frappe.throw(
				_("{0} {1} belongs to Company {2}, not {3}.").format(
					doctype,
					name,
					linked_company,
					company,
				)
			)
	if require_non_group and has_field(doctype, "is_group") and cint(frappe.db.get_value(doctype, name, "is_group")):
		frappe.throw(_("{0} {1} must be a ledger record, not a group.").format(doctype, name))
	if required_root_type and has_field(doctype, "root_type"):
		root_type = frappe.db.get_value(doctype, name, "root_type")
		if root_type and root_type != required_root_type:
			frappe.throw(_("{0} {1} must have Root Type {2}.").format(doctype, name, required_root_type))


def _validate_branch_profile_links(doc) -> None:
	_check_readable_link("Company", doc.get("company"))
	_check_readable_link("Branch", doc.get("branch"))
	_assert_branch_profile_scope(doc)
	branch_company = frappe.db.get_value("Branch", doc.get("branch"), "company") if has_field("Branch", "company") else None
	if branch_company and branch_company != doc.get("company"):
		frappe.throw(_("Branch {0} does not belong to Company {1}.").format(doc.get("branch"), doc.get("company")))

	meta = frappe.get_meta(doc.doctype)
	for field in meta.fields:
		if field.fieldtype != "Link" or not doc.get(field.fieldname):
			continue
		options = field.options
		_check_readable_link(options, doc.get(field.fieldname))
		if options in COMPANY_SCOPED_LINKS and has_field(options, "company"):
			linked_company = frappe.db.get_value(options, doc.get(field.fieldname), "company")
			if linked_company and linked_company != doc.get("company"):
				frappe.throw(
					_("{0} {1} belongs to Company {2}, not {3}.").format(
						options,
						doc.get(field.fieldname),
						linked_company,
						doc.get("company"),
					)
				)

	for table_field in CHILD_ROLE_BY_FIELD:
		for row in doc.get(table_field) or []:
			_check_readable_link("User", row.get("user"))


def _validate_expense_category_links(doc) -> None:
	company = doc.get("company")
	_check_readable_link("Company", company)
	_validate_company_link(
		"Account",
		doc.get("expense_account"),
		company,
		require_non_group=True,
		required_root_type="Expense",
	)
	_validate_company_link(
		"Cost Center",
		doc.get("default_cost_center"),
		company,
		require_non_group=True,
	)


def _validate_statement_mapping_links(doc) -> None:
	company = doc.get("company")
	_check_readable_link("Company", company)
	_validate_company_link("Account", doc.get("default_account"), company, require_non_group=True)


def _validate_resource_document(config: dict[str, Any], doc) -> None:
	if config["key"] == "branch-profiles":
		_validate_branch_profile_links(doc)
	elif config["key"] == "expense-categories":
		_validate_expense_category_links(doc)
	elif config["key"] == "statement-mapping-templates":
		_validate_statement_mapping_links(doc)


def _settings_company() -> str:
	identity = get_retailedge_ui_identity()
	return identity.get("company") or frappe.defaults.get_user_default("Company") or ""


def _default_document_context(meta) -> dict[str, Any]:
	identity = get_retailedge_ui_identity()
	defaults: dict[str, Any] = {}
	if meta.has_field("company") and identity.get("company"):
		defaults["company"] = identity.get("company")
	if meta.has_field("branch") and identity.get("branch"):
		defaults["branch"] = identity.get("branch")
	return defaults


@frappe.whitelist()
def get_resource_definition(resource: str) -> dict[str, Any]:
	config = _require_resource(resource)
	meta = frappe.get_meta(config["doctype"])
	permissions = _permissions(config)
	if not permissions["read"]:
		frappe.throw(_("You are not permitted to view {0}.").format(config["doctype"]), frappe.PermissionError)
	return {
		"resource": config["key"],
		"doctype": config["doctype"],
		"title": config["title"],
		"singular": config["singular"],
		"subtitle": config["subtitle"],
		"icon": config["icon"],
		"is_single": bool(config.get("is_single")),
		"permissions": permissions,
		"columns": _column_schema(meta, config.get("list_fields") or []),
		"filters": _filter_schema(config, meta, config.get("filter_fields") or []),
	}


@frappe.whitelist()
def get_document_list(
	resource: str,
	search: str = "",
	filters: str | dict | None = None,
	start: int = 0,
	page_length: int = 25,
) -> dict[str, Any]:
	config = _require_resource(resource)
	if config.get("is_single"):
		frappe.throw(_("This resource is a single settings document."), frappe.ValidationError)
	doctype = config["doctype"]
	if not frappe.has_permission(doctype, ptype="read"):
		frappe.throw(_("You are not permitted to view {0}.").format(doctype), frappe.PermissionError)
	meta = frappe.get_meta(doctype)
	requested = _parse_json_object(filters)
	query_filters = _resource_list_filters(config, requested)
	allowed_filters = set(config.get("filter_fields") or [])
	for fieldname, value in requested.items():
		if fieldname in allowed_filters and value not in (None, "", []):
			query_filters[fieldname] = value
	query = str(search or "").strip()
	or_filters = None
	if query:
		or_filters = [
			[doctype, fieldname, "like", f"%{query}%"]
			for fieldname in config.get("search_fields") or ["name"]
			if fieldname == "name" or meta.has_field(fieldname)
		]
	start = max(cint(start), 0)
	page_length = min(max(cint(page_length) or 25, 1), PAGE_LENGTH_MAX)
	fields = [
		fieldname
		for fieldname in config.get("list_fields") or ["name"]
		if fieldname == "name" or meta.has_field(fieldname)
	]
	rows = frappe.get_list(
		doctype,
		fields=fields,
		filters=query_filters,
		or_filters=or_filters,
		order_by=f"{meta.sort_field or 'modified'} {meta.sort_order or 'DESC'}",
		start=start,
		page_length=page_length,
	)
	count_rows = frappe.get_list(
		doctype,
		fields=[{"COUNT": "*", "as": "total"}],
		filters=query_filters,
		or_filters=or_filters,
		limit_page_length=1,
	)
	return {
		"rows": rows,
		"total": cint(count_rows[0].get("total")) if count_rows else 0,
		"start": start,
		"page_length": page_length,
	}


@frappe.whitelist()
def get_document(resource: str, name: str | None = None, defaults: str | dict | None = None) -> dict[str, Any]:
	config = _require_resource(resource)
	doctype = config["doctype"]
	meta = frappe.get_meta(doctype)
	is_new = not name and not config.get("is_single")
	if config.get("is_single"):
		doc = frappe.get_single(doctype)
		doc.check_permission("read")
	elif name:
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("read")
		if config["key"] == "branch-profiles":
			_assert_branch_profile_scope(doc)
	else:
		if not config.get("allow_create") or not frappe.has_permission(doctype, ptype="create"):
			frappe.throw(_("You are not permitted to create {0}.").format(doctype), frappe.PermissionError)
		doc = frappe.new_doc(doctype)
		initial = _default_document_context(meta)
		initial.update(_parse_json_object(defaults))
		for fieldname, value in initial.items():
			if value not in (None, "") and meta.has_field(fieldname):
				doc.set(fieldname, value)
		if config["key"] == "branch-profiles" and doc.get("branch"):
			_assert_branch_profile_scope(doc)

	schema = _build_form_schema(config, meta)
	permissions = _permissions(config, doc)
	return {
		"resource": config["key"],
		"doctype": doctype,
		"name": None if is_new else doc.name,
		"is_new": is_new,
		"is_single": bool(config.get("is_single")),
		"title": config["singular"] if is_new else (doc.get(meta.title_field) if meta.title_field else doc.name),
		"schema": schema,
		"values": _document_values(doc, schema),
		"docstatus": cint(doc.docstatus),
		"state": _("New") if is_new else _("Saved"),
		"permissions": permissions,
		"workflow_transitions": [],
		"actions": [],
		"modified": doc.modified if not is_new else None,
		"context_company": doc.get("company") if meta.has_field("company") else _settings_company(),
	}


@frappe.whitelist()
def save_document(
	resource: str,
	values: str | dict,
	name: str | None = None,
	modified: str | None = None,
) -> dict[str, Any]:
	config = _require_resource(resource)
	doctype = config["doctype"]
	meta = frappe.get_meta(doctype)
	if config.get("is_single"):
		doc = frappe.get_single(doctype)
		doc.check_permission("write")
		if modified and str(doc.modified) != str(modified):
			frappe.throw(_("These settings changed after you opened them. Reload before saving."), frappe.TimestampMismatchError)
	elif name:
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("write")
		if config["key"] == "branch-profiles":
			_assert_branch_profile_scope(doc)
		if modified and str(doc.modified) != str(modified):
			frappe.throw(_("This document changed after you opened it. Reload before saving."), frappe.TimestampMismatchError)
	else:
		if not config.get("allow_create") or not frappe.has_permission(doctype, ptype="create"):
			frappe.throw(_("You are not permitted to create {0}.").format(doctype), frappe.PermissionError)
		doc = frappe.new_doc(doctype)

	_apply_values(doc, meta, _parse_json_object(values))
	_validate_resource_document(config, doc)
	if doc.is_new():
		doc.insert()
	else:
		doc.save()
	return get_document(config["key"], None if config.get("is_single") else doc.name)


def _allowed_child_doctypes(config: dict[str, Any]) -> set[str]:
	meta = frappe.get_meta(config["doctype"])
	return {field.options for field in meta.fields if field.fieldtype == "Table" and field.options}


def _option_company(config: dict[str, Any], context: dict[str, Any]) -> str:
	if context.get("company"):
		return context.get("company")
	if config.get("is_single"):
		return _settings_company()
	return ""


def _option_filters(config: dict[str, Any], field, context: dict[str, Any]) -> dict[str, Any]:
	options = field.options
	filters: dict[str, Any] = {}
	company = _option_company(config, context)
	if options == "Branch":
		if not company:
			return {"name": ["in", []]}
		if has_field(options, "company"):
			filters["company"] = company
		if not user_has_global_branch_access(user=frappe.session.user):
			allowed = get_user_allowed_branches(user=frappe.session.user, company=company).get("branches") or []
			filters["name"] = ["in", allowed]
	elif options in COMPANY_SCOPED_LINKS and has_field(options, "company"):
		if not company:
			return {"name": ["in", []]}
		filters["company"] = company
	if options in {"Account", "Warehouse", "Cost Center"} and has_field(options, "is_group"):
		filters["is_group"] = 0
	if config["key"] == "expense-categories" and field.fieldname == "expense_account" and has_field("Account", "root_type"):
		filters["root_type"] = "Expense"
	if options == "Item" and has_field(options, "is_sales_item"):
		filters["is_sales_item"] = 1
	if options == "User":
		if has_field(options, "enabled"):
			filters["enabled"] = 1
		if has_field(options, "user_type"):
			filters["user_type"] = "System User"
	elif has_field(options, "disabled"):
		filters["disabled"] = 0
	elif has_field(options, "enabled"):
		filters["enabled"] = 1
	return filters


@frappe.whitelist()
def get_link_options(
	resource: str,
	fieldname: str,
	query: str = "",
	values: str | dict | None = None,
	child_doctype: str | None = None,
	page_length: int = 20,
) -> list[dict[str, Any]]:
	config = _require_resource(resource)
	if child_doctype and child_doctype not in _allowed_child_doctypes(config):
		frappe.throw(_("This child table is not available for the selected RetailEdge resource."), frappe.PermissionError)
	parent_meta = frappe.get_meta(child_doctype) if child_doctype else frappe.get_meta(config["doctype"])
	field = parent_meta.get_field(fieldname)
	if not field or field.fieldtype not in {"Link", "Dynamic Link"}:
		frappe.throw(_("This field does not support record lookup."), frappe.ValidationError)
	context = _parse_json_object(values)
	options = context.get(field.options) if field.fieldtype == "Dynamic Link" else field.options
	if not options or not frappe.db.exists("DocType", options) or not frappe.has_permission(options, ptype="read"):
		return []
	page_length = min(max(cint(page_length) or 20, 1), LINK_PAGE_LENGTH_MAX)
	text = str(query or "").strip()
	option_meta = frappe.get_meta(options)
	title_field = option_meta.title_field if option_meta.title_field and option_meta.has_field(option_meta.title_field) else "name"
	fields = ["name"]
	for candidate in (title_field, "company", "account_name", "warehouse_name", "cost_center_name", "full_name"):
		if candidate != "name" and option_meta.has_field(candidate) and candidate not in fields:
			fields.append(candidate)
	search_fields = ["name"]
	for candidate in (title_field, *(str(option_meta.search_fields or "").split(","))):
		candidate = str(candidate or "").strip()
		if candidate and option_meta.has_field(candidate) and candidate not in search_fields:
			search_fields.append(candidate)
	or_filters = [[options, candidate, "like", f"%{text}%"] for candidate in search_fields[:5]] if text else None
	rows = frappe.get_list(
		options,
		fields=fields,
		filters=_option_filters(config, field, context),
		or_filters=or_filters,
		order_by=f"{title_field} asc",
		page_length=page_length,
	)
	result = []
	for row in rows:
		label = (
			row.get(title_field)
			or row.get("full_name")
			or row.get("account_name")
			or row.get("warehouse_name")
			or row.get("cost_center_name")
			or row.get("name")
		)
		description_parts = []
		if label != row.get("name"):
			description_parts.append(row.get("name"))
		if row.get("company"):
			description_parts.append(row.get("company"))
		result.append(
			{
				"value": row.get("name"),
				"label": label,
				"description": " · ".join(part for part in description_parts if part),
			}
		)
	return result
