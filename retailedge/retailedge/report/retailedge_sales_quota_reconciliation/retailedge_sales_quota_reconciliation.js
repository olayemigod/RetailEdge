frappe.query_reports["RetailEdge Sales Quota Reconciliation"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
			get_query() {
				const company = frappe.query_report.get_filter_value("company");
				return company
					? {
						query: "retailedge.operating_context.search_operating_branches",
						filters: { company },
					}
					: {};
			},
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nNeeds Review\nPending Finalize\nFinalized",
		},
		{
			fieldname: "source_doctype",
			label: __("Source Type"),
			fieldtype: "Select",
			options: "\nSales Invoice\nPOS Invoice",
		},
		{
			fieldname: "reason_code",
			label: __("Reason Code"),
			fieldtype: "Data",
		},
		{
			fieldname: "from_date",
			label: __("Date From"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("Date To"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "include_finalized",
			label: __("Include Finalized"),
			fieldtype: "Check",
			default: 0,
		},
	],
};
