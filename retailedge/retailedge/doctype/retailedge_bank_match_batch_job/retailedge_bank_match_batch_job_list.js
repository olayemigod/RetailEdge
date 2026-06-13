frappe.listview_settings["RetailEdge Bank Match Batch Job"] = {
	add_fields: [
		"status",
		"action_type",
		"progress_percent",
		"total_rows",
		"processed_rows",
		"failed_count",
		"created_count",
		"confirmed_count",
		"already_exists_count",
		"started_by",
		"started_on",
		"completed_on",
	],
	get_indicator(doc) {
		const status = doc.status || "Queued";
		const colors = {
			Queued: "orange",
			Running: "blue",
			Completed: "green",
			"Completed With Errors": "orange",
			Failed: "red",
			Cancelled: "gray",
		};
		return [__(status), colors[status] || "gray", `status,=,${status}`];
	},
};
