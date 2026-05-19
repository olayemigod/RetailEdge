frappe.listview_settings["RetailEdge Payment Statement Import"] = {
	add_fields: [
		"company",
		"branch",
		"statement_date",
		"statement_type",
		"payment_category",
		"import_status",
		"imported_row_count",
		"rejected_duplicate_count",
	],
	get_indicator(doc) {
		const status = doc.import_status || "Draft";
		if (status === "Imported") {
			return [__("Imported"), "green", "import_status,=,Imported"];
		}
		if (status === "Reviewed") {
			return [__("Reviewed"), "blue", "import_status,=,Reviewed"];
		}
		if (status === "Archived") {
			return [__("Archived"), "gray", "import_status,=,Archived"];
		}
		return [__("Draft"), "orange", "import_status,=,Draft"];
	},
};
