frappe.listview_settings["RetailEdge Daily Sales Audit"] = {
	add_fields: ["audit_status", "audit_result", "review_required", "cash_variance_amount"],
	get_indicator(doc) {
		const status = doc.audit_status || "Draft";
		if (status === "Ready for Review") {
			return [__("Ready for Review"), "blue", "audit_status,=,Ready for Review"];
		}
		if (status === "In Review") {
			return [__("In Review"), "orange", "audit_status,=,In Review"];
		}
		if (status === "Variance Found") {
			return [__("Variance Found"), "red", "audit_status,=,Variance Found"];
		}
		if (status === "Approved") {
			return [__("Approved"), "green", "audit_status,=,Approved"];
		}
		if (status === "Rejected") {
			return [__("Rejected"), "red", "audit_status,=,Rejected"];
		}
		if (status === "Cancelled") {
			return [__("Cancelled"), "gray", "audit_status,=,Cancelled"];
		}
		return [__("Draft"), "gray", "audit_status,=,Draft"];
	},
};

