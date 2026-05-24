frappe.query_reports["RetailEdge Bank Transaction Matching"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "bank_account",
			label: __("Bank Account"),
			fieldtype: "Link",
			options: "Bank Account",
		},
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "match_confidence",
			label: __("Match Confidence"),
			fieldtype: "Select",
			options: "\nStrong Match\nPossible Match\nWeak Match\nNo Match",
		},
		{
			fieldname: "only_unmatched",
			label: __("Only Unmatched"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "include_reconciled",
			label: __("Include Reconciled"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "include_verified_invoices",
			label: __("Include Verified Invoices"),
			fieldtype: "Check",
			default: 0,
		},
	],
};

