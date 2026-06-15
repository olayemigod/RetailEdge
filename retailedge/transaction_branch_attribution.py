from __future__ import annotations

from typing import Iterable

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import now_datetime

from retailedge.branch_context import (
	BRANCH_FIELD_CANDIDATES,
	CASHIER_FIELD_CANDIDATES,
	OPENING_SHIFT_LINK_CANDIDATES,
	POS_PROFILE_FIELD_CANDIDATES,
	get_first_existing_field,
	has_doctype,
	has_field,
	resolve_branch_from_warehouse,
	resolve_retailedge_branch_context,
	resolve_retailedge_operational_defaults,
)


TARGET_DOCTYPE_ORDER = [
	"Sales Invoice",
	"POS Invoice",
	"Sales Order",
	"Delivery Note",
	"Quotation",
	"Payment Entry",
	"Payment Request",
	"Bank Transaction",
	"Material Request",
	"Stock Entry",
	"Stock Reconciliation",
	"Pick List",
	"Packing Slip",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
	"Supplier Quotation",
	"Request for Quotation",
	"POS Opening Shift",
	"POS Closing Shift",
	"POS Profile",
]

MOVEMENT_DOCTYPES = {
	"Material Request",
	"Stock Entry",
	"Stock Reconciliation",
	"Purchase Receipt",
	"Delivery Note",
}

WAREHOUSE_FIELD_CANDIDATES = [
	"warehouse",
	"set_warehouse",
	"default_warehouse",
	"from_warehouse",
	"source_warehouse",
	"to_warehouse",
	"target_warehouse",
]
ITEM_WAREHOUSE_FIELD_CANDIDATES = ["warehouse", "set_warehouse"]
ITEM_SOURCE_WAREHOUSE_FIELDS = ["s_warehouse", "source_warehouse", "from_warehouse"]
ITEM_TARGET_WAREHOUSE_FIELDS = ["t_warehouse", "target_warehouse", "to_warehouse"]
LINKED_SALES_FIELDS = ["sales_order", "against_sales_order"]
LINKED_SALES_INVOICE_FIELDS = ["sales_invoice", "against_sales_invoice"]
LINKED_PURCHASE_FIELDS = ["purchase_order", "material_request", "purchase_receipt"]
LINKED_PURCHASE_INVOICE_FIELDS = ["purchase_receipt", "purchase_order"]
PAYMENT_REFERENCE_DOCTYPES = {"Sales Invoice", "Purchase Invoice", "Sales Order", "Purchase Order"}


def get_branch_attribution_target_doctypes():
	cached = getattr(frappe.local, "retailedge_branch_attr_target_doctypes", None)
	if cached is not None:
		return cached
	cached = [doctype for doctype in TARGET_DOCTYPE_ORDER if has_doctype(doctype)]
	frappe.local.retailedge_branch_attr_target_doctypes = cached
	return cached


def ensure_transaction_branch_custom_fields():
	custom_fields = {}
	for doctype in get_branch_attribution_target_doctypes():
		field_defs = _get_field_defs_for_doctype(doctype)
		if field_defs:
			custom_fields[doctype] = field_defs
	if custom_fields:
		create_custom_fields(custom_fields, ignore_validate=True, update=True)
	return custom_fields


def resolve_transaction_branch(doc):
	if not getattr(doc, "doctype", None):
		return _new_resolution(note="Unsupported document for RetailEdge transaction branch attribution.")

	resolution = _new_resolution()
	explicit_branch = _get_explicit_transaction_branch(doc)
	if explicit_branch:
		resolution["branch"] = explicit_branch
		resolution["source"] = f"{doc.doctype}.explicit_branch"
		resolution["note"] = "Resolved from explicit transaction branch."

	doctype = doc.doctype
	if doctype == "Payment Entry":
		_resolve_payment_entry_branch(doc, resolution)
	elif doctype == "Material Request":
		_resolve_material_request_branch(doc, resolution)
	elif doctype == "Stock Entry":
		_resolve_stock_entry_branch(doc, resolution)
	elif doctype == "Purchase Receipt":
		_resolve_purchase_receipt_branch(doc, resolution)
	elif doctype == "Purchase Invoice":
		_resolve_purchase_invoice_branch(doc, resolution)
	elif doctype == "Delivery Note":
		_resolve_delivery_note_branch(doc, resolution)
	elif doctype == "Purchase Order":
		_resolve_purchase_order_branch(doc, resolution)
	elif doctype in {"Sales Invoice", "POS Invoice", "Sales Order", "Quotation"}:
		_resolve_sales_side_branch(doc, resolution)
	elif doctype in {"Stock Reconciliation", "Pick List", "Packing Slip"}:
		_resolve_warehouse_driven_branch(doc, resolution)
	elif doctype in {"POS Opening Shift", "POS Closing Shift", "POS Profile"}:
		_resolve_pos_context_branch(doc, resolution)
	else:
		_resolve_generic_transaction_branch(doc, resolution)

	resolution["resolved_on"] = now_datetime()
	return resolution


def apply_transaction_branch_attribution(doc, method=None, overwrite=False):
	if getattr(doc, "doctype", None) not in TARGET_DOCTYPE_ORDER:
		return _new_resolution(note="RetailEdge transaction branch attribution is not enabled for this DocType.")

	if not has_field(doc.doctype, "retailedge_branch"):
		return _new_resolution(note="RetailEdge attribution fields are not available on this DocType.")

	current_branch = getattr(doc, "retailedge_branch", None)
	if current_branch and not overwrite:
		return {
			"branch": current_branch,
			"source_branch": getattr(doc, "retailedge_source_branch", None),
			"target_branch": getattr(doc, "retailedge_target_branch", None),
			"warehouse_branch": getattr(doc, "retailedge_warehouse_branch", None),
			"source": getattr(doc, "retailedge_branch_source", None),
			"resolved_on": getattr(doc, "retailedge_branch_resolved_on", None),
			"note": getattr(doc, "retailedge_branch_resolution_note", None),
			"messages": ["RetailEdge branch attribution already exists on this document."],
		}

	resolution = resolve_transaction_branch(doc)
	_set_attr_if_field(doc, "retailedge_branch", resolution.get("branch"))
	_set_attr_if_field(doc, "retailedge_source_branch", resolution.get("source_branch"))
	_set_attr_if_field(doc, "retailedge_target_branch", resolution.get("target_branch"))
	_set_attr_if_field(doc, "retailedge_warehouse_branch", resolution.get("warehouse_branch"))
	_set_attr_if_field(doc, "retailedge_branch_source", resolution.get("source"))
	_set_attr_if_field(doc, "retailedge_branch_resolved_on", resolution.get("resolved_on"))
	_set_attr_if_field(doc, "retailedge_branch_resolution_note", resolution.get("note"))
	return resolution


def refresh_transaction_branch_attribution(doctype, name, overwrite=False):
	if not has_doctype(doctype):
		frappe.throw(f"{doctype} is not available on this site.")
	doc = frappe.get_doc(doctype, name)
	before = _snapshot_retailedge_attribution(doc)
	resolution = apply_transaction_branch_attribution(doc, overwrite=overwrite)
	after = _snapshot_retailedge_attribution(doc)
	if before != after:
		doc.save(ignore_permissions=True)
	return resolution


def preview_transaction_branch_backfill(doctype=None, filters=None, limit=500):
	return run_transaction_branch_backfill(
		doctype=doctype,
		filters=filters,
		limit=limit,
		overwrite=False,
		dry_run=True,
	)


def run_transaction_branch_backfill(
	doctype=None,
	filters=None,
	limit=500,
	overwrite=False,
	dry_run=True,
	commit_every=100,
):
	target_doctypes = _get_backfill_target_doctypes(doctype)
	filters = _coerce_filters(filters)
	dry_run = bool(dry_run)
	overwrite = bool(overwrite)
	commit_every = max(int(commit_every or 100), 1)
	summary = _new_backfill_summary(doctype=doctype, dry_run=dry_run)
	pending_commits = 0

	for target_doctype in target_doctypes:
		doctype_summary = _new_backfill_doctype_summary()
		summary["by_doctype"][target_doctype] = doctype_summary
		if not has_doctype(target_doctype) or not has_field(target_doctype, "retailedge_branch"):
			continue

		query_filters = dict(filters)
		if not overwrite:
			query_filters.setdefault("retailedge_branch", ["in", ["", None]])

		rows = frappe.get_all(
			target_doctype,
			filters=query_filters,
			fields=["name"],
			order_by="modified desc",
			limit_page_length=int(limit or 500),
		)
		for row in rows:
			summary["checked"] += 1
			doctype_summary["checked"] += 1
			try:
				doc = frappe.get_doc(target_doctype, row.name)
				existing_branch = getattr(doc, "retailedge_branch", None) if has_field(target_doctype, "retailedge_branch") else None
				if existing_branch and not overwrite:
					item = _build_backfill_item(target_doctype, row.name, _new_resolution(), action="skipped", note="Existing RetailEdge branch preserved.")
					summary["skipped"] += 1
					doctype_summary["skipped"] += 1
					summary["items"].append(item)
					continue

				resolution = resolve_transaction_branch(doc)
				status = _classify_resolution(resolution)
				if status == "resolved":
					summary["resolved"] += 1
					doctype_summary["resolved"] += 1
				elif status == "ambiguous":
					summary["ambiguous"] += 1
					doctype_summary["ambiguous"] += 1
				else:
					summary["unresolved"] += 1
					doctype_summary["unresolved"] += 1

				values = _build_attribution_update_values(doc, resolution, overwrite=overwrite)
				would_update = _would_update_attribution(doc, values)
				action = "would_update" if dry_run and would_update else status

				if not dry_run and would_update:
					frappe.db.set_value(target_doctype, row.name, values, update_modified=False)
					pending_commits += 1
					summary["updated"] += 1
					doctype_summary["updated"] += 1
					action = "updated"
					if pending_commits >= commit_every:
						frappe.db.commit()
						pending_commits = 0
				elif not dry_run and not would_update:
					summary["skipped"] += 1
					doctype_summary["skipped"] += 1
					action = "skipped"

				summary["items"].append(_build_backfill_item(target_doctype, row.name, resolution, action=action))
			except Exception as exc:
				summary["errors"] += 1
				doctype_summary["errors"] += 1
				summary["items"].append(
					{
						"doctype": target_doctype,
						"name": row.name,
						"branch": None,
						"source_branch": None,
						"target_branch": None,
						"warehouse_branch": None,
						"source": None,
						"note": _safe_error_message(exc),
						"action": "error",
					}
				)

	if not dry_run and pending_commits:
		frappe.db.commit()
	return summary


def validate_sales_invoice_with_branch_attribution(doc, method=None):
	from retailedge.events.sales_invoice import validate_sales_invoice

	validate_sales_invoice(doc, method=method)
	return apply_transaction_branch_attribution(doc, method=method, overwrite=False)


def _get_field_defs_for_doctype(doctype):
	layout_insert_after = _get_insert_after(doctype)
	field_defs = [
		{
			"fieldname": "retailedge_branch_attribution_section",
			"label": "RetailEdge Branch Metadata",
			"fieldtype": "Section Break",
			"hidden": 1,
			"collapsible": 0,
			"read_only": 1,
			"insert_after": layout_insert_after,
		}
	]
	field_defs.append(
		{
			"fieldname": "retailedge_branch",
			"label": "RetailEdge Branch",
			"fieldtype": "Link",
			"options": "Branch",
			"read_only": 1,
			"in_standard_filter": 1,
			"insert_after": layout_insert_after,
			"description": "Branch attributed by RetailEdge for filtering/reporting.",
		}
	)
	insert_after = "retailedge_branch"
	for fieldname, label, fieldtype in (
		("retailedge_branch_source", "RetailEdge Branch Source", "Data"),
		("retailedge_branch_resolved_on", "RetailEdge Branch Resolved On", "Datetime"),
		("retailedge_branch_resolution_note", "RetailEdge Branch Resolution Note", "Small Text"),
	):
		field_defs.append(_hidden_attribution_field(fieldname, label, fieldtype, insert_after=insert_after))
		insert_after = fieldname

	if doctype in MOVEMENT_DOCTYPES:
		for fieldname, label in (
			("retailedge_source_branch", "RetailEdge Source Branch"),
			("retailedge_target_branch", "RetailEdge Target Branch"),
			("retailedge_warehouse_branch", "RetailEdge Warehouse Branch"),
		):
			field_defs.append(
				_hidden_attribution_field(
					fieldname,
					label,
					"Link",
					insert_after=insert_after,
					extra={"options": "Branch", "in_standard_filter": 1},
				)
			)
			insert_after = fieldname
	return field_defs


def _hidden_attribution_field(fieldname, label, fieldtype, insert_after=None, extra=None):
	field_def = {
		"fieldname": fieldname,
		"label": label,
		"fieldtype": fieldtype,
		"hidden": 1,
		"read_only": 1,
		"no_copy": 1,
		"print_hide": 1,
		"insert_after": insert_after,
	}
	field_def.update(extra or {})
	return field_def


def _new_resolution(note=None):
	return {
		"branch": None,
		"source_branch": None,
		"target_branch": None,
		"warehouse_branch": None,
		"source": None,
		"resolved_on": None,
		"note": note,
		"messages": [],
	}


def _new_backfill_summary(doctype=None, dry_run=True):
	return {
		"dry_run": dry_run,
		"doctype": doctype,
		"checked": 0,
		"resolved": 0,
		"updated": 0,
		"ambiguous": 0,
		"unresolved": 0,
		"skipped": 0,
		"errors": 0,
		"by_doctype": {},
		"items": [],
	}


def _new_backfill_doctype_summary():
	return {
		"checked": 0,
		"updated": 0,
		"resolved": 0,
		"ambiguous": 0,
		"unresolved": 0,
		"skipped": 0,
		"errors": 0,
	}


def _get_backfill_target_doctypes(doctype=None):
	if doctype:
		return [doctype] if doctype in TARGET_DOCTYPE_ORDER else []
	return get_branch_attribution_target_doctypes()


def _classify_resolution(resolution):
	if resolution.get("branch") or resolution.get("source_branch") or resolution.get("target_branch") or resolution.get("warehouse_branch"):
		if _is_ambiguous_resolution(resolution) and not resolution.get("branch"):
			return "ambiguous"
		return "resolved"
	if _is_ambiguous_resolution(resolution):
		return "ambiguous"
	return "unresolved"


def _build_attribution_update_values(doc, resolution, overwrite=False):
	values = {}
	has_meaningful_resolution = any(
		resolution.get(key) for key in ("branch", "source_branch", "target_branch", "warehouse_branch")
	) or bool(resolution.get("note"))
	for fieldname, key in (
		("retailedge_branch", "branch"),
		("retailedge_source_branch", "source_branch"),
		("retailedge_target_branch", "target_branch"),
		("retailedge_warehouse_branch", "warehouse_branch"),
		("retailedge_branch_source", "source"),
		("retailedge_branch_resolved_on", "resolved_on"),
		("retailedge_branch_resolution_note", "note"),
	):
		if not has_field(doc.doctype, fieldname):
			continue
		if fieldname == "retailedge_branch" and not overwrite and getattr(doc, fieldname, None):
			continue
		if fieldname == "retailedge_branch_resolved_on" and not has_meaningful_resolution:
			continue
		if fieldname == "retailedge_branch_source" and not has_meaningful_resolution:
			continue
		if fieldname == "retailedge_branch_resolution_note" and not resolution.get("note"):
			continue
		values[fieldname] = resolution.get(key)
	return values


def _would_update_attribution(doc, values):
	for fieldname, value in values.items():
		if getattr(doc, fieldname, None) != value:
			return True
	return False


def _build_backfill_item(doctype, name, resolution, action, note=None):
	return {
		"doctype": doctype,
		"name": name,
		"branch": resolution.get("branch"),
		"source_branch": resolution.get("source_branch"),
		"target_branch": resolution.get("target_branch"),
		"warehouse_branch": resolution.get("warehouse_branch"),
		"source": resolution.get("source"),
		"note": note if note is not None else resolution.get("note"),
		"action": action,
	}


def _safe_error_message(exc):
	message = str(exc) or exc.__class__.__name__
	return message[:300]


def _resolve_generic_transaction_branch(doc, resolution):
	context = _resolve_branch_context_for_doc(doc)
	_apply_context_branch(resolution, context)
	if not resolution.get("note") and context.get("messages"):
		resolution["note"] = " ".join(context.get("messages"))


def _resolve_sales_side_branch(doc, resolution):
	context = _resolve_branch_context_for_doc(doc)
	_apply_context_branch(resolution, context)
	if resolution.get("branch"):
		return

	warehouse_branch, warehouse_note = _resolve_single_branch_from_warehouses(
		_collect_doc_and_item_warehouses(doc)
	)
	if warehouse_branch:
		resolution["branch"] = warehouse_branch
		resolution["warehouse_branch"] = warehouse_branch
		resolution["source"] = "Warehouse Branch"
	elif warehouse_note:
		resolution["note"] = warehouse_note


def _resolve_payment_entry_branch(doc, resolution):
	reference_branches = []
	for row in getattr(doc, "references", []) or []:
		reference_doctype = getattr(row, "reference_doctype", None)
		reference_name = getattr(row, "reference_name", None)
		if not reference_doctype or not reference_name or reference_doctype not in PAYMENT_REFERENCE_DOCTYPES:
			continue
		branch_info = _get_transaction_or_linked_branch(reference_doctype, reference_name)
		if branch_info.get("branch"):
			reference_branches.append(branch_info.get("branch"))
		resolution["messages"].extend(branch_info.get("messages") or [])

	unique_branches = _unique(reference_branches)
	if len(unique_branches) == 1:
		resolution["branch"] = unique_branches[0]
		resolution["source"] = "Payment Entry Reference"
		return
	if len(unique_branches) > 1:
		resolution["note"] = "Multiple referenced document branches detected; manual review required."
		resolution["messages"].append(resolution["note"])
		return

	context = _resolve_branch_context_for_doc(doc)
	_apply_context_branch(resolution, context)


def _resolve_material_request_branch(doc, resolution):
	context = _resolve_branch_context_for_doc(doc)
	_apply_context_branch(resolution, context)
	warehouse_branch, note = _resolve_single_branch_from_warehouses(_collect_doc_and_item_warehouses(doc))
	if warehouse_branch:
		resolution["warehouse_branch"] = warehouse_branch
		if not resolution.get("branch"):
			resolution["branch"] = warehouse_branch
			resolution["source"] = "Warehouse Branch"
	elif note:
		resolution["note"] = note


def _resolve_stock_entry_branch(doc, resolution):
	source_branch, source_note = _resolve_single_branch_from_warehouses(
		_collect_source_warehouses(doc)
	)
	target_branch, target_note = _resolve_single_branch_from_warehouses(
		_collect_target_warehouses(doc)
	)
	resolution["source_branch"] = source_branch
	resolution["target_branch"] = target_branch
	if source_branch and target_branch and source_branch == target_branch:
		resolution["branch"] = source_branch
		resolution["source"] = "Stock Entry Warehouse Branch"
	elif source_branch or target_branch:
		resolution["note"] = "Cross-branch stock movement; branch not auto-attributed."
		resolution["messages"].append(resolution["note"])
		if source_note:
			resolution["messages"].append(source_note)
		if target_note:
			resolution["messages"].append(target_note)
	else:
		context = _resolve_branch_context_for_doc(doc)
		_apply_context_branch(resolution, context)
		if source_note or target_note:
			resolution["note"] = source_note or target_note


def _resolve_purchase_order_branch(doc, resolution):
	linked_branches = _linked_branches_from_children(doc, ["material_request"], "Material Request")
	if len(linked_branches) == 1:
		resolution["branch"] = linked_branches[0]
		resolution["source"] = "Purchase Order Material Request"
		return
	if len(linked_branches) > 1:
		resolution["note"] = "Multiple branches detected; manual review required."
		return
	context = _resolve_branch_context_for_doc(doc)
	_apply_context_branch(resolution, context)
	warehouse_branch, note = _resolve_single_branch_from_warehouses(_collect_doc_and_item_warehouses(doc))
	if warehouse_branch and not resolution.get("branch"):
		resolution["branch"] = warehouse_branch
		resolution["warehouse_branch"] = warehouse_branch
		resolution["source"] = "Warehouse Branch"
	elif note:
		resolution["note"] = note


def _resolve_purchase_receipt_branch(doc, resolution):
	linked_branches = _linked_branches_from_children(doc, LINKED_PURCHASE_FIELDS, None)
	if len(linked_branches) == 1:
		resolution["branch"] = linked_branches[0]
		resolution["source"] = "Purchase Receipt Linked Document"
		return
	if len(linked_branches) > 1:
		resolution["note"] = "Multiple branches detected; manual review required."
		return
	warehouse_branch, note = _resolve_single_branch_from_warehouses(_collect_doc_and_item_warehouses(doc))
	if warehouse_branch:
		resolution["branch"] = warehouse_branch
		resolution["warehouse_branch"] = warehouse_branch
		resolution["source"] = "Purchase Receipt Warehouse Branch"
	elif note:
		resolution["note"] = note
	else:
		context = _resolve_branch_context_for_doc(doc)
		_apply_context_branch(resolution, context)


def _resolve_purchase_invoice_branch(doc, resolution):
	linked_branches = _linked_branches_from_children(doc, LINKED_PURCHASE_INVOICE_FIELDS, None)
	if len(linked_branches) == 1:
		resolution["branch"] = linked_branches[0]
		resolution["source"] = "Purchase Invoice Linked Document"
		return
	if len(linked_branches) > 1:
		resolution["note"] = "Multiple branches detected; manual review required."
		return
	warehouse_branch, note = _resolve_single_branch_from_warehouses(_collect_doc_and_item_warehouses(doc))
	if warehouse_branch:
		resolution["branch"] = warehouse_branch
		resolution["warehouse_branch"] = warehouse_branch
		resolution["source"] = "Purchase Invoice Warehouse Branch"
	elif note:
		resolution["note"] = note
	else:
		context = _resolve_branch_context_for_doc(doc)
		_apply_context_branch(resolution, context)


def _resolve_delivery_note_branch(doc, resolution):
	linked_branches = _linked_branches_from_children(doc, LINKED_SALES_FIELDS, "Sales Order")
	if len(linked_branches) == 1:
		resolution["branch"] = linked_branches[0]
		resolution["source"] = "Delivery Note Sales Order"
		return
	if len(linked_branches) > 1:
		resolution["note"] = "Multiple branches detected; manual review required."
		return
	warehouse_branch, note = _resolve_single_branch_from_warehouses(_collect_doc_and_item_warehouses(doc))
	if warehouse_branch:
		resolution["branch"] = warehouse_branch
		resolution["warehouse_branch"] = warehouse_branch
		resolution["source"] = "Delivery Note Warehouse Branch"
	elif note:
		resolution["note"] = note
	else:
		context = _resolve_branch_context_for_doc(doc)
		_apply_context_branch(resolution, context)


def _resolve_warehouse_driven_branch(doc, resolution):
	warehouse_branch, note = _resolve_single_branch_from_warehouses(_collect_doc_and_item_warehouses(doc))
	if warehouse_branch:
		resolution["branch"] = warehouse_branch
		resolution["warehouse_branch"] = warehouse_branch
		resolution["source"] = "Warehouse Branch"
	elif note:
		resolution["note"] = note
	else:
		context = _resolve_branch_context_for_doc(doc)
		_apply_context_branch(resolution, context)


def _resolve_pos_context_branch(doc, resolution):
	context = _resolve_branch_context_for_doc(doc)
	_apply_context_branch(resolution, context)
	if resolution.get("branch"):
		return
	defaults = resolve_retailedge_operational_defaults(
		company=getattr(doc, "company", None),
		pos_profile=_get_doc_value(doc, POS_PROFILE_FIELD_CANDIDATES),
		user=_get_doc_value(doc, CASHIER_FIELD_CANDIDATES),
	)
	if defaults.get("branch"):
		resolution["branch"] = defaults["branch"]
		resolution["source"] = defaults.get("source") or "RetailEdge Branch Profile"
		resolution["note"] = "Resolved from RetailEdge operational defaults."


def _apply_context_branch(resolution, context):
	if context.get("branch") and not resolution.get("branch"):
		resolution["branch"] = context.get("branch")
		resolution["source"] = context.get("source")
	if context.get("messages") and not resolution.get("note"):
		resolution["note"] = " ".join(context.get("messages"))
	resolution["messages"].extend(context.get("messages") or [])


def _resolve_branch_context_for_doc(doc):
	user_value = _get_doc_value(doc, CASHIER_FIELD_CANDIDATES) or getattr(doc, "owner", None)
	return resolve_retailedge_branch_context(
		doc=doc,
		company=getattr(doc, "company", None),
		branch=_get_explicit_transaction_branch(doc),
		pos_profile=_get_doc_value(doc, POS_PROFILE_FIELD_CANDIDATES),
		cashier=_get_doc_value(doc, CASHIER_FIELD_CANDIDATES),
		pos_opening_shift=_get_opening_shift_value(doc),
		pos_closing_shift=_get_closing_shift_value(doc),
		warehouse=_get_doc_value(doc, WAREHOUSE_FIELD_CANDIDATES),
		user=user_value,
	)


def _get_transaction_or_linked_branch(doctype, name):
	result = {"branch": None, "messages": []}
	if not has_doctype(doctype):
		return result
	if has_field(doctype, "retailedge_branch"):
		branch = frappe.db.get_value(doctype, name, "retailedge_branch")
		if branch:
			result["branch"] = branch
			return result
	doc = frappe.get_doc(doctype, name)
	context = resolve_retailedge_branch_context(
		doc=doc,
		company=getattr(doc, "company", None),
		branch=_get_explicit_transaction_branch(doc),
		pos_profile=_get_doc_value(doc, POS_PROFILE_FIELD_CANDIDATES),
		cashier=_get_doc_value(doc, CASHIER_FIELD_CANDIDATES),
		pos_opening_shift=_get_opening_shift_value(doc),
		pos_closing_shift=_get_closing_shift_value(doc),
		warehouse=_get_doc_value(doc, WAREHOUSE_FIELD_CANDIDATES),
		user=_get_doc_value(doc, CASHIER_FIELD_CANDIDATES) or getattr(doc, "owner", None),
	)
	result["branch"] = context.get("branch")
	result["messages"] = context.get("messages") or []
	return result


def _linked_branches_from_children(doc, fieldnames, default_doctype):
	branches = []
	for row in getattr(doc, "items", []) or []:
		for fieldname in fieldnames:
			link_name = getattr(row, fieldname, None)
			if not link_name:
				continue
			link_doctype = default_doctype or _doctype_for_link_field(fieldname)
			if not link_doctype:
				continue
			branch_info = _get_transaction_or_linked_branch(link_doctype, link_name)
			if branch_info.get("branch"):
				branches.append(branch_info["branch"])
	return _unique(branches)


def _doctype_for_link_field(fieldname):
	return {
		"material_request": "Material Request",
		"purchase_order": "Purchase Order",
		"purchase_receipt": "Purchase Receipt",
		"sales_order": "Sales Order",
		"against_sales_order": "Sales Order",
		"sales_invoice": "Sales Invoice",
		"against_sales_invoice": "Sales Invoice",
	}.get(fieldname)


def _collect_doc_and_item_warehouses(doc):
	warehouses = []
	warehouses.extend(_values_from_fields(doc, WAREHOUSE_FIELD_CANDIDATES))
	for row in getattr(doc, "items", []) or []:
		warehouses.extend(_values_from_fields(row, ITEM_WAREHOUSE_FIELD_CANDIDATES))
	return _unique(warehouses)


def _collect_source_warehouses(doc):
	warehouses = []
	warehouses.extend(_values_from_fields(doc, ["from_warehouse", "source_warehouse"]))
	for row in getattr(doc, "items", []) or []:
		warehouses.extend(_values_from_fields(row, ITEM_SOURCE_WAREHOUSE_FIELDS))
	return _unique(warehouses)


def _collect_target_warehouses(doc):
	warehouses = []
	warehouses.extend(_values_from_fields(doc, ["to_warehouse", "target_warehouse"]))
	for row in getattr(doc, "items", []) or []:
		warehouses.extend(_values_from_fields(row, ITEM_TARGET_WAREHOUSE_FIELDS))
	return _unique(warehouses)


def _resolve_single_branch_from_warehouses(warehouses: Iterable[str]):
	branches = []
	messages = []
	for warehouse in _unique(list(warehouses or [])):
		result = resolve_branch_from_warehouse(warehouse)
		if result.get("branch"):
			branches.append(result["branch"])
		messages.extend(result.get("messages") or [])
	unique_branches = _unique(branches)
	if len(unique_branches) == 1:
		return unique_branches[0], None
	if len(unique_branches) > 1:
		return None, "Multiple branches detected; manual review required."
	return None, "No warehouse branch could be resolved." if warehouses else None


def _get_explicit_transaction_branch(doc):
	for fieldname in ("branch", "set_branch", "service_branch", "retail_branch", "default_branch"):
		value = getattr(doc, fieldname, None)
		if value:
			return value
	return None


def _get_opening_shift_value(doc):
	return _get_doc_value(doc, ["posa_pos_opening_shift", "linked_pos_opening_shift", *OPENING_SHIFT_LINK_CANDIDATES])


def _get_closing_shift_value(doc):
	return _get_doc_value(doc, ["linked_pos_closing_shift", "pos_closing_shift"])


def _get_doc_value(doc, candidates):
	for fieldname in candidates:
		value = getattr(doc, fieldname, None)
		if value:
			return value
	return None


def _values_from_fields(doc, candidates):
	values = []
	for fieldname in candidates:
		value = getattr(doc, fieldname, None)
		if value:
			values.append(value)
	return values


def _get_insert_after(doctype):
	for candidate in (
		"branch",
		"company",
		"posting_date",
		"customer",
		"supplier",
		"title",
		"remarks",
	):
		if has_field(doctype, candidate):
			return candidate
	return None


def _set_attr_if_field(doc, fieldname, value):
	if has_field(doc.doctype, fieldname):
		setattr(doc, fieldname, value)


def _snapshot_retailedge_attribution(doc):
	data = {}
	for fieldname in (
		"retailedge_branch",
		"retailedge_source_branch",
		"retailedge_target_branch",
		"retailedge_warehouse_branch",
		"retailedge_branch_source",
		"retailedge_branch_resolved_on",
		"retailedge_branch_resolution_note",
	):
		if has_field(doc.doctype, fieldname):
			data[fieldname] = getattr(doc, fieldname, None)
	return data


def _unique(values):
	seen = set()
	result = []
	for value in values or []:
		if value and value not in seen:
			seen.add(value)
			result.append(value)
	return result


def _coerce_filters(filters):
	if not filters:
		return {}
	parsed = frappe.parse_json(filters) if isinstance(filters, str) else filters
	if isinstance(parsed, frappe._dict):
		return dict(parsed)
	return parsed if isinstance(parsed, dict) else {}


def _is_ambiguous_resolution(resolution):
	return bool(resolution.get("note") and "manual review required" in resolution.get("note", "").lower())
