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
