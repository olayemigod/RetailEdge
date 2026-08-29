from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.branch_context import (
	resolve_branch_from_closing_shift,
	resolve_branch_from_opening_shift,
	resolve_branch_from_pos_profile,
	resolve_branch_from_warehouse,
	validate_user_branch_access,
)
from retailedge.branch_defaults_application import (
	_build_preview_doc,
	_diff_snapshots,
	_seed_new_doc_from_operating_context,
	_snapshot_branch_default_fields,
	apply_branch_profile_defaults_to_doc,
)
from retailedge.operating_context import validate_operating_branch

WAREHOUSE_CONTEXT_FIELDS = (
	"warehouse",
	"set_warehouse",
	"default_warehouse",
	"target_warehouse",
	"to_warehouse",
	"from_warehouse",
	"source_warehouse",
)
POS_CONTEXT_FIELDS = {
	"linked_pos_opening_shift": ("POS Opening Shift", resolve_branch_from_opening_shift),
	"pos_opening_shift": ("POS Opening Shift", resolve_branch_from_opening_shift),
	"linked_pos_closing_shift": ("POS Closing Shift", resolve_branch_from_closing_shift),
	"pos_closing_shift": ("POS Closing Shift", resolve_branch_from_closing_shift),
}


@frappe.whitelist()
def get_new_document_operating_defaults(
	doctype: str,
	values: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
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
	_validate_preview_context(doc)
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


def _validate_preview_context(doc) -> None:
	company = str(getattr(doc, "company", None) or "").strip()
	branch = str(
		getattr(doc, "branch", None)
		or getattr(doc, "retailedge_branch", None)
		or ""
	).strip()

	if company:
		_assert_named_read("Company", company)
	if branch:
		_assert_branch_access(branch=branch, company=company)

	for fieldname in WAREHOUSE_CONTEXT_FIELDS:
		warehouse = str(getattr(doc, fieldname, None) or "").strip()
		if not warehouse:
			continue
		_assert_named_read("Warehouse", warehouse)
		warehouse_company = str(frappe.db.get_value("Warehouse", warehouse, "company") or "").strip()
		if company and warehouse_company and warehouse_company != company:
			frappe.throw(_("Stock Location {0} does not belong to Company {1}.").format(warehouse, company))
		resolved = resolve_branch_from_warehouse(warehouse, company=company or warehouse_company)
		warehouse_branch = str(resolved.get("branch") or "").strip()
		if warehouse_branch:
			_assert_branch_access(branch=warehouse_branch, company=company or warehouse_company)
			if branch and warehouse_branch != branch:
				frappe.throw(_("Stock Location {0} does not belong to Branch {1}.").format(warehouse, branch))

	pos_profile = str(getattr(doc, "pos_profile", None) or "").strip()
	if pos_profile:
		_assert_named_read("POS Profile", pos_profile)
		resolved = resolve_branch_from_pos_profile(pos_profile, company=company or None)
		profile_company = str(resolved.get("company") or "").strip()
		profile_branch = str(resolved.get("branch") or "").strip()
		if company and profile_company and profile_company != company:
			frappe.throw(_("POS Profile {0} does not belong to Company {1}.").format(pos_profile, company))
		if profile_branch:
			_assert_branch_access(branch=profile_branch, company=company or profile_company)
			if branch and profile_branch != branch:
				frappe.throw(_("POS Profile {0} does not belong to Branch {1}.").format(pos_profile, branch))

	for fieldname, (doctype, resolver) in POS_CONTEXT_FIELDS.items():
		reference = str(getattr(doc, fieldname, None) or "").strip()
		if not reference or not frappe.db.exists("DocType", doctype):
			continue
		_assert_named_read(doctype, reference)
		resolved = resolver(reference, company=company or None)
		resolved_company = str(resolved.get("company") or "").strip()
		resolved_branch = str(resolved.get("branch") or "").strip()
		if company and resolved_company and resolved_company != company:
			frappe.throw(_("{0} {1} belongs to a different Company.").format(doctype, reference))
		if resolved_branch:
			_assert_branch_access(branch=resolved_branch, company=company or resolved_company)
			if branch and resolved_branch != branch:
				frappe.throw(_("{0} {1} belongs to a different Branch.").format(doctype, reference))


def _assert_named_read(doctype: str, name: str) -> None:
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, name))
	if not frappe.has_permission(doctype, "read", doc=name):
		frappe.throw(
			_("You do not have permission to use {0} {1}.").format(doctype, name),
			frappe.PermissionError,
		)


def _assert_branch_access(*, branch: str, company: str = "") -> None:
	_assert_named_read("Branch", branch)
	validate_user_branch_access(
		branch,
		user=frappe.session.user,
		company=company or None,
		throw=True,
	)
	validate_operating_branch(
		company=company,
		branch=branch,
		user=frappe.session.user,
		throw=True,
	)
