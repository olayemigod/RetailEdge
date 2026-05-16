frappe.listview_settings["RetailEdge Cashier Expense"] = {
	add_fields: [
		"expense_status",
		"ledger_status",
		"daily_audit_inclusion_status",
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
		const effectiveStatus = get_effective_review_status(doc);
		if (effectiveStatus === "Pending Ledger") {
			return [__("Review: Pending Ledger"), "orange", "expense_status,=,Pending Ledger"];
		}
		if (effectiveStatus === "Submitted") {
			return [__("Review: Submitted"), "blue", "expense_status,=,Submitted"];
		}
		if (effectiveStatus === "Rejected") {
			return [__("Review: Rejected"), "red", "expense_status,=,Rejected"];
		}
		if (effectiveStatus === "Posted") {
			return [__("Review: Posted"), "green", "expense_status,=,Posted"];
		}
		if (effectiveStatus === "Cancelled") {
			return [__("Review: Cancelled"), "gray", "expense_status,=,Cancelled"];
		}
		return [__("Review: Draft"), "gray", "expense_status,=,Draft"];
	},
};

function get_effective_review_status(doc) {
	if (doc.docstatus === 2 || doc.expense_status === "Cancelled") {
		return "Cancelled";
	}
	if (doc.docstatus === 1 && (!doc.expense_status || doc.expense_status === "Draft")) {
		return "Submitted";
	}
	return doc.expense_status || "Draft";
}
