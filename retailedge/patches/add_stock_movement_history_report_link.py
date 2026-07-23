from __future__ import annotations

import frappe


WORKSPACE_NAME = "RetailEdge"
REPORT_NAME = "RetailEdge Stock Movement History"
SECTION_NAME = "Reports & Insights"


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE_NAME) or not frappe.db.exists("Report", REPORT_NAME):
		return

	workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
	links = [row.as_dict(no_nulls=True) for row in workspace.links or []]
	if any(row.get("type") == "Link" and row.get("link_to") == REPORT_NAME for row in links):
		return

	insert_at = None
	section_index = None
	for index, row in enumerate(links):
		if row.get("type") == "Card Break" and row.get("label") == SECTION_NAME:
			section_index = index
			continue
		if section_index is not None:
			if row.get("type") == "Card Break":
				break
			if row.get("type") == "Link" and row.get("link_to") == "Stock Ledger":
				insert_at = index + 1
				break

	if section_index is None:
		links.append(
			{
				"type": "Card Break",
				"label": SECTION_NAME,
				"link_type": "Report",
				"link_count": 0,
				"hidden": 0,
				"is_query_report": 0,
				"onboard": 0,
				"close": 1,
			}
		)
		insert_at = len(links)
	elif insert_at is None:
		insert_at = section_index + 1
		while insert_at < len(links) and links[insert_at].get("type") != "Card Break":
			insert_at += 1

	links.insert(
		insert_at,
		{
			"type": "Link",
			"label": "Stock Movement History",
			"link_to": REPORT_NAME,
			"link_type": "Report",
			"link_count": 0,
			"hidden": 0,
			"is_query_report": 1,
			"onboard": 0,
		},
	)
	_recount_links(links)
	workspace.set("links", links)
	workspace.save(ignore_permissions=True)

	try:
		from retailedge.patches.sync_retailedge_workspace import _sync_workspace_sidebar

		_sync_workspace_sidebar(workspace)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "RetailEdge Stock Movement History workspace sidebar sync")

	frappe.clear_cache(doctype="Workspace")


def _recount_links(links):
	current_card = None
	for row in links:
		if row.get("type") == "Card Break":
			row["link_count"] = 0
			current_card = row
		elif row.get("type") == "Link" and current_card is not None:
			current_card["link_count"] = int(current_card.get("link_count") or 0) + 1
