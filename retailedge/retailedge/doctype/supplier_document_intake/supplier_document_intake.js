frappe.ui.form.on("Supplier Document Intake", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Record Extracted Fields"), () => record_extracted_fields(frm), __("Extraction"));
		frm.add_custom_button(__("View Extractions"), () => {
			frappe.set_route("List", "Supplier Document Extraction", { supplier_document_intake: frm.doc.name });
		}, __("Extraction"));
	}
});

function record_extracted_fields(frm) {
	frappe.prompt(
		[
			{ fieldname: "document_number", fieldtype: "Data", label: __("Document Number") },
			{ fieldname: "document_date", fieldtype: "Date", label: __("Document Date") },
			{ fieldname: "currency", fieldtype: "Link", options: "Currency", label: __("Currency") },
			{ fieldname: "subtotal", fieldtype: "Currency", label: __("Subtotal") },
			{ fieldname: "tax_amount", fieldtype: "Currency", label: __("Tax Amount") },
			{ fieldname: "total", fieldtype: "Currency", label: __("Total") },
			{ fieldname: "purchase_order_reference", fieldtype: "Data", label: __("Purchase Order Reference Found in Document") }
		],
		(values) => {
			frappe.call({
				method: "retailedge.supplier_document_extraction.record_manual_extraction",
				args: {
					intake_name: frm.doc.name,
					document_number: values.document_number || "",
					document_date: values.document_date || "",
					currency: values.currency || "",
					subtotal: values.subtotal,
					tax_amount: values.tax_amount,
					total: values.total,
					purchase_order_reference: values.purchase_order_reference || ""
				},
				freeze: true,
				freeze_message: __("Recording extraction…"),
				callback(r) {
					if (!r.message) return;
					frappe.set_route("Form", "Supplier Document Extraction", r.message.extraction);
				}
			});
		},
		__("Record Extracted Fields"),
		__("Record")
	);
}
