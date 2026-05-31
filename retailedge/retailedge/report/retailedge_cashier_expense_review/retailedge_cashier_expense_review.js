function applyRetailEdgeSummaryCardDesign() {
	// Report summary cards are styled through native Frappe DOM selectors in CSS.
}

function scheduleRetailEdgeSummaryCardDesign() {
	// No-op: report summary card appearance is CSS-only.
}

frappe.query_reports["RetailEdge Cashier Expense Review"] = {
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
			fieldname: "linked_pos_opening_shift",
			label: __("Opening Shift"),
			fieldtype: "Link",
			options: "POS Opening Shift",
		},
		{
			fieldname: "linked_pos_closing_shift",
			label: __("Closing Shift"),
			fieldtype: "Link",
			options: "POS Closing Shift",
		},
		{
			fieldname: "expense_category",
			label: __("Expense Category"),
			fieldtype: "Link",
			options: "RetailEdge Expense Category",
		},
		{
			fieldname: "expense_status",
			label: __("Expense Status"),
			fieldtype: "Select",
			options: "\nDraft\nSubmitted\nPending Ledger\nRejected\nPosted\nCancelled",
		},
		{
			fieldname: "ledger_status",
			label: __("Ledger Status"),
			fieldtype: "Select",
			options: "\nNot Applicable\nPending Ledger\nPosted\nFailed",
		},
		{
			fieldname: "daily_audit_inclusion_status",
			label: __("Daily Audit Inclusion Status"),
			fieldtype: "Select",
			options: "\nPending Review\nIncluded\nExcluded\nNeeds Clarification",
		},
		{
			fieldname: "daily_audit_classification",
			label: __("Daily Audit Classification"),
			fieldtype: "Select",
			options: "\nCash Expense\nCash Shortage Explanation\nCash Overage Explanation\nReimbursement Pending\nInvalid / Duplicate\nOther",
		},
		{
			fieldname: "posting_ready",
			label: __("Posting Ready"),
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
