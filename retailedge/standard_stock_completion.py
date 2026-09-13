from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime

from retailedge.branch_context import resolve_branch_from_warehouse
from retailedge.guided_stock_adjustment import (
	STOCK_RECONCILIATION_DOCTYPE,
	STOCK_RECONCILIATION_PURPOSE,
	_validate_branch_warehouse as _validate_adjustment_branch_warehouse,
)
from retailedge.guided_stock_transfer import (
	MATERIAL_TRANSFER,
	STOCK_ENTRY_DOCTYPE,
	_validate_branch_warehouse as _validate_transfer_branch_warehouse,
)
from retailedge.operating_context import get_operational_branch_scope, resolve_operational_branch
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness

SUPPORTED_DOCTYPES = {STOCK_ENTRY_DOCTYPE, STOCK_RECONCILIATION_DOCTYPE}
MAX_PREVIEW_ITEMS = 12
MAX_STANDARD_ITEMS = 50


def _clean(value: Any) -> str:
	return str(value or "").strip()


def _get_stock_document(doctype: str, name: str):
	doctype = _clean(doctype)
	name = _clean(name)
	if doctype not in SUPPORTED_DOCTYPES:
		frappe.throw(_("Unsupported standard stock completion document type."), frappe.ValidationError)
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name or "(blank)"))
	doc = frappe.get_doc(doctype, name)
	if not frappe.has_permission(doctype, "read", doc=doc):
		frappe.throw(_("You do not have permission to read {0} {1}.").format(doctype, name), frappe.PermissionError)
	return doc


def _lock_document(doctype: str, name: str) -> None:
	table = {
		STOCK_ENTRY_DOCTYPE: "tabStock Entry",
		STOCK_RECONCILIATION_DOCTYPE: "tabStock Reconciliation",
	}[doctype]
	frappe.db.sql(f"SELECT name FROM `{table}` WHERE name = %s FOR UPDATE", (_clean(name),))


def _assert_expected_modified(doc, expected_modified: str | None) -> str:
	expected_modified = _clean(expected_modified)
	if not expected_modified:
		frappe.throw(
			_("The reviewed stock document version is required. Refresh completion review."),
			frappe.TimestampMismatchError,
		)
	try:
		expected = get_datetime(expected_modified)
		current = get_datetime(doc.modified)
	except Exception:
		frappe.throw(_("Invalid reviewed stock document version."), frappe.ValidationError)
	if expected != current:
		frappe.throw(
			_("This stock document changed after it was reviewed. Refresh completion before continuing."),
			frappe.TimestampMismatchError,
		)
	return expected_modified


def _item_tracking(item_code: str) -> dict[str, int]:
	if not item_code:
		return {"has_serial_no": 0, "has_batch_no": 0}
	row = frappe.db.get_value("Item", item_code, ["has_serial_no", "has_batch_no"], as_dict=True)
	return {
		"has_serial_no": cint(row.get("has_serial_no")) if row else 0,
		"has_batch_no": cint(row.get("has_batch_no")) if row else 0,
	}


def _validate_company_and_scope(doc) -> tuple[str, dict[str, Any]]:
	company = _clean(doc.get("company"))
	if not company:
		frappe.throw(_("{0} {1} has no Company.").format(doc.doctype, doc.name))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have permission to use Company {0}.").format(company), frappe.PermissionError)
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	if scope.get("restricted") and not scope.get("allowed_branches"):
		frappe.throw(
			_("Your Branch operating access is not active for Company {0}.").format(company),
			frappe.PermissionError,
		)
	return company, scope


def _resolve_warehouse_branch(warehouse: str) -> str:
	result = resolve_branch_from_warehouse(warehouse) if warehouse else {}
	return _clean(result.get("branch"))


def _validate_warehouse_access(
	*,
	company: str,
	warehouse: str,
	stored_branch: str,
	scope: dict[str, Any],
	validator,
) -> str:
	warehouse = _clean(warehouse)
	if not warehouse or not frappe.db.exists("Warehouse", warehouse):
		frappe.throw(_("Warehouse {0} does not exist.").format(warehouse or "(blank)"))
	if not frappe.has_permission("Warehouse", "read", doc=warehouse):
		frappe.throw(_("You do not have permission to use Warehouse {0}.").format(warehouse), frappe.PermissionError)
	warehouse_company = _clean(frappe.db.get_value("Warehouse", warehouse, "company"))
	if warehouse_company and warehouse_company != company:
		frappe.throw(_("Warehouse {0} does not belong to Company {1}.").format(warehouse, company))

	branch = _clean(stored_branch) or _resolve_warehouse_branch(warehouse)
	if branch:
		branch = resolve_operational_branch(company, branch, user=frappe.session.user)["branch"]
		validator(
			branch=branch,
			warehouse=warehouse,
			company=company,
			user=frappe.session.user,
		)
	elif scope.get("restricted"):
		frappe.throw(
			_(
				"RetailEdge cannot prove the Branch scope for Warehouse {0}. "
				"Use Advanced ERPNext after correcting Warehouse/Branch setup."
			).format(warehouse),
			frappe.PermissionError,
		)
	return branch


def _base_blockers(doc) -> list[str]:
	blockers: list[str] = []
	if cint(doc.docstatus) != 0:
		blockers.append(_("Only draft stock documents can use standard EdgeSuite completion."))
	if _clean(doc.get("amended_from")):
		blockers.append(_("Amended stock documents require Advanced ERPNext review."))
	items = list(doc.get("items") or [])
	if not items:
		blockers.append(_("At least one stock item is required."))
	if len(items) > MAX_STANDARD_ITEMS:
		blockers.append(
			_("Stock documents with more than {0} rows require Advanced ERPNext review.").format(MAX_STANDARD_ITEMS)
		)
	return blockers


def _transfer_preview(doc, company: str, scope: dict[str, Any]) -> dict[str, Any]:
	blockers = _base_blockers(doc)
	if _clean(doc.get("purpose")) != MATERIAL_TRANSFER or _clean(doc.get("stock_entry_type")) not in {"", MATERIAL_TRANSFER}:
		blockers.append(_("Only standard Material Transfer Stock Entries can be completed here."))

	source_warehouses = {
		_clean(row.get("s_warehouse") or doc.get("from_warehouse"))
		for row in list(doc.get("items") or [])
		if _clean(row.get("s_warehouse") or doc.get("from_warehouse"))
	}
	target_warehouses = {
		_clean(row.get("t_warehouse") or doc.get("to_warehouse"))
		for row in list(doc.get("items") or [])
		if _clean(row.get("t_warehouse") or doc.get("to_warehouse"))
	}
	if len(source_warehouses) != 1 or len(target_warehouses) != 1:
		blockers.append(_("Standard completion requires one Source Warehouse and one Target Warehouse."))
	source_warehouse = next(iter(source_warehouses), _clean(doc.get("from_warehouse")))
	target_warehouse = next(iter(target_warehouses), _clean(doc.get("to_warehouse")))
	if not source_warehouse or not target_warehouse:
		blockers.append(_("Source Warehouse and Target Warehouse are required."))
	if source_warehouse and source_warehouse == target_warehouse:
		blockers.append(_("Source Warehouse and Target Warehouse must be different."))

	source_branch = ""
	target_branch = ""
	if source_warehouse:
		source_branch = _validate_warehouse_access(
			company=company,
			warehouse=source_warehouse,
			stored_branch=_clean(doc.get("retailedge_source_branch")),
			scope=scope,
			validator=_validate_transfer_branch_warehouse,
		)
	if target_warehouse:
		target_branch = _validate_warehouse_access(
			company=company,
			warehouse=target_warehouse,
			stored_branch=_clean(doc.get("retailedge_target_branch")),
			scope=scope,
			validator=_validate_transfer_branch_warehouse,
		)

	items: list[dict[str, Any]] = []
	for index, row in enumerate(list(doc.get("items") or []), start=1):
		item_code = _clean(row.get("item_code"))
		qty = flt(row.get("qty"))
		if not item_code:
			blockers.append(_("Item is missing on row {0}.").format(index))
		elif not frappe.has_permission("Item", "read", doc=item_code):
			frappe.throw(_("You do not have permission to use Item {0}.").format(item_code), frappe.PermissionError)
		else:
			tracking = _item_tracking(item_code)
			if tracking["has_serial_no"] or tracking["has_batch_no"]:
				blockers.append(
					_("Item {0} uses Serial No or Batch tracking and requires Advanced ERPNext.").format(item_code)
				)
		if qty <= 0:
			blockers.append(_("Quantity on row {0} must be greater than zero.").format(index))
		row_source = _clean(row.get("s_warehouse") or doc.get("from_warehouse"))
		row_target = _clean(row.get("t_warehouse") or doc.get("to_warehouse"))
		if source_warehouse and row_source != source_warehouse:
			blockers.append(_("Row {0} uses a different Source Warehouse.").format(index))
		if target_warehouse and row_target != target_warehouse:
			blockers.append(_("Row {0} uses a different Target Warehouse.").format(index))
		if index <= MAX_PREVIEW_ITEMS:
			items.append({"item_code": item_code, "qty": qty, "source_warehouse": row_source, "target_warehouse": row_target})

	return {
		"kind": "transfer",
		"title": _("Complete Stock Transfer"),
		"company": company,
		"source_branch": source_branch,
		"target_branch": target_branch,
		"source_warehouse": source_warehouse,
		"target_warehouse": target_warehouse,
		"items": items,
		"item_count": len(doc.get("items") or []),
		"blockers": list(dict.fromkeys(blockers)),
	}


def _adjustment_preview(doc, company: str, scope: dict[str, Any]) -> dict[str, Any]:
	blockers = _base_blockers(doc)
	if _clean(doc.get("purpose")) not in {"", STOCK_RECONCILIATION_PURPOSE}:
		blockers.append(_("Only standard Stock Reconciliation adjustments can be completed here."))

	warehouses = {
		_clean(row.get("warehouse") or doc.get("set_warehouse"))
		for row in list(doc.get("items") or [])
		if _clean(row.get("warehouse") or doc.get("set_warehouse"))
	}
	if len(warehouses) != 1:
		blockers.append(_("Standard completion requires one Warehouse for the physical count."))
	warehouse = next(iter(warehouses), _clean(doc.get("set_warehouse")))
	if not warehouse:
		blockers.append(_("Warehouse is required."))

	branch = ""
	if warehouse:
		branch = _validate_warehouse_access(
			company=company,
			warehouse=warehouse,
			stored_branch=_clean(doc.get("retailedge_branch")),
			scope=scope,
			validator=_validate_adjustment_branch_warehouse,
		)

	items: list[dict[str, Any]] = []
	seen: set[str] = set()
	for index, row in enumerate(list(doc.get("items") or []), start=1):
		item_code = _clean(row.get("item_code"))
		qty = flt(row.get("qty"))
		if not item_code:
			blockers.append(_("Item is missing on row {0}.").format(index))
		elif item_code in seen:
			blockers.append(_("Item {0} appears more than once.").format(item_code))
		else:
			seen.add(item_code)
			if not frappe.has_permission("Item", "read", doc=item_code):
				frappe.throw(_("You do not have permission to use Item {0}.").format(item_code), frappe.PermissionError)
			tracking = _item_tracking(item_code)
			if tracking["has_serial_no"] or tracking["has_batch_no"]:
				blockers.append(
					_("Item {0} uses Serial No or Batch tracking and requires Advanced ERPNext.").format(item_code)
				)
		if qty < 0:
			blockers.append(_("Physical quantity on row {0} cannot be negative.").format(index))
		row_warehouse = _clean(row.get("warehouse") or doc.get("set_warehouse"))
		if warehouse and row_warehouse != warehouse:
			blockers.append(_("Row {0} uses a different Warehouse.").format(index))
		if index <= MAX_PREVIEW_ITEMS:
			items.append({"item_code": item_code, "qty": qty, "warehouse": row_warehouse})

	return {
		"kind": "adjustment",
		"title": _("Complete Stock Adjustment"),
		"company": company,
		"branch": branch,
		"warehouse": warehouse,
		"items": items,
		"item_count": len(doc.get("items") or []),
		"blockers": list(dict.fromkeys(blockers)),
	}


def _build_preview(doc) -> dict[str, Any]:
	company, scope = _validate_company_and_scope(doc)
	if doc.doctype == STOCK_ENTRY_DOCTYPE:
		payload = _transfer_preview(doc, company, scope)
	else:
		payload = _adjustment_preview(doc, company, scope)

	workflow_readiness = get_workflow_readiness(doctype=doc.doctype, doc=doc)
	workflow_controlled = _clean(workflow_readiness.get("source")) == "frappe"
	blockers = list(payload.get("blockers") or [])
	if not workflow_controlled and not blockers and not frappe.has_permission(doc.doctype, "submit", doc=doc):
		blockers.append(_("You do not have permission to submit this {0}.").format(doc.doctype))

	return {
		**payload,
		"doctype": doc.doctype,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"posting_date": str(doc.get("posting_date") or ""),
		"status": _clean(doc.get("status")) or ("Draft" if cint(doc.docstatus) == 0 else ""),
		"blockers": blockers,
		"can_submit": bool(not blockers and not workflow_controlled and cint(doc.docstatus) == 0),
		"workflow_readiness": workflow_readiness,
		"workflow_eligible": bool(workflow_controlled and not blockers and cint(doc.docstatus) == 0),
		"source_of_truth": f"ERPNext {doc.doctype}",
		"persistence": "none",
		"route": f"/app/{frappe.scrub(doc.doctype).replace('_', '-')}/{doc.name}",
	}


@frappe.whitelist()
def get_standard_stock_completion_preview(doctype: str, name: str) -> dict[str, Any]:
	doc = _get_stock_document(doctype, name)
	return _build_preview(doc)


@frappe.whitelist(methods=["POST"])
def submit_standard_stock_document(
	doctype: str,
	name: str,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	doctype = _clean(doctype)
	name = _clean(name)
	if doctype not in SUPPORTED_DOCTYPES:
		frappe.throw(_("Unsupported standard stock completion document type."), frappe.ValidationError)
	_lock_document(doctype, name)
	doc = _get_stock_document(doctype, name)
	_assert_expected_modified(doc, expected_modified)
	preview = _build_preview(doc)
	if preview.get("blockers"):
		frappe.throw(
			_("Standard EdgeSuite completion is blocked:\n- {0}").format("\n- ".join(preview["blockers"])),
			frappe.ValidationError,
		)
	if _clean(preview.get("workflow_readiness", {}).get("source")) == "frappe":
		frappe.throw(
			_("This {0} is controlled by an active Frappe Workflow. Use the available workflow action in EdgeSuite.").format(doctype),
			frappe.ValidationError,
		)
	if not frappe.has_permission(doctype, "submit", doc=doc):
		frappe.throw(_("You do not have permission to submit this {0}.").format(doctype), frappe.PermissionError)

	# ERPNext owns Stock Ledger, valuation and all stock validation.
	doc.submit()
	if cint(doc.docstatus) != 1:
		frappe.throw(_("ERPNext did not submit {0} {1}.").format(doctype, name))
	doc.reload()
	return {
		"doctype": doc.doctype,
		"name": doc.name,
		"modified": _clean(doc.get("modified")),
		"docstatus": cint(doc.docstatus),
		"status": _clean(doc.get("status")) or "Submitted",
		"company": _clean(doc.get("company")),
		"source_of_truth": "ERPNext native stock submit",
		"route": preview.get("route"),
	}


@frappe.whitelist(methods=["POST"])
def apply_standard_stock_workflow_action(
	doctype: str,
	name: str,
	action: str,
	expected_modified: str | None = None,
	expected_workflow_state: str | None = None,
) -> dict[str, Any]:
	doctype = _clean(doctype)
	name = _clean(name)
	action = _clean(action)
	if doctype not in SUPPORTED_DOCTYPES:
		frappe.throw(_("Unsupported standard stock completion document type."), frappe.ValidationError)
	if not action:
		frappe.throw(_("Workflow action is required."), frappe.ValidationError)
	_lock_document(doctype, name)
	doc = _get_stock_document(doctype, name)
	expected_modified = _assert_expected_modified(doc, expected_modified)
	preview = _build_preview(doc)
	if preview.get("blockers"):
		frappe.throw(
			_("Standard EdgeSuite completion is blocked:\n- {0}").format("\n- ".join(preview["blockers"])),
			frappe.ValidationError,
		)
	if _clean(preview.get("workflow_readiness", {}).get("source")) != "frappe":
		frappe.throw(_("No active Frappe Workflow owns this {0}.").format(doctype), frappe.ValidationError)

	return apply_document_workflow_action(
		doctype=doctype,
		name=name,
		action=action,
		expected_modified=expected_modified,
		expected_state=_clean(expected_workflow_state),
	)
