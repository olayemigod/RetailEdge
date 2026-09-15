from __future__ import annotations

import frappe


APP_NAME = "retailedge"
DESKTOP_LABEL = "PEdge Retail"
DESKTOP_ROUTE = "/desk/retailedge-business-hub"
DESKTOP_LOGO = "/assets/retailedge/images/processedge_retail/pedge-retail-app-icon-dark.png"
LEGACY_LABELS = {"RetailEdge", "ProcessEdge Retail"}
WORKSPACE_NAME = "RetailEdge"


def sync_retailedge_desktop_identity():
	"""Keep the Frappe desktop launcher aligned with the Retail product identity.

	Frappe creates App desktop icons only once. Changing hooks later does not
	update an existing icon, while a Workspace desktop icon can continue routing
	to a generated workspace slug. This reconciles both cases without renaming
	the RetailEdge workspace, module, DocTypes, routes, or other internal IDs.
	"""

	app_icons = frappe.get_all(
		"Desktop Icon",
		filters={"app": APP_NAME, "icon_type": "App"},
		fields=["name", "label", "idx", "hidden"],
		order_by="idx asc, creation asc",
	)
	canonical_name = frappe.db.exists("Desktop Icon", DESKTOP_LABEL)
	created = False

	if canonical_name:
		icon = frappe.get_doc("Desktop Icon", canonical_name)
		if icon.icon_type != "App" or icon.app != APP_NAME:
			frappe.throw(
				f"Desktop Icon '{DESKTOP_LABEL}' is already used by another desktop entry."
			)
	else:
		icon = frappe.new_doc("Desktop Icon")
		icon.label = DESKTOP_LABEL
		icon.icon_type = "App"
		icon.app = APP_NAME
		icon.idx = app_icons[0].idx if app_icons else 0
		icon.link_type = "External"
		icon.link = DESKTOP_ROUTE
		icon.logo_url = DESKTOP_LOGO
		icon.hidden = 0
		icon.insert(ignore_permissions=True)
		canonical_name = icon.name
		created = True

	updates = {
		"label": DESKTOP_LABEL,
		"icon_type": "App",
		"app": APP_NAME,
		"link_type": "External",
		"link": DESKTOP_ROUTE,
		"logo_url": DESKTOP_LOGO,
		"hidden": 0,
		"parent_icon": None,
	}
	changed = False
	for fieldname, value in updates.items():
		if getattr(icon, fieldname, None) != value:
			setattr(icon, fieldname, value)
			changed = True
	if changed:
		icon.save(ignore_permissions=True)

	hidden_duplicates = []
	for row in frappe.get_all(
		"Desktop Icon",
		filters={"app": APP_NAME, "icon_type": "App"},
		fields=["name", "hidden"],
	):
		if row.name == canonical_name or row.hidden:
			continue
		frappe.db.set_value("Desktop Icon", row.name, "hidden", 1, update_modified=False)
		hidden_duplicates.append(row.name)

	hidden_workspace_icons = []
	for row in frappe.get_all(
		"Desktop Icon",
		filters={
			"icon_type": "Link",
			"link_type": "Workspace Sidebar",
			"link_to": WORKSPACE_NAME,
		},
		fields=["name", "label", "parent_icon", "hidden"],
	):
		if row.parent_icon or row.hidden or row.label not in LEGACY_LABELS:
			continue
		frappe.db.set_value("Desktop Icon", row.name, "hidden", 1, update_modified=False)
		hidden_workspace_icons.append(row.name)

	# Frappe caches the desktop grid and boot payload independently. Purge both
	# after reconciliation so the corrected launcher appears after migrate.
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")

	return {
		"desktop_icon": canonical_name,
		"created": created,
		"updated": changed,
		"hidden_duplicate_app_icons": hidden_duplicates,
		"hidden_legacy_workspace_icons": hidden_workspace_icons,
		"route": DESKTOP_ROUTE,
		"logo": DESKTOP_LOGO,
	}
