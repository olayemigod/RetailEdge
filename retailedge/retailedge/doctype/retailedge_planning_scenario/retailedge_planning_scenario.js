frappe.ui.form.on("RetailEdge Planning Scenario", {
	setup(frm) {
		frm.set_query("branch", () => ({ filters: { company: frm.doc.company || "" } }));
	},
	company(frm) {
		if (frm.doc.branch) frm.set_value("branch", "");
	},
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Open Forecasting & Planning"), () => {
				frappe.route_options = { scenario: frm.doc.name, company: frm.doc.company, branch: frm.doc.branch || "" };
				frappe.set_route("forecasting-planning");
			});
		}
	},
});
