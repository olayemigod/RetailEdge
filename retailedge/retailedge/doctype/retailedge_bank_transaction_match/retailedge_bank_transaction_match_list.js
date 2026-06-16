frappe.listview_settings["RetailEdge Bank Transaction Match"] = {
	add_fields: [
		"decision_status",
		"review_status",
		"match_confidence",
		"risk_level",
		"transaction_date",
		"branch",
		"bank_account",
		"company",
		"suggested_document_type",
		"suggested_document",
		"execution_status",
		"executed_by",
		"executed_on",
		"dry_run_status_at_execution",
		"gate_status_at_execution",
		"execution_reference",
	],

	get_indicator(doc) {
		const executionStatus = doc.execution_status || "Not Executed";
		if (executionStatus && executionStatus !== "Not Executed") {
			const executionIndicators = {
				Executed: "green",
				Failed: "red",
				Blocked: "orange",
				"Already Handled": "gray",
			};
			return [__(executionStatus), executionIndicators[executionStatus] || "gray", `execution_status,=,${executionStatus}`];
		}
		const status = doc.review_status || doc.decision_status || "Pending Review";
		const indicators = {
			"Needs Review": "orange",
			"Pending Review": "orange",
			"Ready to Confirm": "green",
			Confirmed: "blue",
			Rejected: "red",
			Cancelled: "gray",
			Reopened: "yellow",
		};
		return [__(status), indicators[status] || "gray", `review_status,=,${status}`];
	},

	onload(listview) {
		listview.page.add_inner_button(__("Review Queue Summary"), function () {
			show_bank_match_queue_summary(listview);
		});

		listview.page.add_inner_button(__("Open Batch Jobs"), function () {
			frappe.set_route("List", "RetailEdge Bank Match Batch Job");
		});



		listview.page.add_actions_menu_item(__("Check Execution Readiness"), function () {
			const rows = listview.get_checked_items() || [];
			const names = rows.map((row) => row.name).filter(Boolean);
			if (!names.length) {
				frappe.msgprint(__("Select one or more confirmed Bank Match Review records first."));
				return;
			}
			const unconfirmed = rows.filter((row) => (row.decision_status || row.review_status) !== "Confirmed");
			if (unconfirmed.length) {
				frappe.msgprint(__("Execution readiness can only be checked for confirmed Bank Match Review records."));
				return;
			}
			frappe.call({
				method: "retailedge.api.check_reconciliation_execution_gate_for_matches",
				args: { match_names: JSON.stringify(names) },
				freeze: true,
				freeze_message: __("Checking execution gate..."),
				callback: function (r) {
					show_reconciliation_gate_summary(r.message);
				},
			});
		});

		listview.page.add_actions_menu_item(__("Dry Run Selected"), function () {
			const rows = listview.get_checked_items() || [];
			const names = rows.map((row) => row.name).filter(Boolean);
			if (!names.length) {
				frappe.msgprint(__("Select one or more confirmed Bank Match Review records first."));
				return;
			}
			const unconfirmed = rows.filter((row) => (row.decision_status || row.review_status) !== "Confirmed");
			if (unconfirmed.length) {
				frappe.msgprint(__("Dry Run Selected is only available for confirmed Bank Match Review records."));
				return;
			}
			frappe.call({
				method: "retailedge.api.dry_run_reconciliation_for_matches",
				args: { match_names: JSON.stringify(names) },
				freeze: true,
				freeze_message: __("Checking reconciliation readiness..."),
				callback: function (r) {
					show_reconciliation_dry_run_summary(r.message);
				},
			});
		});

		listview.page.add_actions_menu_item(__("Preview Bulk Confirm"), function () {
			const names = get_selected_bank_match_names(listview);
			if (!names.length) {
				frappe.msgprint(__("Select one or more Bank Match Review records first."));
				return;
			}
			preview_bulk_confirm_bank_matches(names, false, listview);
		});

		listview.page.add_actions_menu_item(__("Bulk Confirm Selected"), function () {
			const names = get_selected_bank_match_names(listview);
			if (!names.length) {
				frappe.msgprint(__("Select one or more Bank Match Review records first."));
				return;
			}
			preview_bulk_confirm_bank_matches(names, true, listview);
		});

		listview.page.add_actions_menu_item(__("Bulk Mark Needs Review"), function () {
			const names = get_selected_bank_match_names(listview);
			if (!names.length) {
				frappe.msgprint(__("Select one or more Bank Match Review records first."));
				return;
			}
			frappe.prompt(
				[
					{
						fieldname: "remarks",
						fieldtype: "Small Text",
						label: __("Remarks"),
					},
				],
				function (values) {
					frappe.call({
						method: "retailedge.api.bulk_mark_bank_transaction_matches_needs_review",
						args: {
							match_names: JSON.stringify(names),
							remarks: values.remarks || "",
						},
						freeze: true,
						freeze_message: __("Marking selected matches for review..."),
						callback: function (r) {
							show_bulk_bank_match_result(r.message, __("Bulk Needs Review Summary"));
							listview.refresh();
						},
					});
				},
				__("Bulk Mark Needs Review"),
				__("Apply")
			);
		});
	},
};


function show_bank_match_batch_job_queued(result) {
	frappe.msgprint({
		title: __("Bank Match Batch Job Queued"),
		indicator: "blue",
		message: `<p>${frappe.utils.escape_html((result && result.message) || __("Bank Match Batch Job has been queued."))}</p>
			${result && result.batch_job ? `<p><a href="/app/retailedge-bank-match-batch-job/${encodeURIComponent(result.batch_job)}">${frappe.utils.escape_html(result.batch_job)}</a></p>` : ""}`,
	});
}

function should_run_bank_match_background(names) {
	return (names || []).length > 200;
}

function confirm_large_bank_match_bulk_action(names, callback) {
	if (!should_run_bank_match_background(names)) {
		callback(false);
		return;
	}
	frappe.confirm(
		__(
			"You selected {0} records. This exceeds the safe live-processing limit of 200. Run this as a background job?",
			[names.length]
		),
		function () {
			callback(true);
		}
	);
}

function get_selected_bank_match_names(listview) {
	return (listview.get_checked_items() || []).map((row) => row.name).filter(Boolean);
}

function preview_bulk_confirm_bank_matches(names, confirmAfterPreview, listview) {
	frappe.call({
		method: "retailedge.api.preview_bulk_confirm_bank_transaction_matches",
		args: {
			match_names: JSON.stringify(names),
		},
		freeze: true,
		freeze_message: __("Checking selected matches..."),
		callback: function (r) {
			const result = r.message || {};
			show_bulk_bank_match_result(result, __("Bulk Confirm Preview"));
			if (!confirmAfterPreview || !result.eligible_count) {
				return;
			}
			frappe.confirm(
				__(
					"You are about to confirm selected RetailEdge bank match records. This will not reconcile Bank Transactions, create Payment Entries, post GL, or update Sales Invoice accounting fields. It only updates RetailEdge match decisions."
				),
				function () {
					frappe.prompt(
						[
							{
								fieldname: "remarks",
								fieldtype: "Small Text",
								label: __("Remarks"),
							},
						],
						function (values) {
							confirm_large_bank_match_bulk_action(names, function (runBackground) {
								frappe.call({
									method: "retailedge.api.bulk_confirm_bank_transaction_matches",
									args: {
										match_names: JSON.stringify(names),
										remarks: values.remarks || "",
										run_background: runBackground ? 1 : 0,
									},
									freeze: !runBackground,
									freeze_message: __("Confirming eligible matches..."),
									callback: function (confirmResponse) {
										const confirmResult = confirmResponse.message || {};
										if (confirmResult.status === "queued" || confirmResult.batch_job) {
											show_bank_match_batch_job_queued(confirmResult);
										} else {
											show_bulk_bank_match_result(confirmResult, __("Bulk Confirm Summary"));
											listview.refresh();
										}
									},
								});
							});
						},
						__("Bulk Confirm Selected"),
						__("Confirm")
					);
				}
			);
		},
	});
}

function show_bulk_bank_match_result(result, title) {
	if (!result) {
		frappe.msgprint({
			title,
			message: __("No result returned."),
			indicator: "orange",
		});
		return;
	}
	const rows = [
		[__("Total Selected"), result.total_selected || 0],
		[__("Eligible"), result.eligible_count || result.confirmed_count || 0],
		[__("Blocked / Skipped"), result.blocked_count || result.skipped_count || 0],
		[__("Unsafe"), result.unsafe_count || 0],
		[__("Already Confirmed"), result.already_confirmed_count || 0],
		[__("Duplicate Blocked"), result.duplicate_blocked_count || 0],
		[__("Weak / Needs Review"), result.weak_needs_review_count || 0],
		[__("Warnings"), result.warning_count || 0],
	];
	const blocked = (result.blocked || [])
		.slice(0, 10)
		.map((row) => `${row.name || ""}: ${row.reason || ""}`);
	const ui = window.retailedge && window.retailedge.ui;
	frappe.msgprint({
		title,
		message:
			ui && ui.renderCardGrid
				? `<div class="retailedge-dialog-content">
						${ui.renderCardGrid([
							{
								title: __("Selected Matches"),
								value: String(result.total_selected || 0),
								badge: result.confirmed_count ? __("Matched") : __("Needs Review"),
								tone: result.confirmed_count ? "success" : "warning",
								meta: [
									`${__("Eligible")}: ${result.eligible_count || result.confirmed_count || 0}`,
									`${__("Blocked / Skipped")}: ${result.blocked_count || result.skipped_count || 0}`,
								],
								footer: __("RetailEdge updates only review decisions here."),
							},
							{
								title: __("Risk Signals"),
								value: String((result.unsafe_count || 0) + (result.duplicate_blocked_count || 0) + (result.weak_needs_review_count || 0)),
								badge: result.unsafe_count ? __("High Risk") : __("Needs Review"),
								tone: result.unsafe_count ? "danger" : "warning",
								meta: [
									`${__("Unsafe")}: ${result.unsafe_count || 0}`,
									`${__("Duplicate Blocked")}: ${result.duplicate_blocked_count || 0}`,
									`${__("Weak / Needs Review")}: ${result.weak_needs_review_count || 0}`,
								],
								footer: __("Duplicate candidate records are informational and remain outside automatic confirmation."),
							},
							{
								title: __("Warnings"),
								value: String(result.warning_count || 0),
								badge: result.warning_count ? __("Needs Review") : __("Clear"),
								tone: result.warning_count ? "warning" : "success",
								meta: [`${__("Already Confirmed")}: ${result.already_confirmed_count || 0}`],
								footer: __("No Bank Reconciliation, Payment Entry, Sales Invoice accounting field, or GL mutation occurred."),
							},
						])}
						${blocked.length
							? ui.renderListCard(__("Blocked"), blocked, {
									value: `${blocked.length}`,
									badge: __("Blocked"),
									tone: "danger",
							  })
							: ""}
					</div>`
				: "",
		indicator: result.blocked_count || result.skipped_count ? "orange" : "green",
	});
}

function show_bank_match_queue_summary(listview) {
	frappe.call({
		method: "retailedge.api.get_bank_match_review_queue_summary",
		args: {
			filters: JSON.stringify(get_bank_match_list_filters(listview)),
		},
		freeze: true,
		freeze_message: __("Loading review queue summary..."),
		callback: function (r) {
			const result = r.message || {};
			const rows = [
				[__("Total Review Records"), result.total || 0],
				[__("Draft / Prepared"), result.draft_prepared || 0],
				[__("Confirmed"), result.confirmed || 0],
				[__("Pending Review"), result.pending_review || 0],
				[__("Needs Review"), result.needs_review || 0],
				[__("Ready to Confirm"), result.ready_to_confirm || 0],
				[__("High-confidence Matches"), result.high_confidence || 0],
				[__("Weak / Needs Review"), result.weak_needs_review || 0],
				[__("Confirmed Today"), result.confirmed_today || 0],
				[__("Rejected"), result.rejected || 0],
				[__("Reopened"), result.reopened || 0],
				[__("Cancelled"), result.cancelled || 0],
				[__("Duplicate / Blocked"), result.duplicate_blocked || 0],
			];
			const ui = window.retailedge && window.retailedge.ui;
			frappe.msgprint({
				title: __("Bank Match Review Queue Summary"),
				message:
					ui && ui.renderCardGrid
						? `<div class="retailedge-dialog-content">
								${ui.renderCardGrid([
									{
										title: __("Review Queue"),
										value: String(result.total || 0),
										badge: result.pending_review || result.needs_review ? __("Needs Review") : __("Ready"),
										tone: result.pending_review || result.needs_review ? "warning" : "success",
										meta: [
											`${__("Pending Review")}: ${result.pending_review || 0}`,
											`${__("Needs Review")}: ${result.needs_review || 0}`,
											`${__("Ready to Confirm")}: ${result.ready_to_confirm || 0}`,
										],
										footer: __("Counts are operational only and do not change accounting records."),
									},
									{
										title: __("Confirmed Flow"),
										value: String(result.confirmed || 0),
										badge: __("Matched"),
										tone: "success",
										meta: [
											`${__("Confirmed Today")}: ${result.confirmed_today || 0}`,
											`${__("High-confidence Matches")}: ${result.high_confidence || 0}`,
										],
										footer: __("Confirmed records are already reviewed."),
									},
									{
										title: __("Exceptions"),
										value: String((result.rejected || 0) + (result.reopened || 0) + (result.cancelled || 0) + (result.duplicate_blocked || 0)),
										badge: result.duplicate_blocked ? __("Possible Match") : __("Needs Review"),
										tone: result.rejected || result.cancelled ? "danger" : "warning",
										meta: [
											`${__("Rejected")}: ${result.rejected || 0}`,
											`${__("Reopened")}: ${result.reopened || 0}`,
											`${__("Cancelled")}: ${result.cancelled || 0}`,
											`${__("Duplicate / Blocked")}: ${result.duplicate_blocked || 0}`,
										],
										footer: __("These counts are read-only and do not reconcile Bank Transactions or mutate accounting records."),
									},
								])}
							</div>`
						: rows
								.map(
									([label, value]) =>
										`<p><strong>${frappe.utils.escape_html(label)}</strong>: ${frappe.utils.escape_html(String(value))}</p>`
								)
								.join(""),
				indicator: "blue",
			});
		},
	});
}

function get_bank_match_list_filters(listview) {
	const filters = {};
	((listview && listview.filter_area && listview.filter_area.get()) || []).forEach((filter) => {
		const fieldname = filter[1];
		const operator = filter[2];
		const value = filter[3];
		if (operator === "=" && value) {
			filters[fieldname] = value;
		}
	});
	return filters;
}


function show_reconciliation_dry_run_summary(result) {
	if (!result) {
		frappe.msgprint({ title: __("Reconciliation Dry Run"), indicator: "orange", message: __("No dry-run summary returned.") });
		return;
	}
	const blocked = (result.groups && result.groups.Blocked ? result.groups.Blocked : [])
		.slice(0, 10)
		.map((row) => `${row.review_name || ""}: ${row.block_reason || ""}`);
	const rows = [
		[__("Checked"), result.total_count || 0],
		[__("Ready"), result.ready_count || 0],
		[__("Blocked"), result.blocked_count || 0],
		[__("Already Handled"), result.already_handled_count || 0],
		[__("Needs Review"), result.needs_review_count || 0],
	];
	frappe.msgprint({
		title: __("Reconciliation Dry Run Summary"),
		indicator: result.blocked_count ? "orange" : "green",
		message: `${frappe.render_template("<table class='table table-bordered'><tbody>{% for row in rows %}<tr><th style='width: 180px'>{{ row[0] }}</th><td>{{ row[1] }}</td></tr>{% endfor %}</tbody></table>", { rows })}
			${blocked.length ? `<p><b>${frappe.utils.escape_html(__("Blocked Items"))}</b></p><ul>${blocked.map((line) => `<li>${frappe.utils.escape_html(line)}</li>`).join("")}</ul>` : ""}`,
	});
}


function show_reconciliation_gate_summary(result) {
	if (!result) {
		frappe.msgprint({ title: __("Reconciliation Execution Gate"), indicator: "orange", message: __("No gate summary returned.") });
		return;
	}
	const rows = [
		[__("Checked"), result.total_count || 0],
		[__("Allowed Later"), result.allowed_count || 0],
		[__("Blocked"), result.blocked_count || 0],
		[__("Needs Approval"), result.needs_approval_count || 0],
		[__("Settings Disabled"), result.settings_disabled_count || 0],
		[__("Permission Denied"), result.permission_denied_count || 0],
	];
	const blocked = (result.results || [])
		.filter((row) => !row.can_execute)
		.slice(0, 10)
		.map((row) => `${row.status || ""}: ${(row.block_reasons || [row.safe_next_step || ""])[0] || ""}`);
	frappe.msgprint({
		title: __("Reconciliation Execution Gate Summary"),
		indicator: result.allowed_count ? "green" : "orange",
		message: `${frappe.render_template("<table class='table table-bordered'><tbody>{% for row in rows %}<tr><th style='width: 200px'>{{ row[0] }}</th><td>{{ row[1] }}</td></tr>{% endfor %}</tbody></table>", { rows })}
			<p>${frappe.utils.escape_html(__("R5.8 checks the execution gate only. No reconciliation was executed."))}</p>
			${blocked.length ? `<ul>${blocked.map((line) => `<li>${frappe.utils.escape_html(line)}</li>`).join("")}</ul>` : ""}`,
	});
}
