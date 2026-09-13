from __future__ import annotations

import frappe


VISIBLE_BRANCH_FIELD_METADATA = {
	"retailedge_branch": {
		"label": "Operating Branch",
		"description": "Branch attributed for operating context, filtering and reporting.",
	},
}

HIDDEN_BRANCH_FIELD_LABELS = {
	"retailedge_branch_source": "Operating Branch Source",
	"retailedge_branch_resolved_on": "Operating Branch Resolved On",
	"retailedge_branch_resolution_note": "Operating Branch Resolution Note",
	"retailedge_source_branch": "Source Branch",
	"retailedge_target_branch": "Target Branch",
	"retailedge_warehouse_branch": "Warehouse Branch",
}

BACKFILL_CONFIRMATION = "APPLY BRANCH ATTRIBUTION"


def ensure_neutral_branch_field_labels():
	"""Keep namespaced fieldnames while removing product branding from visible metadata.

	This runs after the branch-attribution custom-field installer, so existing and
	new sites converge on neutral user-facing labels without renaming database
	columns or breaking reports/integrations that depend on the fieldnames.
	"""
	if not frappe.db.exists("DocType", "Custom Field"):
		return {"updated": 0}

	updated = 0
	for fieldname, metadata in VISIBLE_BRANCH_FIELD_METADATA.items():
		updated += _update_matching_custom_fields(fieldname, metadata)
	for fieldname, label in HIDDEN_BRANCH_FIELD_LABELS.items():
		updated += _update_matching_custom_fields(fieldname, {"label": label})
	return {"updated": updated}


def preview_branch_attribution_backfill(doctype=None, filters=None, limit=500):
	"""Safe read-only maintenance preview."""
	from retailedge.transaction_branch_attribution import run_transaction_branch_backfill

	return run_transaction_branch_backfill(
		doctype=doctype,
		filters=filters,
		limit=limit,
		overwrite=False,
		dry_run=True,
	)


def apply_branch_attribution_backfill(
	doctype=None,
	filters=None,
	limit=500,
	overwrite=False,
	commit_every=100,
	confirmation=None,
):
	"""Explicit maintenance-only write path for historical attribution metadata.

	The normal transaction hooks populate attribution on draft/validate. Historical
	backfill is intentionally separate, System Manager only and requires an exact
	confirmation phrase before it may update stored metadata.
	"""
	frappe.only_for("System Manager")
	if confirmation != BACKFILL_CONFIRMATION:
		frappe.throw(
			"Historical branch attribution is maintenance-only. "
			f"Confirm with '{BACKFILL_CONFIRMATION}' before applying changes.",
			frappe.ValidationError,
		)

	from retailedge.transaction_branch_attribution import run_transaction_branch_backfill

	return run_transaction_branch_backfill(
		doctype=doctype,
		filters=filters,
		limit=limit,
		overwrite=overwrite,
		dry_run=False,
		commit_every=commit_every,
	)


def _update_matching_custom_fields(fieldname: str, values: dict) -> int:
	rows = frappe.get_all(
		"Custom Field",
		filters={"fieldname": fieldname},
		fields=["name", "label", "description"],
		limit_page_length=200,
	)
	updated = 0
	for row in rows:
		changes = {
			key: value
			for key, value in values.items()
			if row.get(key) != value
		}
		if not changes:
			continue
		frappe.db.set_value("Custom Field", row.name, changes, update_modified=False)
		updated += 1
	return updated
