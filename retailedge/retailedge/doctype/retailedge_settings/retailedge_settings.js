frappe.ui.form.on("RetailEdge Settings", {
	setup(frm) {
		frm.set_query("cashier_expense_posting_workflow_state", () => ({
			query: "retailedge.cashier_expense_posting.search_cashier_expense_posting_workflow_states",
		}));
		frm.set_query("business_expense_posting_workflow_state", () => ({
			query: "retailedge.business_expense_posting.search_business_expense_posting_workflow_states",
		}));
	},
	refresh(frm) {
		if (frm.page && frm.page.set_title) {
			frm.page.set_title(__("Settings"));
		}
	},
});
