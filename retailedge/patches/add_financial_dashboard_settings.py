import frappe


FIELDS = (
	{
		"fieldname": "financial_dashboard_settings_section",
		"label": "Financial Dashboard",
		"fieldtype": "Section Break",
		"insert_after": "business_hub_variance_tolerance",
	},
	{
		"fieldname": "financial_dashboard_comparison_mode",
		"label": "Default Comparison",
		"fieldtype": "Select",
		"options": "Previous Period\nOff",
		"default": "Previous Period",
		"description": (
			"Controls the dashboard's initial comparison view. Users may switch comparison off for a session. "
			"This setting never changes financial definitions."
		),
		"insert_after": "financial_dashboard_settings_section",
	},
	{
		"fieldname": "financial_dashboard_composition_dimension",
		"label": "Default Revenue Composition",
		"fieldtype": "Select",
		"options": "Item Group\nBrand\nBranch",
		"default": "Item Group",
		"description": (
			"Selects the default authorised dimension for the Revenue Composition panel. "
			"Unavailable or unattributed dimensions remain explicitly unavailable."
		),
		"insert_after": "financial_dashboard_comparison_mode",
	},
	{
		"fieldname": "financial_dashboard_show_collection",
		"label": "Show Collection Performance",
		"fieldtype": "Check",
		"default": "1",
		"description": "Shows collection and invoice-cohort measures that are supported by the current financial contract.",
		"insert_after": "financial_dashboard_composition_dimension",
	},
	{
		"fieldname": "financial_dashboard_show_financial_health",
		"label": "Show Financial Health",
		"fieldtype": "Check",
		"default": "1",
		"description": "Shows permitted accounting and transactional health measures. Cost restrictions still apply.",
		"insert_after": "financial_dashboard_show_collection",
	},
	{
		"fieldname": "financial_dashboard_show_outstanding",
		"label": "Show Outstanding Insights",
		"fieldtype": "Check",
		"default": "1",
		"description": "Shows current customer and supplier outstanding summaries from their governed registers.",
		"insert_after": "financial_dashboard_show_financial_health",
	},
)


def execute():
	if not frappe.db.exists("DocType", "RetailEdge Settings"):
		return

	changed = False
	for field in FIELDS:
		name = f"RetailEdge Settings-{field['fieldname']}"
		if frappe.db.exists("Custom Field", name):
			continue
		frappe.get_doc({"doctype": "Custom Field", "dt": "RetailEdge Settings", **field}).insert()
		changed = True

	if changed:
		frappe.clear_cache(doctype="RetailEdge Settings")
