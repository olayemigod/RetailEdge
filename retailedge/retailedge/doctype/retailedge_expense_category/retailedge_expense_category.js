frappe.ui.form.on("RetailEdge Expense Category", {
	refresh(frm) {
		frm.set_query("expense_account", function () {
			return {
				filters: {
					company: frm.doc.company || "",
				},
			};
		});

		frm.set_query("default_cost_center", function () {
			return {
				filters: {
					company: frm.doc.company || "",
				},
			};
		});
	},
});
