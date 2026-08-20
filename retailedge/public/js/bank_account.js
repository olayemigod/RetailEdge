frappe.ui.form.on("Bank Account", {
	setup(frm) {
		if (!frm.fields_dict.retailedge_branch) return;
		frm.set_query("retailedge_branch", () => ({
			filters: frm.doc.company ? { company: frm.doc.company } : {},
		}));
	},

	async company(frm) {
		if (!frm.fields_dict.retailedge_branch || !frm.doc.retailedge_branch || !frm.doc.company) return;
		const branch = await frappe.db.get_value("Branch", frm.doc.retailedge_branch, "company");
		const branchCompany = branch?.message?.company;
		if (branchCompany && branchCompany !== frm.doc.company) {
			await frm.set_value("retailedge_branch", "");
			frappe.show_alert({
				message: __("RetailEdge Branch was cleared because it does not belong to the selected Company."),
				indicator: "orange",
			});
		}
	},
});
