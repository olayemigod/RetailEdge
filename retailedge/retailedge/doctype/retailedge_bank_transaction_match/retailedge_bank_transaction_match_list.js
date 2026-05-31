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
	],

	get_indicator(doc) {
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
							frappe.call({
								method: "retailedge.api.bulk_confirm_bank_transaction_matches",
								args: {
									match_names: JSON.stringify(names),
									remarks: values.remarks || "",
								},
								freeze: true,
								freeze_message: __("Confirming eligible matches..."),
								callback: function (confirmResponse) {
									show_bulk_bank_match_result(confirmResponse.message, __("Bulk Confirm Summary"));
									listview.refresh();
								},
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
