frappe.listview_settings["RetailEdge Cashier Expense"] = {
	add_fields: [
		"expense_status",
		"ledger_status",
		"posting_ready",
		"amount",
		"expense_category",
		"cashier",
		"expense_date",
		"pos_profile",
		"branch",
		"linked_pos_opening_shift",
		"docstatus",
	],
	get_indicator(doc) {
		if (doc.expense_status === "Pending Ledger") {
			return [__("Pending Ledger"), "orange", "expense_status,=,Pending Ledger"];
		}
		if (doc.expense_status === "Submitted") {
			return [__("Submitted"), "blue", "expense_status,=,Submitted"];
		}
		if (doc.expense_status === "Rejected") {
			return [__("Rejected"), "red", "expense_status,=,Rejected"];
		}
		if (doc.expense_status === "Posted") {
			return [__("Posted"), "green", "expense_status,=,Posted"];
		}
		if (doc.expense_status === "Cancelled") {
			return [__("Cancelled"), "gray", "expense_status,=,Cancelled"];
		}
		return [__("Draft"), "gray", "expense_status,=,Draft"];
	},
};
