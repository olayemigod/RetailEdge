import frappe


FIELDS = (
	{
		"fieldname": "business_hub_intelligence_section",
		"label": "Business Hub Intelligence",
		"fieldtype": "Section Break",
		"insert_after": "enable_reporting_export",
	},
	{
		"fieldname": "business_hub_variance_tolerance",
		"label": "Business Hub Variance Tolerance",
		"fieldtype": "Currency",
		"default": "0",
		"description": (
			"Cash-shift and branch audit variances at or below this absolute amount are treated as within tolerance "
			"by Business Hub. This affects prioritisation only and never changes accounting or audit records."
		),
		"insert_after": "business_hub_intelligence_section",
	},
)


def execute():
	if not frappe.db.exists("DocType", "RetailEdge Settings"):
		return

	for field in FIELDS:
		name = f"RetailEdge Settings-{field['fieldname']}"
		if frappe.db.exists("Custom Field", name):
			continue
		frappe.get_doc({"doctype": "Custom Field", "dt": "RetailEdge Settings", **field}).insert()
