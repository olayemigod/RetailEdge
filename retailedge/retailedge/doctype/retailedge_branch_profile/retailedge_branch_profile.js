frappe.ui.form.on("RetailEdge Branch Profile", {
	refresh(frm) {
		if (frm.page && frm.page.set_title) {
			frm.page.set_title(__("Branch Setup"));
		}
	},
});
