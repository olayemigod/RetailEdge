frappe.ui.form.on("RetailEdge Statement Import Row", {
	refresh(frm) {
		frm.clear_custom_buttons();

		if (frm.is_new() || !should_show_accept_possible_duplicate(frm.doc)) {
			return;
		}

		frm.add_custom_button(__("Accept Possible Duplicate"), function () {
			frappe.prompt(
				[
					{
						fieldname: "acceptance_note",
						fieldtype: "Small Text",
						label: __("Acceptance Note"),
					},
				],
				function (values) {
					frappe.call({
						method: "retailedge.api.accept_possible_duplicate_statement_row",
						args: {
							row_name: frm.doc.name,
							acceptance_note: values.acceptance_note || "",
						},
						freeze: true,
						freeze_message: __("Accepting possible duplicate..."),
						callback: function (r) {
							const message =
								(r.message && r.message.reason) ||
								__("Possible duplicate accepted and imported safely.");
							frappe.msgprint({
								title: __("Possible Duplicate Accepted"),
								message: frappe.utils.escape_html(message),
								indicator: "green",
							});
							frm.reload_doc();
						},
					});
				},
				__("Accept Possible Duplicate"),
				__("Accept")
			);
		});
	},
});

function should_show_accept_possible_duplicate(doc) {
	const duplicateStatus = (doc.duplicate_status || "").trim();
	const importStatus = (doc.import_status || "").trim();
	return duplicateStatus === "Possible Duplicate" || importStatus === "Duplicate Suspected" || importStatus === "Skipped";
}
