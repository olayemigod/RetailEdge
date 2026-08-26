frappe.listview_settings["RetailEdge Branch Profile"] = {
	onload(listview) {
		if (listview.page && listview.page.set_title) {
			listview.page.set_title(__("Branch Setup"));
		}
	},
};
