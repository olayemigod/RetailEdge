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
			frm.doc.reason_code === "FAIL_OPEN_UNRESERVED" &&
			!frm.doc.reconciliation_case_reference
		) {
			frm.add_custom_button(
				__("Submit to CoreEdge Review"),
				() => prompt_reconciliation_reason(frm, "submit_review"),
				__("Reconciliation")
			);
		}
		if (
			frm.doc.status === "Needs Review" &&
			frm.doc.reconciliation_case_reference
		) {
			frm.add_custom_button(
				__("Refresh CoreEdge Review Status"),
				() => prompt_reconciliation_reason(frm, "refresh_status"),
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
	let method =
		"retailedge.coreedge_sales_quota_reconciliation.retry_quota_finalization";
	if (action === "submit_review") {
		method =
			"retailedge.coreedge_sales_quota_reconciliation.submit_unreserved_quota_reconciliation_case";
	} else if (action === "refresh_status") {
		method =
			"retailedge.coreedge_sales_quota_reconciliation.refresh_reconciliation_case_status";
	}

	frappe.call({
		method,
		args: {
			operation_name: frm.doc.name,
			reason,
		},
		freeze: true,
		freeze_message:
			action === "submit_review"
				? __("Submitting evidence to CoreEdge review...")
				: action === "refresh_status"
					? __("Refreshing CoreEdge review status...")
					: __("Reconciling CoreEdge quota..."),
		callback(r) {
			const result = r.message || {};
			let indicator = "orange";
			let message = __("Quota reconciliation still needs review.");
			if (result.status === "Resolved") {
				indicator = "green";
				message = __("CoreEdge usage review is resolved.");
			} else if (result.status === "Rejected") {
				indicator = "red";
				message = __("CoreEdge rejected the submitted usage evidence.");
			} else if (
				action === "submit_review" &&
				result.reconciliation_case_reference
			) {
				indicator = "blue";
				message = __("CoreEdge reconciliation case submitted for platform review.");
			} else if (action === "refresh_status" && result.reconciliation_case_status === "Open") {
				indicator = "orange";
				message = __("CoreEdge review is still open.");
			} else if (result.status === "Finalized") {
				indicator = "green";
				message = __("Quota reconciliation completed.");
			} else if (result.status === "Pending Finalize") {
				indicator = "blue";
				message = __("Quota reservation is pending finalization.");
			}
			frappe.show_alert({ message, indicator });
			frm.reload_doc();
		},
	});
}
