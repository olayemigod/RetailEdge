from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from retailedge.cashier_expense import append_cashier_expense_action_log


EXPENSE_DOCTYPE = "RetailEdge Cashier Expense"
BRANCH_PROFILE_DOCTYPE = "RetailEdge Branch Profile"
OPENING_SHIFT_DOCTYPE = "POS Opening Shift"
MAX_AUDIT_ROWS = 5000


@frappe.whitelist()
def audit_cashier_expense_pos_profile_branch_history(limit: int | str = MAX_AUDIT_ROWS) -> dict[str, Any]:
	_assert_reconciliation_access()
	return _run_cashier_expense_pos_profile_branch_history(limit=limit, dry_run=True)


@frappe.whitelist(methods=["POST"])
def reconcile_cashier_expense_pos_profile_branch_history(
	dry_run: bool | int | str = True,
	limit: int | str = MAX_AUDIT_ROWS,
) -> dict[str, Any]:
	_assert_reconciliation_access()
	return _run_cashier_expense_pos_profile_branch_history(
		limit=limit,
		dry_run=bool(cint(dry_run)) if isinstance(dry_run, str) else bool(dry_run),
	)


def run_patch_reconciliation(limit: int | str = MAX_AUDIT_ROWS) -> dict[str, Any]:
	"""Migration entry point. No explicit commit: Frappe owns the patch transaction."""
	return _run_cashier_expense_pos_profile_branch_history(limit=limit, dry_run=False)


def _run_cashier_expense_pos_profile_branch_history(
	*,
	limit: int | str,
	dry_run: bool,
) -> dict[str, Any]:
	limit = max(1, min(cint(limit) or MAX_AUDIT_ROWS, MAX_AUDIT_ROWS))
	result = {
		"dry_run": bool(dry_run),
		"checked": 0,
		"repairable": 0,
		"repaired": 0,
		"already_correct": 0,
		"ambiguous": 0,
		"skipped": 0,
		"items": [],
	}
	if not frappe.db.exists("DocType", EXPENSE_DOCTYPE):
		return result
	if not frappe.db.exists("DocType", BRANCH_PROFILE_DOCTYPE):
		return result

	rows = frappe.get_all(
		EXPENSE_DOCTYPE,
		filters={
			"docstatus": ["!=", 2],
			"expense_status": ["!=", "Cancelled"],
			"pos_profile": ["not in", ["", None]],
			"branch": ["not in", ["", None]],
		},
		fields=[
			"name",
			"company",
			"branch",
			"pos_profile",
			"linked_pos_opening_shift",
			"expense_status",
			"ledger_status",
			"posting_reference_type",
			"posting_reference",
			"docstatus",
		],
		order_by="creation asc, name asc",
		limit_page_length=limit,
	)

	for row in rows:
		result["checked"] += 1
		classification = _classify_row(row)
		item = {
			"name": row.get("name"),
			"company": row.get("company"),
			"pos_profile": row.get("pos_profile"),
			"opening_shift": row.get("linked_pos_opening_shift"),
			"old_branch": row.get("branch"),
			"new_branch": classification.get("target_branch"),
			"status": classification.get("status"),
			"reason": classification.get("reason"),
			"posting_reference_type": row.get("posting_reference_type"),
			"posting_reference": row.get("posting_reference"),
		}
		status = classification["status"]
		if status == "already_correct":
			result["already_correct"] += 1
		elif status == "repairable":
			result["repairable"] += 1
			if not dry_run:
				_repair_row(row, classification)
				result["repaired"] += 1
				item["status"] = "repaired"
		elif status == "ambiguous":
			result["ambiguous"] += 1
		else:
			result["skipped"] += 1
		result["items"].append(item)
	return result


def _classify_row(row) -> dict[str, str | None]:
	company = str(row.get("company") or "").strip()
	current_branch = str(row.get("branch") or "").strip()
	pos_profile = str(row.get("pos_profile") or "").strip()
	opening_shift = str(row.get("linked_pos_opening_shift") or "").strip()
	if not company or not current_branch or not pos_profile:
		return _classification("skipped", "Company, current Branch, and POS Profile are required.")

	targets = frappe.get_all(
		BRANCH_PROFILE_DOCTYPE,
		filters={
			"company": company,
			"enabled": 1,
			"default_pos_profile": pos_profile,
		},
		fields=["name", "branch", "default_pos_profile"],
		limit_page_length=3,
		order_by="branch asc, name asc",
	)
	target_branches = list(
		dict.fromkeys(str(target.get("branch") or "").strip() for target in targets if target.get("branch"))
	)
	if len(target_branches) != 1:
		return _classification(
			"ambiguous",
			"Explicit POS Profile does not map to exactly one enabled Branch Profile.",
		)
	target_branch = target_branches[0]
	if target_branch == current_branch:
		return _classification("already_correct", "Branch already matches the exact POS Profile mapping.", target_branch)

	current_profiles = frappe.get_all(
		BRANCH_PROFILE_DOCTYPE,
		filters={"company": company, "branch": current_branch, "enabled": 1},
		fields=["name", "branch", "default_pos_profile"],
		limit_page_length=2,
	)
	if len(current_profiles) != 1:
		return _classification(
			"ambiguous",
			"Current Branch does not have exactly one enabled Branch Profile.",
			target_branch,
		)
	current_profile_pos = str(current_profiles[0].get("default_pos_profile") or "").strip()
	if current_profile_pos:
		return _classification(
			"skipped",
			"Current Branch has an explicit POS Profile mapping, so this is not the blank-profile wildcard defect.",
			target_branch,
		)

	if not opening_shift:
		return _classification(
			"ambiguous",
			"No linked POS Opening Shift is available to prove the historical POS context.",
			target_branch,
		)
	opening_profile = frappe.db.get_value(OPENING_SHIFT_DOCTYPE, opening_shift, "pos_profile")
	if str(opening_profile or "").strip() != pos_profile:
		return _classification(
			"ambiguous",
			"Linked POS Opening Shift does not use the same POS Profile as the expense.",
			target_branch,
		)

	return _classification(
		"repairable",
		"Historical blank POS-profile wildcard attribution is proven by exact POS Profile and Opening Shift context.",
		target_branch,
	)


def _repair_row(row, classification: dict[str, str | None]) -> None:
	old_branch = str(row.get("branch") or "").strip()
	new_branch = str(classification.get("target_branch") or "").strip()
	if not old_branch or not new_branch or old_branch == new_branch:
		return
	frappe.db.set_value(
		EXPENSE_DOCTYPE,
		row.get("name"),
		"branch",
		new_branch,
		update_modified=False,
	)
	status = str(row.get("expense_status") or "").strip() or None
	append_cashier_expense_action_log(
		row.get("name"),
		action="Branch Attribution Reconciled",
		previous_status=status,
		new_status=status,
		remarks=_("Corrected historical Branch attribution caused by the blank POS Profile wildcard resolver defect."),
		context={
			"old_branch": old_branch,
			"new_branch": new_branch,
			"pos_profile": row.get("pos_profile"),
			"opening_shift": row.get("linked_pos_opening_shift"),
			"posting_reference_type": row.get("posting_reference_type"),
			"posting_reference": row.get("posting_reference"),
			"reason": classification.get("reason"),
		},
	)


def _classification(status: str, reason: str, target_branch: str | None = None) -> dict[str, str | None]:
	return {"status": status, "reason": reason, "target_branch": target_branch}


def _assert_reconciliation_access() -> None:
	user = frappe.session.user
	if user == "Administrator":
		return
	roles = set(frappe.get_roles(user))
	if roles.intersection({"System Manager", "RetailEdge Manager", "RetailEdgeManager"}):
		return
	frappe.throw(_("You do not have permission to audit or reconcile Cashier Expense Branch history."), frappe.PermissionError)
