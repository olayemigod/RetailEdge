frappe.ui.form.on("Supplier Document Extraction", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("View Intake"), () => {
			frappe.set_route("Form", "Supplier Document Intake", frm.doc.supplier_document_intake);
		});
		frm.add_custom_button(__("View Reviews"), () => {
			frappe.set_route("List", "Supplier Document Extraction Review", { extraction: frm.doc.name });
		});

		frappe.call({
			method: "retailedge.supplier_document_extraction.get_extraction_review_state",
			type: "GET",
			args: { extraction_name: frm.doc.name },
			callback(r) {
				if (!r.message || r.message.review_status !== "Pending Review") return;
				frm.add_custom_button(__("Accept Extraction"), () => review_extraction(frm, "Accepted"), __("Review"));
				frm.add_custom_button(__("Reject Extraction"), () => review_extraction(frm, "Rejected"), __("Review"));
			}
		});
	}
});

function review_extraction(frm, decision) {
	frappe.prompt(
		[
			{
				fieldname: "review_notes",
				fieldtype: "Small Text",
				label: __("Review Notes"),
				reqd: decision === "Rejected"
			}
		],
		(values) => {
			frappe.call({
				method: "retailedge.supplier_document_extraction.record_extraction_review",
				args: {
					extraction_name: frm.doc.name,
					decision,
					review_notes: values.review_notes || ""
				},
				freeze: true,
				freeze_message: __("Recording review…"),
				callback(r) {
					if (!r.message) return;
					frappe.show_alert({ message: __("Extraction review recorded"), indicator: "green" });
					frm.reload_doc();
				}
			});
		},
		__(decision === "Accepted" ? "Accept Extraction" : "Reject Extraction"),
		__(decision === "Accepted" ? "Accept" : "Reject")
	);
}
