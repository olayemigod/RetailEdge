from __future__ import annotations

import frappe

from retailedge.branch_context import has_field, resolve_retailedge_operational_defaults
from retailedge.transaction_branch_attribution import (
	apply_transaction_branch_attribution,
	get_branch_attribution_target_doctypes,
	validate_sales_invoice_with_branch_attribution,
)
from retailedge.utils.settings import get_retailedge_settings


SALES_DOCTYPES = {"Sales Order", "Delivery Note", "Sales Invoice", "POS Invoice"}
PURCHASE_DOCTYPES = {"Purchase Order", "Purchase Receipt", "Purchase Invoice"}
DEFAULT_APPLICATION_MANAGER_ROLES = {
	"System Manager",
	"Accounts Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}
WAREHOUSE_CONTEXT_FIELDS = (
	"warehouse",
	"set_warehouse",
	"default_warehouse",
	"target_warehouse",
	"to_warehouse",
	"from_warehouse",
	"source_warehouse",
)


def get_branch_default_application_settings():
	settings = _get_settings_doc()
	return {
		"enabled": bool(getattr(settings, "enable_branch_default_application", 1)),
		"apply_warehouse": bool(getattr(settings, "apply_branch_default_warehouse", 1)),
		"apply_cost_center": bool(getattr(settings, "apply_branch_default_cost_center", 1)),
		"apply_accounts": bool(getattr(settings, "apply_branch_default_accounts", 0)),
		"apply_pos_profile": bool(getattr(settings, "apply_branch_default_pos_profile", 1)),
	}


def apply_branch_attribution_and_defaults(doc, method=None, overwrite=False):
	doctype = getattr(doc, "doctype", None)
	if doctype == "Sales Invoice":
		validate_sales_invoice_with_branch_attribution(doc, method=method)
	elif doctype in set(get_branch_attribution_target_doctypes()):
		apply_transaction_branch_attribution(doc, method=method, overwrite=False)
	return apply_branch_profile_defaults_to_doc(doc, method=method, overwrite=overwrite)


def apply_branch_profile_defaults_to_doc(doc, method=None, overwrite=False):
	summary = {"applied": [], "skipped": [], "messages": []}
	if not getattr(doc, "doctype", None):
		summary["messages"].append("Branch defaults were skipped because the document type is missing.")
		return summary
	if getattr(doc, "docstatus", 0) in (1, 2):
		summary["skipped"].append({"field": "docstatus", "reason": "submitted_or_cancelled"})
		return summary

	settings = get_branch_default_application_settings()
	if not settings["enabled"]:
		summary["skipped"].append({"field": "settings", "reason": "branch_default_application_disabled"})
		return summary

	defaults = resolve_retailedge_operational_defaults(
		company=getattr(doc, "company", None),
		branch=getattr(doc, "branch", None),
		user=_get_context_user(doc),
		pos_profile=getattr(doc, "pos_profile", None),
		warehouse=_get_context_warehouse(doc),
	)
	summary["messages"].extend(defaults.get("messages") or [])
	if not defaults.get("branch"):
		message = "Branch defaults were not applied because branch could not be resolved safely."
		_set_resolution_note(doc, message)
		summary["messages"].append(message)
		summary["skipped"].append({"field": "branch", "reason": "branch_missing_or_ambiguous"})
		return summary

	doctype = doc.doctype
	if doctype == "Material Request":
		_apply_material_request_defaults(doc, defaults, settings, summary, overwrite=overwrite)
	elif doctype == "Stock Entry":
		_apply_stock_entry_defaults(doc, defaults, settings, summary, overwrite=overwrite)
	elif doctype in PURCHASE_DOCTYPES:
		_apply_purchase_defaults(doc, defaults, settings, summary, overwrite=overwrite)
	elif doctype in SALES_DOCTYPES:
		_apply_sales_defaults(doc, defaults, settings, summary, overwrite=overwrite)
	elif doctype == "RetailEdge Cashier Expense":
		_apply_cashier_expense_defaults(doc, defaults, settings, summary, overwrite=overwrite)
	elif doctype == "RetailEdge Daily Sales Audit":
		_apply_daily_sales_audit_defaults(doc, defaults, settings, summary, overwrite=overwrite)
	return summary


def preview_branch_defaults_for_doc(doctype, name=None, values=None):
	if not doctype:
		frappe.throw("DocType is required.")
	doc = _build_preview_doc(doctype=doctype, name=name, values=values)
	before = _snapshot_branch_default_fields(doc)
	summary = apply_branch_profile_defaults_to_doc(doc, overwrite=False)
	after = _snapshot_branch_default_fields(doc)
	return {
		"doctype": doctype,
		"name": getattr(doc, "name", None),
		"summary": summary,
		"changes": _diff_snapshots(before, after),
	}


def assert_can_preview_branch_defaults():
	user_roles = set(frappe.get_roles(frappe.session.user))
	if user_roles.intersection(DEFAULT_APPLICATION_MANAGER_ROLES):
		return
	frappe.throw(
		"You do not have permission to preview RetailEdge branch defaults.",
		frappe.PermissionError,
	)


def _apply_material_request_defaults(doc, defaults, settings, summary, overwrite=False):
	if settings["apply_warehouse"]:
		target_default = defaults.get("default_target_warehouse") or defaults.get("default_warehouse")
		_apply_doc_field(doc, "target_warehouse", target_default, summary, overwrite=overwrite)
		_apply_doc_field(doc, "set_warehouse", target_default, summary, overwrite=overwrite)
		row_default = getattr(doc, "target_warehouse", None) or getattr(doc, "set_warehouse", None)
		_apply_child_field(doc, "items", "warehouse", row_default, summary, overwrite=overwrite)


def _apply_stock_entry_defaults(doc, defaults, settings, summary, overwrite=False):
	if not settings["apply_warehouse"]:
		return
	source_default = defaults.get("default_source_warehouse")
	target_default = defaults.get("default_target_warehouse")
	_apply_doc_field(doc, "from_warehouse", source_default, summary, overwrite=overwrite)
	_apply_doc_field(doc, "source_warehouse", source_default, summary, overwrite=overwrite)
	_apply_doc_field(doc, "to_warehouse", target_default, summary, overwrite=overwrite)
	_apply_doc_field(doc, "target_warehouse", target_default, summary, overwrite=overwrite)
	_apply_child_field(
		doc,
		"items",
		"s_warehouse",
		getattr(doc, "from_warehouse", None) or getattr(doc, "source_warehouse", None),
		summary,
		overwrite=overwrite,
	)
	_apply_child_field(
		doc,
		"items",
		"t_warehouse",
		getattr(doc, "to_warehouse", None) or getattr(doc, "target_warehouse", None),
		summary,
		overwrite=overwrite,
	)


def _apply_purchase_defaults(doc, defaults, settings, summary, overwrite=False):
	if settings["apply_warehouse"]:
		warehouse_default = defaults.get("default_target_warehouse") or defaults.get("default_warehouse")
		_apply_doc_field(doc, "set_warehouse", warehouse_default, summary, overwrite=overwrite)
		_apply_child_field(
			doc,
			"items",
			"warehouse",
			getattr(doc, "set_warehouse", None),
			summary,
			overwrite=overwrite,
		)


def _apply_sales_defaults(doc, defaults, settings, summary, overwrite=False):
	if settings["apply_warehouse"]:
		warehouse_default = defaults.get("default_source_warehouse") or defaults.get("default_warehouse")
		_apply_doc_field(doc, "set_warehouse", warehouse_default, summary, overwrite=overwrite)
		_apply_child_field(
			doc,
			"items",
			"warehouse",
			getattr(doc, "set_warehouse", None),
			summary,
			overwrite=overwrite,
		)
	if settings["apply_cost_center"]:
		cost_center_default = defaults.get("default_sales_cost_center") or defaults.get("default_cost_center")
		_apply_doc_field(doc, "cost_center", cost_center_default, summary, overwrite=overwrite)
		_apply_child_field(
			doc,
			"items",
			"cost_center",
			getattr(doc, "cost_center", None),
			summary,
			overwrite=overwrite,
		)


def _apply_cashier_expense_defaults(doc, defaults, settings, summary, overwrite=False):
	if settings["apply_accounts"] and not getattr(doc, "_cashier_context", None):
		account_default = defaults.get("default_cash_account")
		_apply_doc_field(doc, "payment_account", account_default, summary, overwrite=overwrite)
	if settings["apply_cost_center"]:
		cost_center_default = defaults.get("default_expense_cost_center") or defaults.get("default_cost_center")
		_apply_doc_field(doc, "cost_center", cost_center_default, summary, overwrite=overwrite)
	if settings["apply_pos_profile"] and not getattr(doc, "linked_pos_opening_shift", None):
		_apply_doc_field(doc, "pos_profile", defaults.get("default_pos_profile"), summary, overwrite=overwrite)


def _apply_daily_sales_audit_defaults(doc, defaults, settings, summary, overwrite=False):
	if settings["apply_pos_profile"] and getattr(doc, "branch", None):
		_apply_doc_field(doc, "pos_profile", defaults.get("default_pos_profile"), summary, overwrite=overwrite)


def _apply_doc_field(doc, fieldname, value, summary, overwrite=False):
	if not value:
		summary["skipped"].append({"field": fieldname, "reason": "no_default_value"})
		return
	if not has_field(doc.doctype, fieldname):
		summary["skipped"].append({"field": fieldname, "reason": "field_missing"})
		return
	current = getattr(doc, fieldname, None)
	if current not in (None, "") and not overwrite:
		summary["skipped"].append({"field": fieldname, "reason": "existing_value_preserved"})
		return
	if current == value:
		summary["skipped"].append({"field": fieldname, "reason": "already_matches_default"})
		return
	setattr(doc, fieldname, value)
	summary["applied"].append({"field": fieldname, "value": value})


def _apply_child_field(doc, table_field, fieldname, value, summary, overwrite=False):
	if not value or not hasattr(doc, table_field):
		return
	for index, row in enumerate(getattr(doc, table_field, []) or [], start=1):
		if not hasattr(row, fieldname):
			continue
		current = getattr(row, fieldname, None)
		if current not in (None, "") and not overwrite:
			summary["skipped"].append(
				{"field": f"{table_field}[{index}].{fieldname}", "reason": "existing_value_preserved"}
			)
			continue
		if current == value:
			continue
		setattr(row, fieldname, value)
		summary["applied"].append({"field": f"{table_field}[{index}].{fieldname}", "value": value})


def _set_resolution_note(doc, message):
	if has_field(doc.doctype, "retailedge_branch_resolution_note"):
		current = getattr(doc, "retailedge_branch_resolution_note", None)
		if not current:
			doc.retailedge_branch_resolution_note = message


def _get_context_user(doc):
	return getattr(doc, "cashier", None) or getattr(doc, "owner", None) or frappe.session.user


def _get_context_warehouse(doc):
	for fieldname in WAREHOUSE_CONTEXT_FIELDS:
		value = getattr(doc, fieldname, None)
		if value:
			return value
	return None


def _build_preview_doc(doctype, name=None, values=None):
	if name:
		doc = frappe.get_doc(doctype, name)
		return frappe.get_doc(doc.as_dict())
	data = frappe.parse_json(values) if values else {}
	data = dict(data or {})
	data["doctype"] = doctype
	return frappe.get_doc(data)


def _snapshot_branch_default_fields(doc):
	fields = {"docstatus": getattr(doc, "docstatus", 0)}
	for fieldname in (
		"target_warehouse",
		"set_warehouse",
		"from_warehouse",
		"source_warehouse",
		"to_warehouse",
		"cost_center",
		"payment_account",
		"pos_profile",
		"retailedge_branch_resolution_note",
	):
		if hasattr(doc, fieldname):
			fields[fieldname] = getattr(doc, fieldname, None)
	for table_field in ("items",):
		if hasattr(doc, table_field):
			fields[table_field] = []
			for row in getattr(doc, table_field, []) or []:
				fields[table_field].append(
					{
						key: getattr(row, key, None)
						for key in ("warehouse", "s_warehouse", "t_warehouse", "cost_center")
						if hasattr(row, key)
					}
				)
	return fields


def _diff_snapshots(before, after):
	changes = {}
	for key, value in after.items():
		if before.get(key) != value:
			changes[key] = value
	return changes


def _get_settings_doc():
	try:
		return get_retailedge_settings()
	except Exception:
		return frappe._dict()
