frappe.ui.form.on("RetailEdge Settings", {
	refresh(frm) {
		if (frm.page && frm.page.set_title) {
			frm.page.set_title(__("Settings"));
		}
	},
});
