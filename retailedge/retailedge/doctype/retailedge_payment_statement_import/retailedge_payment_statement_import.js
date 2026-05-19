frappe.ui.form.on("RetailEdge Payment Statement Import", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Preview Statement Rows"), async () => {
			if (!frm.doc.mapping_template || !frm.doc.attachment) {
				frappe.msgprint(__("Select a mapping template and upload a statement attachment first."));
				return;
			}
			const response = await frappe.call({
				method: "retailedge.api.preview_payment_statement_import_rows",
				args: { import_name: frm.doc.name },
			});
			const payload = response.message || {};
			const preview_count = payload.row_count || 0;
			const sample_count = payload.sample_row_count || preview_count;
			const error_count = (payload.errors || []).length;
			const duplicate_summary = payload.duplicate_summary || {};
			frappe.msgprint(
				__(
					"Preview generated: {0} normalized row(s), showing {1}. Unique: {2}, Duplicate Suspected: {3}, Rejected Duplicates: {4}. Errors: {5}.{6}",
					[
						preview_count,
						sample_count,
						duplicate_summary.unique_count || 0,
						duplicate_summary.duplicate_suspected_count || 0,
						duplicate_summary.rejected_duplicate_count || 0,
						error_count,
						payload.truncated ? " Large previews are summarized to keep the form responsive." : "",
					]
				)
			);
		});

		frm.add_custom_button(__("Import Statement Rows"), async () => {
			if (!frm.doc.mapping_template || !frm.doc.attachment) {
				frappe.msgprint(__("Select a mapping template and upload a statement attachment first."));
				return;
			}
			const response = await frappe.call({
				method: "retailedge.api.import_payment_statement_rows",
				args: {
					import_name: frm.doc.name,
					replace_rows: 1,
				},
			});
			const payload = response.message || {};
			await frm.reload_doc();
			frappe.msgprint(
				__(
					"Imported {0} statement row(s). Open the matching report for detailed row review; the import form now keeps only summary counters to stay responsive.",
					[payload.imported_row_count || 0]
				)
			);
		});
	},
});
