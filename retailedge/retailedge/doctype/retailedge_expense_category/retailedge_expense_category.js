frappe.ui.form.on("RetailEdge Expense Category", {
	refresh(frm) {
		frm.set_query("expense_account", function () {
			return {
				filters: {
					company: frm.doc.company || "",
					root_type: "Expense",
					is_group: 0,
					disabled: 0,
				},
			};
		});

		frm.set_query("default_cost_center", function () {
			return {
				filters: {
					company: frm.doc.company || "",
					is_group: 0,
				},
			};
		});
	},

	company(frm) {
		if (frm.__retailedge_expense_category_company === undefined) {
			frm.__retailedge_expense_category_company = frm.doc.company || "";
			return;
		}
		const previousCompany = frm.__retailedge_expense_category_company;
		const nextCompany = frm.doc.company || "";
		frm.__retailedge_expense_category_company = nextCompany;
		if (previousCompany === nextCompany) {
			return;
		}
		frm.set_value("expense_account", null);
		frm.set_value("default_cost_center", null);
	},
});
