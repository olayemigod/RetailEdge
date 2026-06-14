frappe.ui.form.on("RetailEdge Bank Match Batch Job", {
	refresh(frm) {
		set_batch_job_indicator(frm);
		configure_batch_job_actions(frm);
	},
});

function configure_batch_job_actions(frm) {
	frm.clear_custom_buttons();
	if (!frm.doc || frm.is_new()) {
		return;
	}
	frm.add_custom_button(__("Refresh Progress"), () => refresh_batch_job_summary(frm, true));
	refresh_batch_job_summary(frm, false);
}

function refresh_batch_job_summary(frm, reloadAfter) {
	return frappe.call({
		method: "retailedge.api.refresh_bank_match_batch_job_progress",
		args: { batch_job_name: frm.doc.name },
		freeze: Boolean(reloadAfter),
		freeze_message: __("Refreshing progress..."),
		callback(r) {
			const summary = r.message || {};
			if (reloadAfter) {
				frm.reload_doc();
				return;
			}
			render_batch_job_action_buttons(frm, summary);
		},
	});
}

function render_batch_job_action_buttons(frm, summary) {
	if (summary.can_retry_failed) {
		frm.add_custom_button(__("Retry Failed Rows"), () => {
			frappe.prompt(
				[{ fieldname: "retry_reason", fieldtype: "Small Text", label: __("Retry Reason") }],
				(values) => {
					frappe.call({
						method: "retailedge.api.retry_bank_match_batch_job_rows",
						args: { batch_job_name: frm.doc.name, retry_reason: values.retry_reason || "Retry failed rows" },
						freeze: true,
						freeze_message: __("Queueing retry job..."),
						callback(r) {
							const result = r.message || {};
							if (result.batch_job) {
								frappe.show_alert({ message: result.message || __("Retry job queued."), indicator: "blue" });
								frappe.set_route("Form", "RetailEdge Bank Match Batch Job", result.batch_job);
							}
						},
					});
				},
				__("Retry Failed Rows"),
				__("Queue Retry")
			);
		}, __("Actions"));
	}

	if (summary.can_cancel) {
		frm.add_custom_button(__("Cancel Job"), () => {
			frappe.prompt(
				[{ fieldname: "reason", fieldtype: "Small Text", label: __("Cancellation Reason") }],
				(values) => {
					frappe.call({
						method: "retailedge.api.cancel_bank_match_batch_job",
						args: { batch_job_name: frm.doc.name, reason: values.reason || "Cancelled by user" },
						freeze: true,
						freeze_message: __("Cancelling job..."),
						callback(r) {
							const result = r.message || {};
							frappe.show_alert({ message: result.message || __("Batch job cancelled."), indicator: "gray" });
							frm.reload_doc();
						},
					});
				},
				__("Cancel Batch Job"),
				__("Cancel Job")
			);
		}, __("Actions"));
	}
}

function set_batch_job_indicator(frm) {
	const colors = {
		Queued: "orange",
		Running: "blue",
		Completed: "green",
		"Completed With Errors": "orange",
		Failed: "red",
		Cancelled: "gray",
	};
	frm.dashboard.clear_headline();
	frm.dashboard.set_headline(
		__("{0}% complete: {1} of {2} rows processed", [
			frm.doc.progress_percent || 0,
			frm.doc.processed_rows || 0,
			frm.doc.total_rows || 0,
		])
	);
	frm.dashboard.set_indicator(__(frm.doc.status || "Queued"), colors[frm.doc.status] || "gray");
}
