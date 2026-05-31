function applyRetailEdgeSummaryCardDesign() {
	// Report summary cards are styled through native Frappe DOM selectors in CSS.
}

function scheduleRetailEdgeSummaryCardDesign() {
	// No-op: report summary card appearance is CSS-only.
}

frappe.query_reports["RetailEdge Cash Shift Verification"] = {
	after_refresh(report) {
		scheduleRetailEdgeSummaryCardDesign(report);
	},

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
			fieldname: "pos_profile",
			label: __("POS Profile"),
			fieldtype: "Link",
			options: "POS Profile",
		},
		{
			fieldname: "cashier",
			label: __("Cashier"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "cash_status",
			label: __("Cash Status"),
			fieldtype: "Select",
			options: "\nBalanced\nShortage\nOverage\nNeeds Review\nMissing Closing Shift\nMissing Opening Shift",
		},
		{
			fieldname: "review_status",
			label: __("Review Status"),
			fieldtype: "Select",
			options: "\nDraft\nReady for Review\nIn Review\nBalanced\nVariance Found\nClarification Required\nApproved\nRejected\nCancelled\nReopened",
		},
		{
			fieldname: "only_unsynced",
			label: __("Only Unsynced"),
			fieldtype: "Check",
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
