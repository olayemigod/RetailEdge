from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from retailedge.branch_setup import get_branch_setup, save_branch_setup
from retailedge.print_output_settings import BRANCH_PRINT_VISIBILITY_FIELD


BRANCH_SETUP_DOCTYPE = "RetailEdge Branch Profile"


def _coerce_values(values=None) -> dict[str, Any]:
	if isinstance(values, str):
		values = frappe.parse_json(values)
	return dict(values or {})


def _require_visibility_field(doc) -> None:
	if doc.meta.has_field(BRANCH_PRINT_VISIBILITY_FIELD):
		return
	frappe.throw(
		_("Branch print visibility is not installed yet. Run site migration and try again."),
		title=_("Branch Setup needs migration"),
	)


@frappe.whitelist()
def get_branch_setup_with_print_visibility(name: str) -> dict[str, Any]:
	"""Return the normal Branch Setup payload plus customer-facing print policy."""
	result = get_branch_setup(name)
	doc = frappe.get_doc(BRANCH_SETUP_DOCTYPE, name)
	doc.check_permission("read")
	_require_visibility_field(doc)
	result = dict(result or {})
	result["doc"] = dict(result.get("doc") or {})
	result["doc"][BRANCH_PRINT_VISIBILITY_FIELD] = cint(doc.get(BRANCH_PRINT_VISIBILITY_FIELD))
	return result


@frappe.whitelist(methods=["POST"])
def save_branch_setup_with_print_visibility(values=None) -> dict[str, Any]:
	"""Save Branch Setup and its print policy in the same request transaction.

	The base Branch Setup service remains authoritative for Company/Branch/default
	validation. This wrapper owns only the presentation-only branch visibility flag.
	No submitted accounting document is read for write or mutated here.
	"""
	values = _coerce_values(values)
	show_branch = cint(values.pop(BRANCH_PRINT_VISIBILITY_FIELD, 0))

	result = save_branch_setup(values)
	name = str((result or {}).get("name") or "").strip()
	if not name:
		frappe.throw(_("Branch Setup could not be resolved after saving."))

	doc = frappe.get_doc(BRANCH_SETUP_DOCTYPE, name)
	doc.check_permission("write")
	_require_visibility_field(doc)
	doc.set(BRANCH_PRINT_VISIBILITY_FIELD, show_branch)
	doc.save()

	result = dict(result or {})
	result["doc"] = dict(result.get("doc") or {})
	result["doc"][BRANCH_PRINT_VISIBILITY_FIELD] = show_branch
	return result
