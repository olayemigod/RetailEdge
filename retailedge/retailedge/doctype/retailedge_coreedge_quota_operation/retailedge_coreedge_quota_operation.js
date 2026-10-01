frappe.ui.form.on("RetailEdge CoreEdge Quota Operation", {
	refresh(frm) {
		frm.disable_save();
		add_source_document_action(frm);
		if (!can_reconcile_quota()) {
			return;
		}
		if (
			["Pending Finalize", "Needs Review"].includes(frm.doc.status) &&
			frm.doc.reservation_reference
		) {
			frm.add_custom_button(
				__("Retry CoreEdge Finalization"),
				() => prompt_reconciliation_reason(frm, "retry"),
				__("Reconciliation")
			);
		}
		if (
			frm.doc.status === "Needs Review" &&
			!frm.doc.reservation_reference &&
			frm.doc.reason_code === "FAIL_OPEN_UNRESERVED"
		) {
			frm.add_custom_button(
				__("Reconcile Current Quota Period"),
				() => prompt_reconciliation_reason(frm, "unreserved"),
				__("Reconciliation")
			);
		}
	},
});


function can_reconcile_quota() {
	const roles = new Set(frappe.user_roles || []);
	return (
		roles.has("System Manager") ||
		roles.has("RetailEdge Manager") ||
		roles.has("RetailEdgeManager")
	);
}


function add_source_document_action(frm) {
	if (!frm.doc.source_doctype || !frm.doc.source_name) {
		return;
	}
	frm.add_custom_button(__("Open Source Document"), () => {
		frappe.set_route("Form", frm.doc.source_doctype, frm.doc.source_name);
	});
}


function prompt_reconciliation_reason(frm, action) {
	frappe.prompt(
		[
			{
				fieldname: "reason",
				fieldtype: "Small Text",
				label: __("Reason"),
				reqd: 1,
			},
		],
		(values) => run_reconciliation(frm, action, values.reason),
		__("Quota Reconciliation"),
		__("Continue")
	);
}


function run_reconciliation(frm, action, reason) {
	const method =
		action === "unreserved"
			? "retailedge.coreedge_sales_quota_reconciliation.reconcile_unreserved_quota_operation"
			: "retailedge.coreedge_sales_quota_reconciliation.retry_quota_finalization";

	frappe.call({
		method,
		args: {
			operation_name: frm.doc.name,
			reason,
		},
		freeze: true,
		freeze_message: __("Reconciling CoreEdge quota..."),
		callback(r) {
			const result = r.message || {};
			const indicator = result.ok ? "green" : "orange";
			frappe.show_alert({
				message: result.ok
					? __("Quota reconciliation completed.")
					: __("Quota reconciliation still needs review."),
				indicator,
			});
			frm.reload_doc();
		},
	});
}
