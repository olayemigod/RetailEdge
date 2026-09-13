from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.professional_purchasing import (
	_assert_create,
	_assert_read,
	_document_branch,
	_permission,
	_validate_native_purchase_return_source,
	_validate_native_purchase_return_target,
)
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_doctype_workflow_summary, get_workflow_readiness

PURCHASE_RECEIPT_DOCTYPE = "Purchase Receipt"
PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"
SOURCE_TYPES = {
	"purchase_receipt": PURCHASE_RECEIPT_DOCTYPE,
	"purchase_invoice": PURCHASE_INVOICE_DOCTYPE,
}


def _source_doctype(source_type: str | None) -> str:
	key = str(source_type or "").strip().lower()
	if key not in SOURCE_TYPES:
		frappe.throw(_("Choose Purchase Receipt return or Supplier Debit Note."))
	return SOURCE_TYPES[key]


def _source_label(doctype: str) -> str:
	return PURCHASE_RECEIPT_DOCTYPE if doctype == PURCHASE_RECEIPT_DOCTYPE else PURCHASE_INVOICE_DOCTYPE


def _get_source(
	source_type: str | None,
	source_name: str | None,
	*,
	lock: bool = False,
	require_create: bool = True,
) -> Any:
	doctype = _source_doctype(source_type)
	name = str(source_name or "").strip()
	if not name:
		frappe.throw(_("{0} is required.").format(_source_label(doctype)))
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(_source_label(doctype), name))
	_assert_read(doctype, name)
	if require_create:
		_assert_create(doctype)
	if lock:
		# Serialise return posting for one submitted source so concurrent requests
		# cannot both map the same remaining returnable quantity.
		frappe.db.sql(f"SELECT name FROM `tab{doctype}` WHERE name = %s FOR UPDATE", (name,))
	source = frappe.get_doc(doctype, name)
	_validate_native_purchase_return_source(source, source_label=_source_label(doctype))
	return source


def _map_target(source: Any) -> tuple[Any, list[Any], str]:
	doctype = str(source.doctype or "")
	company, source_branch = _validate_native_purchase_return_source(source, source_label=_source_label(doctype))
	if doctype == PURCHASE_RECEIPT_DOCTYPE:
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_return

		target = make_purchase_return(source.name)
	else:
		from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import make_debit_note

		target = make_debit_note(source.name)
	items, target_branch = _validate_native_purchase_return_target(
		source,
		target,
		target_doctype=doctype,
		source_label=_source_label(doctype),
		company=company,
		source_branch=source_branch,
	)
	return target, items, target_branch


def _return_workflow_summary(doctype: str) -> dict[str, Any]:
	summary = get_doctype_workflow_summary(doctype)
	if summary.get("enabled") and summary.get("source") == "frappe":
		return summary
	return {"enabled": False, "source": "none", "workflow": "", "state_field": ""}


def _linked_draft_return_names(source: Any) -> list[str]:
	doctype = str(source.doctype or "")
	rows = frappe.db.sql(
		f"""
		SELECT name, modified
		FROM `tab{doctype}`
		WHERE docstatus = 0
			AND COALESCE(is_return, 0) = 1
			AND return_against = %s
		ORDER BY modified DESC, name DESC
		LIMIT 3
		""",
		(source.name,),
		as_dict=True,
	)
	return [str(row.get("name") or "") for row in rows if row.get("name")]


def _get_single_linked_draft_return(source: Any) -> Any | None:
	names = _linked_draft_return_names(source)
	if len(names) > 1:
		frappe.throw(
			_(
				"Multiple draft {0} returns already exist for {1}. Use Advanced ERPNext review before continuing."
			).format(source.doctype, source.name)
		)
	if not names:
		return None
	draft = frappe.get_doc(source.doctype, names[0])
	if not frappe.has_permission(source.doctype, "read", doc=draft):
		frappe.throw(
			_(
				"A draft {0} return already exists for {1}, but you do not have permission to review it."
			).format(source.doctype, source.name),
			frappe.PermissionError,
		)
	return draft


def _return_item_signature(rows: list[Any], source_doctype: str) -> list[tuple[str, str, float, str, float, float]]:
	source_item_field = (
		"purchase_receipt_item"
		if source_doctype == PURCHASE_RECEIPT_DOCTYPE
		else "purchase_invoice_item"
	)
	result: list[tuple[str, str, float, str, float, float]] = []
	for row in rows:
		result.append(
			(
				str(getattr(row, source_item_field, None) or ""),
				str(getattr(row, "item_code", None) or ""),
				round(flt(getattr(row, "qty", 0)), 6),
				str(getattr(row, "warehouse", None) or ""),
				round(flt(getattr(row, "rate", 0)), 6),
				round(flt(getattr(row, "conversion_factor", 0)), 6),
			)
		)
	return sorted(result)


def _validate_standard_return_draft(
	*,
	source: Any,
	draft: Any,
	expected_target: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], str]:
	blockers: list[dict[str, str]] = []
	if cint(getattr(draft, "docstatus", 0)) != 0:
		blockers.append({"key": "not_draft", "label": _("{0} return is no longer a draft").format(source.doctype)})
	if not cint(getattr(draft, "is_return", 0)):
		blockers.append({"key": "not_return", "label": _("Saved document is no longer marked as a return")})
	if str(getattr(draft, "return_against", "") or "") != str(source.name or ""):
		blockers.append({"key": "return_against", "label": _("Saved return no longer links to the selected source")})
	if str(getattr(draft, "company", "") or "") != str(getattr(expected_target, "company", "") or ""):
		blockers.append({"key": "company_mismatch", "label": _("Saved return Company no longer matches ERPNext's canonical mapping")})
	if str(getattr(draft, "supplier", "") or "") != str(getattr(expected_target, "supplier", "") or ""):
		blockers.append({"key": "supplier_mismatch", "label": _("Saved return Supplier no longer matches ERPNext's canonical mapping")})

	expected_branch = _document_branch(expected_target)
	draft_branch = _document_branch(draft)
	if draft_branch != expected_branch:
		blockers.append({"key": "branch_mismatch", "label": _("Saved return Branch no longer matches ERPNext's canonical mapping")})

	if source.doctype == PURCHASE_INVOICE_DOCTYPE and bool(cint(getattr(draft, "update_stock", 0))) != bool(
		cint(getattr(expected_target, "update_stock", 0))
	):
		blockers.append({"key": "update_stock_changed", "label": _("Saved Debit Note Update Stock setting no longer matches ERPNext's canonical mapping")})

	all_rows = list(getattr(draft, "items", None) or [])
	negative_rows = [row for row in all_rows if flt(getattr(row, "qty", 0)) < 0]
	if len(negative_rows) != len(all_rows):
		blockers.append({"key": "non_return_quantity", "label": _("Saved return contains a non-negative item quantity")})
	items, row_blockers = _preview_items(draft, negative_rows)
	blockers.extend(row_blockers)
	if not items:
		blockers.append({"key": "no_return_items", "label": _("Saved return has no negative return quantity")})

	if _return_item_signature(all_rows, source.doctype) != _return_item_signature(
		list(getattr(expected_target, "items", None) or []),
		source.doctype,
	):
		blockers.append(
			{
				"key": "mapped_return_changed",
				"label": _("Saved return no longer matches ERPNext's current canonical return mapping"),
			}
		)

	return items, blockers, draft_branch


def _workflow_draft_payload(
	*,
	source: Any,
	draft: Any,
	items: list[dict[str, Any]],
	blockers: list[dict[str, str]],
	branch: str,
	idempotent: bool,
) -> dict[str, Any]:
	readiness = get_workflow_readiness(doctype=source.doctype, doc=draft)
	return {
		"source_type": "purchase_receipt" if source.doctype == PURCHASE_RECEIPT_DOCTYPE else "purchase_invoice",
		"source_doctype": source.doctype,
		"source_name": source.name,
		"source_modified": str(getattr(source, "modified", "") or ""),
		"target_doctype": draft.doctype,
		"target_name": draft.name,
		"target_modified": str(getattr(draft, "modified", "") or ""),
		"return_against": str(getattr(draft, "return_against", "") or ""),
		"company": str(getattr(draft, "company", "") or ""),
		"branch": branch,
		"supplier": str(getattr(draft, "supplier", "") or ""),
		"supplier_name": str(getattr(draft, "supplier_name", "") or getattr(source, "supplier_name", "") or getattr(draft, "supplier", "") or ""),
		"posting_date": str(getattr(draft, "posting_date", "") or ""),
		"update_stock": bool(cint(getattr(draft, "update_stock", 0))),
		"stock_effect": _stock_effect_enabled(draft),
		"items": items,
		"blockers": blockers,
		"standard_return_eligible": not blockers,
		"can_submit": False,
		"workflow_controlled": True,
		"can_start_workflow": False,
		"workflow_started": True,
		"workflow_readiness": readiness,
		"idempotent": idempotent,
		"persistence": "draft",
		"posting_status": "Workflow draft",
		"source_of_truth": "ERPNext canonical purchase return mapper",
	}


def _stock_effect_enabled(target: Any) -> bool:
	if str(target.doctype or "") == PURCHASE_RECEIPT_DOCTYPE:
		return True
	return bool(cint(getattr(target, "update_stock", 0)))


def _item_stock_controls(item_code: str) -> dict[str, bool]:
	if not item_code:
		return {"has_serial_no": False, "has_batch_no": False}
	values = frappe.db.get_value(
		"Item",
		item_code,
		["has_serial_no", "has_batch_no"],
		as_dict=True,
	) or {}
	return {
		"has_serial_no": bool(cint(values.get("has_serial_no"))),
		"has_batch_no": bool(cint(values.get("has_batch_no"))),
	}


def _preview_items(target: Any, items: list[Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
	rows: list[dict[str, Any]] = []
	blockers: list[dict[str, str]] = []
	stock_effect = _stock_effect_enabled(target)
	company = str(getattr(target, "company", "") or "")
	for item in items:
		item_code = str(getattr(item, "item_code", "") or "").strip()
		qty = flt(getattr(item, "qty", 0))
		if qty >= 0:
			frappe.throw(_("ERPNext mapped a non-return quantity for Item {0}.").format(item_code or _("Unknown")))
		warehouse = str(getattr(item, "warehouse", "") or "").strip()
		if stock_effect and warehouse:
			warehouse_company = str(frappe.db.get_value("Warehouse", warehouse, "company") or "")
			if warehouse_company != company:
				frappe.throw(_("Stock Location {0} does not belong to Company {1}.").format(warehouse, company))
		controls = _item_stock_controls(item_code) if stock_effect else {"has_serial_no": False, "has_batch_no": False}
		if controls["has_serial_no"]:
			blockers.append({
				"key": "serial_number",
				"item_code": item_code,
				"label": _("Serial Number handling requires Advanced ERPNext"),
			})
		if controls["has_batch_no"]:
			blockers.append({
				"key": "batch",
				"item_code": item_code,
				"label": _("Batch handling requires Advanced ERPNext"),
			})
		rows.append(
			{
				"name": str(getattr(item, "name", "") or ""),
				"item_code": item_code,
				"item_name": str(getattr(item, "item_name", "") or item_code),
				"qty": qty,
				"uom": str(getattr(item, "uom", "") or getattr(item, "stock_uom", "") or ""),
				"warehouse": warehouse,
				"rate": flt(getattr(item, "rate", 0)),
				"amount": flt(getattr(item, "amount", 0)),
				"requires_serial_no": controls["has_serial_no"],
				"requires_batch": controls["has_batch_no"],
			}
		)
	return rows, blockers


def _build_review(
	source: Any,
	workflow_summary: dict[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
	target, mapped_items, target_branch = _map_target(source)
	items, blockers = _preview_items(target, mapped_items)
	workflow_summary = workflow_summary or _return_workflow_summary(source.doctype)
	workflow_controlled = bool(workflow_summary.get("enabled"))
	can_submit = bool(
		not workflow_controlled
		and not blockers
		and _permission(source.doctype, "submit")
	)
	return target, {
		"source_type": "purchase_receipt" if source.doctype == PURCHASE_RECEIPT_DOCTYPE else "purchase_invoice",
		"source_doctype": source.doctype,
		"source_name": source.name,
		"source_modified": str(getattr(source, "modified", "") or ""),
		"target_doctype": target.doctype,
		"target_name": "",
		"target_modified": "",
		"return_against": str(getattr(target, "return_against", "") or ""),
		"company": str(getattr(target, "company", "") or ""),
		"branch": target_branch,
		"supplier": str(getattr(target, "supplier", "") or ""),
		"supplier_name": str(getattr(target, "supplier_name", "") or getattr(source, "supplier_name", "") or getattr(target, "supplier", "") or ""),
		"posting_date": str(getattr(target, "posting_date", "") or ""),
		"update_stock": bool(cint(getattr(target, "update_stock", 0))),
		"stock_effect": _stock_effect_enabled(target),
		"items": items,
		"blockers": blockers,
		"standard_return_eligible": not blockers,
		"can_submit": can_submit,
		"workflow_controlled": workflow_controlled,
		"can_start_workflow": bool(workflow_controlled and not blockers),
		"workflow_started": False,
		"workflow_readiness": {
			**workflow_summary,
			"current_state": "",
			"available_actions": [],
			"requires_action": workflow_controlled,
			"message": _(
				"Start return approval to save the canonical return draft and load the permitted workflow actions."
			)
			if workflow_controlled
			else _("No active return Workflow is configured."),
		},
		"persistence": "none",
		"posting_status": "Preview only",
		"source_of_truth": "ERPNext canonical purchase return mapper",
	}


@frappe.whitelist()
def get_purchase_return_review(source_type: str, source_name: str) -> dict[str, Any]:
	"""Preview a canonical ERPNext Purchase Return / Debit Note without persistence."""
	source = _get_source(source_type, source_name, require_create=False)
	workflow_summary = _return_workflow_summary(source.doctype)
	expected_target, review = _build_review(source, workflow_summary)

	if workflow_summary.get("enabled"):
		existing_draft = _get_single_linked_draft_return(source)
		if existing_draft:
			items, blockers, branch = _validate_standard_return_draft(
				source=source,
				draft=existing_draft,
				expected_target=expected_target,
			)
			return _workflow_draft_payload(
				source=source,
				draft=existing_draft,
				items=items,
				blockers=blockers,
				branch=branch,
				idempotent=True,
			)
	_assert_create(source.doctype)
	return review


@frappe.whitelist(methods=["POST"])
def start_purchase_return_workflow(
	source_type: str,
	source_name: str,
	expected_source_modified: str | None = None,
) -> dict[str, Any]:
	"""Persist or reuse exactly one canonical return draft for an active Frappe Workflow."""
	source = _get_source(
		source_type,
		source_name,
		lock=True,
		require_create=False,
	)
	workflow_summary = _return_workflow_summary(source.doctype)
	if not workflow_summary.get("enabled"):
		frappe.throw(_("No active Frappe Workflow controls this return document."))

	expected_modified = str(expected_source_modified or "").strip()
	current_modified = str(getattr(source, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(
			_("{0} {1} changed after the return preview. Refresh before starting approval.").format(
				_source_label(source.doctype), source.name
			)
		)

	expected_target, review = _build_review(source, workflow_summary)
	if review["blockers"]:
		labels = ", ".join(str(row.get("label") or row.get("key") or "") for row in review["blockers"])
		frappe.throw(_("This return requires Advanced ERPNext handling: {0}").format(labels))

	existing_draft = _get_single_linked_draft_return(source)
	if existing_draft:
		items, blockers, branch = _validate_standard_return_draft(
			source=source,
			draft=existing_draft,
			expected_target=expected_target,
		)
		if blockers:
			labels = ", ".join(str(row.get("label") or row.get("key") or "") for row in blockers)
			frappe.throw(_("The existing return draft requires Advanced ERPNext review: {0}").format(labels))
		return _workflow_draft_payload(
			source=source,
			draft=existing_draft,
			items=items,
			blockers=[],
			branch=branch,
			idempotent=True,
		)

	_assert_create(source.doctype)
	expected_target.insert()
	if cint(getattr(expected_target, "docstatus", 0)) != 0:
		frappe.throw(_("Workflow-controlled return must begin as a saved draft."))
	items, blockers, branch = _validate_standard_return_draft(
		source=source,
		draft=expected_target,
		expected_target=expected_target,
	)
	if blockers:
		labels = ", ".join(str(row.get("label") or row.get("key") or "") for row in blockers)
		frappe.throw(_("The saved return draft no longer satisfies the standard workflow contract: {0}").format(labels))
	return _workflow_draft_payload(
		source=source,
		draft=expected_target,
		items=items,
		blockers=[],
		branch=branch,
		idempotent=False,
	)


@frappe.whitelist(methods=["POST"])
def apply_purchase_return_workflow_action(
	source_type: str,
	source_name: str,
	target_name: str,
	action: str,
	expected_source_modified: str | None = None,
	expected_target_modified: str | None = None,
	expected_workflow_state: str | None = None,
) -> dict[str, Any]:
	"""Apply one permitted Frappe Workflow action to the exact standard return draft."""
	target_name = str(target_name or "").strip()
	action = str(action or "").strip()
	if not target_name or not action:
		frappe.throw(_("Return document and workflow action are required."))

	source = _get_source(
		source_type,
		source_name,
		lock=True,
		require_create=False,
	)
	expected_source = str(expected_source_modified or "").strip()
	current_source = str(getattr(source, "modified", "") or "")
	if not expected_source or expected_source != current_source:
		frappe.throw(
			_("{0} {1} changed after review. Refresh before applying a workflow action.").format(
				_source_label(source.doctype), source.name
			)
		)

	if not frappe.db.exists(source.doctype, target_name):
		frappe.throw(_("{0} return {1} does not exist.").format(source.doctype, target_name))
	_assert_read(source.doctype, target_name)
	frappe.db.sql(
		f"SELECT name FROM `tab{source.doctype}` WHERE name = %s FOR UPDATE",
		(target_name,),
	)
	draft = frappe.get_doc(source.doctype, target_name)
	if cint(getattr(draft, "docstatus", 0)) != 0:
		frappe.throw(_("Only a draft return can use the standard EdgeSuite workflow action path."))

	existing_draft = _get_single_linked_draft_return(source)
	if not existing_draft or existing_draft.name != draft.name:
		frappe.throw(
			_(
				"{0} {1} no longer has exactly this standard return draft. Use Advanced ERPNext review."
			).format(source.doctype, source.name)
		)

	workflow_summary = _return_workflow_summary(source.doctype)
	if not workflow_summary.get("enabled"):
		frappe.throw(_("This return document no longer has an active Frappe Workflow."))

	expected_target, review = _build_review(source, workflow_summary)
	if review["blockers"]:
		labels = ", ".join(str(row.get("label") or row.get("key") or "") for row in review["blockers"])
		frappe.throw(_("This return now requires Advanced ERPNext handling: {0}").format(labels))
	_items, blockers, _branch = _validate_standard_return_draft(
		source=source,
		draft=draft,
		expected_target=expected_target,
	)
	if blockers:
		labels = ", ".join(str(row.get("label") or row.get("key") or "") for row in blockers)
		frappe.throw(_("This return draft requires Advanced ERPNext review: {0}").format(labels))

	expected_target_version = str(expected_target_modified or "").strip()
	current_target_version = str(getattr(draft, "modified", "") or "")
	if not expected_target_version or expected_target_version != current_target_version:
		frappe.throw(
			_("{0} return {1} changed after review. Refresh before applying a workflow action.").format(
				draft.doctype, draft.name
			)
		)

	return apply_document_workflow_action(
		doctype=draft.doctype,
		name=draft.name,
		action=action,
		expected_modified=expected_target_version,
		expected_state=str(expected_workflow_state or ""),
	)


@frappe.whitelist(methods=["POST"])
def submit_purchase_return_review(
	source_type: str,
	source_name: str,
	expected_source_modified: str | None = None,
) -> dict[str, Any]:
	"""Insert and submit one standard canonical Purchase Return / Debit Note."""
	source = _get_source(source_type, source_name, lock=True)
	if _return_workflow_summary(source.doctype).get("enabled"):
		frappe.throw(
			_(
				"{0} return is controlled by an active Frappe Workflow. Start return approval instead of direct submission."
			).format(source.doctype)
		)
	if not _permission(source.doctype, "submit"):
		frappe.throw(_("You do not have permission to submit {0}.").format(_source_label(source.doctype)), frappe.PermissionError)

	expected_modified = str(expected_source_modified or "").strip()
	current_modified = str(getattr(source, "modified", "") or "")
	if not expected_modified or expected_modified != current_modified:
		frappe.throw(
			_("{0} {1} changed after the return preview. Refresh the preview before submitting.").format(
				_source_label(source.doctype), source.name
			)
		)

	target, review = _build_review(source)
	if review["blockers"]:
		labels = ", ".join(str(row.get("label") or row.get("key") or "") for row in review["blockers"])
		frappe.throw(_("This return requires Advanced ERPNext handling: {0}").format(labels))
	if not review["can_submit"]:
		frappe.throw(_("You do not have permission to submit {0}.").format(_source_label(source.doctype)), frappe.PermissionError)

	# ERPNext remains authoritative. The mapped return is inserted and submitted
	# as the current user; no direct Stock Ledger / General Ledger writes occur here.
	target.insert()
	target.submit()
	if cint(getattr(target, "docstatus", 0)) != 1:
		frappe.throw(_("ERPNext did not submit {0} {1}.").format(target.doctype, target.name))

	return {
		"doctype": target.doctype,
		"name": target.name,
		"docstatus": cint(target.docstatus),
		"return_against": str(getattr(target, "return_against", "") or ""),
		"company": str(getattr(target, "company", "") or ""),
		"supplier": str(getattr(target, "supplier", "") or ""),
		"branch": review["branch"],
		"item_count": len(review["items"]),
		"update_stock": review["update_stock"],
		"posting_status": "Submitted",
		"source_of_truth": "ERPNext document submit",
	}
