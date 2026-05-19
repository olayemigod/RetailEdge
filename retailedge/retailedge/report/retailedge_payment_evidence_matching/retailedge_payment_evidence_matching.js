frappe.query_reports["RetailEdge Payment Evidence Matching"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "sales_invoice",
			label: __("Sales Invoice"),
			fieldtype: "Link",
			options: "Sales Invoice",
		},
		{
			fieldname: "payment_category",
			label: __("Payment Category"),
			fieldtype: "Select",
			options: "\nCash\nBank Transfer\nCard / POS\nMobile Money\nOther",
		},
		{
			fieldname: "match_confidence",
			label: __("Match Confidence"),
			fieldtype: "Select",
			options: "\nLow\nMedium\nHigh",
		},
		{
			fieldname: "match_status",
			label: __("Match Status"),
			fieldtype: "Select",
			options: "\nCandidate\nStrong Candidate\nWeak Candidate\nDuplicate Suspected\nNo Match\nIgnored",
		},
		{
			fieldname: "only_unmatched",
			label: __("Only Unmatched"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "only_duplicates",
			label: __("Only Duplicates"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
};
