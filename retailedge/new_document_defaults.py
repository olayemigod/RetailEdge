from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_defaults_application import (
	_build_preview_doc,
	_diff_snapshots,
	_seed_new_doc_from_operating_context,
	_snapshot_branch_default_fields,
	apply_branch_profile_defaults_to_doc,
)


@frappe.whitelist()
def get_new_document_operating_defaults(doctype: str, values: str | dict[str, Any] | None = None) -> dict[str, Any]:
	"""Preview missing Operating Context / Branch Setup defaults for a new document.

	This API never inserts, saves, submits, cancels or updates a database document.
	It runs the same server-side default engine against an unsaved in-memory copy and
	returns proposed field changes for the caller to apply visibly on a new form.
	"""
	doctype = str(doctype or "").strip()
	if not doctype or not frappe.db.exists("DocType", doctype):
		frappe.throw(_("A valid DocType is required."))
	if not frappe.has_permission(doctype, "create"):
		frappe.throw(
			_("You do not have permission to create {0}.").format(doctype),
			frappe.PermissionError,
		)

	payload = frappe.parse_json(values) if isinstance(values, str) else values
	payload = dict(payload or {})
	payload.pop("name", None)
	payload["doctype"] = doctype
	payload["docstatus"] = 0

	doc = _build_preview_doc(doctype=doctype, values=payload)
	before = _snapshot_branch_default_fields(doc)
	seed = _seed_new_doc_from_operating_context(doc)
	summary = apply_branch_profile_defaults_to_doc(doc, overwrite=False)
	after = _snapshot_branch_default_fields(doc)
	changes = _diff_snapshots(before, after)

	return {
		"doctype": doctype,
		"changes": changes,
		"seed": seed,
		"summary": summary,
		"has_changes": bool(changes),
	}
