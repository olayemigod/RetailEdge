from __future__ import annotations

import frappe

from retailedge.branch_context import resolve_retailedge_branch_context


STRONG_BRANCH_SOURCES = {
	"RetailEdge Branch Profile",
	"POS Profile.branch",
	"POS Profile.set_branch",
	"POS Profile.service_branch",
	"POS Profile.retail_branch",
	"POS Profile.default_branch",
	"POS Opening Shift.branch",
	"POS Opening Shift.set_branch",
	"POS Opening Shift.service_branch",
	"POS Opening Shift.retail_branch",
	"POS Opening Shift.default_branch",
}


def execute():
	if not frappe.db.exists("DocType", "RetailEdge Cashier Expense"):
		return

	meta = frappe.get_meta("RetailEdge Cashier Expense")
	required = {"branch", "company", "cashier", "pos_profile", "linked_pos_opening_shift"}
	if not all(meta.has_field(fieldname) for fieldname in required):
		return

	rows = frappe.get_all(
		"RetailEdge Cashier Expense",
		filters={"branch": ["in", ["", None]]},
		fields=[
			"name",
			"company",
			"cashier",
			"pos_profile",
			"linked_pos_opening_shift",
		],
		limit_page_length=0,
		order_by="creation asc",
	)

	for row in rows:
		if not (row.pos_profile or row.linked_pos_opening_shift):
			continue
		context = resolve_retailedge_branch_context(
			company=row.company,
			pos_profile=row.pos_profile,
			cashier=row.cashier,
			pos_opening_shift=row.linked_pos_opening_shift,
			user=row.cashier,
			prefer_coreedge=False,
		)
		branch = str(context.get("branch") or "").strip()
		source = str(context.get("source") or "").strip()
		if not branch or source not in STRONG_BRANCH_SOURCES:
			continue
		frappe.db.set_value(
			"RetailEdge Cashier Expense",
			row.name,
			"branch",
			branch,
			update_modified=False,
		)
