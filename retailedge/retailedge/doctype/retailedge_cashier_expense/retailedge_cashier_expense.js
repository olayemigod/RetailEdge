frappe.ui.form.on("RetailEdge Cashier Expense", {
	setup(frm) {
		frm.set_query("expense_category", function () {
			const filters = {};
			if (frm.doc.company) {
				filters.company = frm.doc.company;
			}
			filters.is_active = 1;
			return { filters };
		});

		frm.set_query("payment_account", function () {
			return {
				filters: {
					company: frm.doc.company || "",
					is_group: 0,
				},
			};
		});

		frm.set_query("cost_center", function () {
			return {
				filters: {
					company: frm.doc.company || "",
					is_group: 0,
				},
			};
		});
	},

	onload(frm) {
		if (frm.is_new()) {
			frm.events.load_cashier_context(frm);
		}
	},

	refresh(frm) {
		frm.events.ensure_settings_context(frm);
		frm.events.apply_read_only_context(frm);
		if (frm.is_new() && !frm.__cashier_context_loaded) {
			frm.events.load_cashier_context(frm);
		}
		frm.events.add_review_actions(frm);
		frm.events.add_daily_audit_actions(frm);
		frm.events.add_posting_preview_actions(frm);
		frm.events.update_status_message(frm);
	},

	amount(frm) {
		frm.events.recalculate_cash_after_expense(frm);
	},

	expense_category(frm) {
		if (!frm.doc.expense_category) {
			return;
		}

		frappe.db
			.get_value("RetailEdge Expense Category", frm.doc.expense_category, [
				"expense_account",
				"default_cost_center",
			])
			.then((result) => {
				const data = result.message || {};
				const updates = {};
				if (data.expense_account && data.expense_account !== frm.doc.expense_account) {
					updates.expense_account = data.expense_account;
				}
				if (data.default_cost_center && data.default_cost_center !== frm.doc.cost_center) {
					updates.cost_center = data.default_cost_center;
				}
				if (Object.keys(updates).length) {
					frm.set_value(updates);
				}
			});
	},

	load_cashier_context(frm) {
		if (frm.__cashier_context_loading || !frm.is_new()) {
			return;
		}
		frm.__cashier_context_loading = true;

		frappe.call({
			method: "retailedge.api.get_cashier_expense_entry_context",
			args: {
				company: frm.doc.company || undefined,
			},
			callback: (response) => {
				const context = response.message || {};
				const updates = {};
				const mapping = [
					"company",
					"branch",
					"pos_profile",
					"cashier",
					"expense_date",
					"payment_account",
					"cost_center",
					"linked_pos_opening_shift",
					"shift_opening_cash_amount",
					"shift_cash_sales_amount",
					"prior_shift_expense_amount",
					"available_shift_cash_before_expense",
					"available_shift_cash_after_expense",
					"cash_balance_source",
					"cash_control_message",
				];
				["branch_source", "cost_center_source"].forEach((fieldname) => {
					if (frm.fields_dict[fieldname]) {
						mapping.push(fieldname);
					}
				});

				mapping.forEach((fieldname) => {
					if (!frm.doc[fieldname] && context[fieldname] !== undefined && context[fieldname] !== null) {
						updates[fieldname] = context[fieldname];
					}
				});

				if (Object.keys(updates).length) {
					frm.set_value(updates).then(() => {
						frm.events.recalculate_cash_after_expense(frm);
					});
				} else {
					frm.events.recalculate_cash_after_expense(frm);
				}

				const settings = context.settings || {};
				frm.__cashier_expense_settings = settings;
				frm.events.apply_read_only_context(frm);
				if (
					!context.linked_pos_opening_shift &&
					settings.require_open_shift_for_cashier_expense &&
					context.cash_control_message
				) {
					frappe.msgprint(__("No open POS Opening Shift found. Please open a POS shift before recording cashier expenses."));
				}
				frm.__cashier_context_loaded = true;
			},
			always: () => {
				frm.__cashier_context_loading = false;
			},
		});
	},

	recalculate_cash_after_expense(frm) {
		const availableBefore = flt(frm.doc.available_shift_cash_before_expense);
		const amount = flt(frm.doc.amount);
		const availableAfter = availableBefore - amount;
		frm.set_value("available_shift_cash_after_expense", availableAfter);
		if (amount > availableBefore && availableBefore > 0) {
			frappe.show_alert(
				{
					message: __(
						"Insufficient shift cash. Available: {0}. Requested: {1}.",
						[format_currency(availableBefore), format_currency(amount)]
					),
					indicator: "orange",
				},
				5
			);
		}
	},

	apply_read_only_context(frm) {
		const settings = frm.events.get_cashier_expense_settings(frm);
		const allowDateEdit = cint(settings.allow_cashier_expense_date_edit || 0);
		frm.set_df_property("expense_date", "read_only", allowDateEdit ? 0 : 1);
		frm.set_df_property("expense_status", "label", __("Review Status"));
		frm.set_df_property("ledger_status", "label", __("Ledger Status"));

		[
			"company",
			"cashier",
			"pos_profile",
			"branch",
			"expense_account",
			"cost_center",
			"payment_account",
			"linked_pos_opening_shift",
			"linked_pos_closing_shift",
			"shift_opening_cash_amount",
			"shift_cash_sales_amount",
			"prior_shift_expense_amount",
			"available_shift_cash_before_expense",
			"available_shift_cash_after_expense",
			"cash_balance_source",
			"cash_control_message",
			"posting_ready",
			"posting_block_reason",
			"resolved_debit_account",
			"resolved_credit_account",
			"resolved_posting_cost_center",
			"posting_preview",
			"daily_audit_inclusion_status",
			"daily_audit_reviewed_by",
			"daily_audit_reviewed_on",
			"review_required",
			"user_message",
			"last_readiness_refresh_on",
			"last_readiness_refresh_by",
		].forEach((fieldname) => {
			frm.set_df_property(fieldname, "read_only", 1);
		});
	},

	add_review_actions(frm) {
		const effectiveStatus = frm.events.get_effective_review_status(frm);
		if (frm.is_new() || frm.doc.docstatus !== 1 || !frm.events.user_is_reviewer()) {
			return;
		}
		const group = __("Review");

		if (effectiveStatus === "Submitted") {
			frm.add_custom_button(__("Approve"), () => {
				frm.events.prompt_review_action(frm, {
					title: __("Approve Cashier Expense"),
					label: __("Remarks"),
					required: 0,
					method: "retailedge.api.approve_cashier_expense",
				});
			}, group);
			frm.add_custom_button(__("Reject"), () => {
				frm.events.prompt_review_action(frm, {
					title: __("Reject Cashier Expense"),
					label: __("Remarks"),
					required: 1,
					method: "retailedge.api.reject_cashier_expense",
				});
			}, group);
		}

		if (["Rejected", "Pending Ledger"].includes(effectiveStatus)) {
			frm.add_custom_button(__("Reopen"), () => {
				frm.events.prompt_review_action(frm, {
					title: __("Reopen Cashier Expense"),
					label: __("Remarks"),
					required: 0,
					method: "retailedge.api.reopen_cashier_expense",
				});
			}, group);
		}
	},

	add_posting_preview_actions(frm) {
		if (frm.is_new()) {
			return;
		}
		const group = __("Readiness");

		frm.add_custom_button(__("Preview Ledger Posting"), () => {
			frappe.call({
				method: "retailedge.api.get_cashier_expense_posting_preview",
				args: { expense_name: frm.doc.name },
				callback: (response) => {
					const preview = response.message || {};
					const lines = (preview.preview_lines || [])
						.map(
							(line) =>
								`<li><strong>${frappe.utils.escape_html(line.account || "")}</strong>: debit ${format_currency(
									line.debit || 0
								)}, credit ${format_currency(line.credit || 0)}, cost center ${frappe.utils.escape_html(
									line.cost_center || ""
								)}</li>`
						)
						.join("");
					const blockReason = preview.posting_block_reason
						? `<p><strong>${__("Block Reason")}:</strong> ${frappe.utils.escape_html(preview.posting_block_reason)}</p>`
						: "";
					frappe.msgprint({
						title: __("Ledger Posting Preview"),
						message: `
							<p><strong>${__("Posting Ready")}:</strong> ${preview.posting_ready ? __("Yes") : __("No")}</p>
							${blockReason}
							<p><strong>${__("Document Type")}:</strong> ${frappe.utils.escape_html(preview.posting_document_type || "")}</p>
							<p><strong>${__("Amount")}:</strong> ${format_currency(preview.amount || 0)}</p>
							<p><strong>${__("Posting Date")}:</strong> ${frappe.utils.escape_html(preview.posting_date || "")}</p>
							<p><strong>${__("Debit Account")}:</strong> ${frappe.utils.escape_html(preview.debit_account || "")}</p>
							<p><strong>${__("Credit Account")}:</strong> ${frappe.utils.escape_html(preview.credit_account || "")}</p>
							<p><strong>${__("Cost Center")}:</strong> ${frappe.utils.escape_html(preview.cost_center || "")}</p>
							<p><strong>${__("Remarks")}:</strong> ${frappe.utils.escape_html(preview.remarks || "")}</p>
							<ul>${lines}</ul>
						`,
					});
				},
			});
		}, group);

		if (frm.doc.docstatus === 1 && frm.events.user_can_refresh_posting_readiness()) {
			frm.add_custom_button(__("Refresh Posting Readiness"), () => {
				frappe.call({
					method: "retailedge.api.refresh_cashier_expense_posting_readiness",
					args: { expense_name: frm.doc.name },
					callback: () => frm.reload_doc(),
				});
			}, group);
		}
	},

	add_daily_audit_actions(frm) {
		if (frm.is_new() || !frm.events.user_is_reviewer()) {
			return;
		}
		const effectiveStatus = frm.events.get_effective_review_status(frm);
		if (frm.doc.docstatus === 2 || effectiveStatus === "Cancelled") {
			return;
		}
		if (!frm.events.is_daily_audit_status_enabled(frm, effectiveStatus)) {
			return;
		}
		const group = __("Daily Audit");

		if (frm.doc.daily_audit_inclusion_status !== "Included") {
			frm.add_custom_button(__("Mark Included for Daily Audit"), () => {
				frm.events.prompt_daily_audit_action(frm, {
					title: __("Mark Included for Daily Audit"),
					label: __("Note"),
					required: 0,
					argname: "note",
					method: "retailedge.api.mark_cashier_expense_included_for_daily_audit",
				});
			}, group);
		}

		if (frm.doc.daily_audit_inclusion_status !== "Excluded") {
			frm.add_custom_button(__("Exclude from Daily Audit"), () => {
				frm.events.prompt_daily_audit_action(frm, {
					title: __("Exclude from Daily Audit"),
					label: __("Reason"),
					required: 1,
					argname: "reason",
					method: "retailedge.api.mark_cashier_expense_excluded_from_daily_audit",
				});
			}, group);
		}

		if (frm.doc.daily_audit_inclusion_status !== "Needs Clarification") {
			frm.add_custom_button(__("Needs Clarification"), () => {
				frm.events.prompt_daily_audit_action(frm, {
					title: __("Mark Daily Audit Needs Clarification"),
					label: __("Note"),
					required: 0,
					argname: "note",
					method: "retailedge.api.mark_cashier_expense_needs_clarification",
				});
			}, group);
		}
	},

	update_status_message(frm) {
		const effectiveStatus = frm.events.get_effective_review_status(frm);
		const documentStatus = frm.events.get_document_status_label(frm);
		const reviewMessage = __(
			"Document Status: {0}. Review Status: {1}. Ledger Status: {2}.",
			[documentStatus, effectiveStatus, frm.doc.ledger_status || __("Not Applicable")]
		);

		if (effectiveStatus === "Pending Ledger") {
			frm.set_intro(
				__(
					"{0} This expense is approved for future ledger posting, but actual posting is not enabled in this phase.",
					[reviewMessage]
				),
				"orange"
			);
			return;
		}
		if (frm.doc.posting_block_reason) {
			frm.set_intro(
				__("{0} Posting readiness is blocked: {1}", [reviewMessage, frm.doc.posting_block_reason]),
				"orange"
			);
			return;
		}
		if (frm.doc.daily_audit_inclusion_status === "Needs Clarification") {
			frm.set_intro(
				__("{0} This expense needs clarification before future Daily Audit review.", [reviewMessage]),
				"orange"
			);
			return;
		}
		if (!frm.doc.linked_pos_opening_shift && frm.doc.__islocal) {
			frm.set_intro(
				__("{0} An open POS Opening Shift is required before recording cashier expenses.", [reviewMessage]),
				"orange"
			);
			return;
		}
		frm.set_intro(reviewMessage, "blue");
	},

	get_cashier_expense_settings(frm) {
		return frm.__cashier_expense_settings || frappe.boot?.retailedge?.cashier_expense_settings || {};
	},

	ensure_settings_context(frm) {
		if (frm.__cashier_expense_settings_loaded || frm.__cashier_expense_settings_loading) {
			return;
		}
		const bootSettings = frappe.boot?.retailedge?.cashier_expense_settings || null;
		if (bootSettings) {
			frm.__cashier_expense_settings = bootSettings;
			frm.__cashier_expense_settings_loaded = true;
			return;
		}
		frm.__cashier_expense_settings_loading = true;
		frappe.call({
			method: "retailedge.api.get_cashier_expense_entry_context",
			args: {
				company: frm.doc.company || undefined,
			},
			callback: (response) => {
				const context = response.message || {};
				frm.__cashier_expense_settings = context.settings || {};
				frm.__cashier_expense_settings_loaded = true;
				frm.events.apply_read_only_context(frm);
				frm.events.clear_custom_buttons(frm);
			},
			always: () => {
				frm.__cashier_expense_settings_loading = false;
			},
		});
	},

	clear_custom_buttons(frm) {
		[
			[__("Approve"), __("Review")],
			[__("Reject"), __("Review")],
			[__("Reopen"), __("Review")],
			[__("Mark Included for Daily Audit"), __("Daily Audit")],
			[__("Exclude from Daily Audit"), __("Daily Audit")],
			[__("Needs Clarification"), __("Daily Audit")],
			[__("Preview Ledger Posting"), __("Readiness")],
			[__("Refresh Posting Readiness"), __("Readiness")],
		].forEach(([label, group]) => frm.remove_custom_button(label, group));
		frm.events.add_review_actions(frm);
		frm.events.add_daily_audit_actions(frm);
		frm.events.add_posting_preview_actions(frm);
		frm.events.update_status_message(frm);
	},

	get_effective_review_status(frm) {
		if (frm.doc.docstatus === 2 || frm.doc.expense_status === "Cancelled") {
			return "Cancelled";
		}
		if (frm.doc.docstatus === 1 && (!frm.doc.expense_status || frm.doc.expense_status === "Draft")) {
			return "Submitted";
		}
		return frm.doc.expense_status || "Draft";
	},

	get_document_status_label(frm) {
		if (frm.doc.docstatus === 2) {
			return __("Cancelled");
		}
		if (frm.doc.docstatus === 1) {
			return __("Submitted");
		}
		return __("Draft");
	},

	is_daily_audit_status_enabled(frm, effectiveStatus) {
		const settings = frm.events.get_cashier_expense_settings(frm);
		const statusSettings = {
			Draft: cint(settings.include_draft_cashier_expenses_in_daily_audit ?? 1),
			Submitted: cint(settings.include_submitted_cashier_expenses_in_daily_audit ?? 1),
			"Pending Ledger": cint(settings.include_pending_ledger_cashier_expenses_in_daily_audit ?? 1),
			Rejected: cint(settings.include_rejected_cashier_expenses_in_daily_audit ?? 1),
			Posted: 1,
			Cancelled: cint(settings.exclude_cancelled_cashier_expenses_from_daily_audit ?? 1) ? 0 : 1,
		};
		return Boolean(statusSettings[effectiveStatus] ?? 1);
	},

	prompt_review_action(frm, options) {
		frappe.prompt(
			[
				{
					fieldname: "remarks",
					fieldtype: "Small Text",
					label: options.label || __("Remarks"),
					reqd: options.required ? 1 : 0,
				},
			],
			(values) => {
				frappe.call({
					method: options.method,
					args: {
						expense_name: frm.doc.name,
						remarks: values.remarks,
					},
					callback: () => frm.reload_doc(),
				});
			},
			options.title,
			__("Submit")
		);
	},

	prompt_daily_audit_action(frm, options) {
		frappe.prompt(
			[
				{
					fieldname: "message",
					fieldtype: "Small Text",
					label: options.label,
					reqd: options.required ? 1 : 0,
				},
			],
			(values) => {
				frappe.call({
					method: options.method,
					args: {
						expense_name: frm.doc.name,
						[options.argname]: values.message,
					},
					callback: () => frm.reload_doc(),
				});
			},
			options.title,
			__("Submit")
		);
	},

	user_is_reviewer() {
		const reviewerRoles = new Set([
			"System Manager",
			"Accounts Manager",
			"RetailEdge Manager",
			"RetailEdge Branch Manager",
			"RetailEdge Auditor",
			"RetailEdgeManager",
			"RetailEdgeBranchManager",
			"RetailEdgeAuditor",
		]);
		return (frappe.user_roles || []).some((role) => reviewerRoles.has(role));
	},

	user_can_refresh_posting_readiness() {
		const refreshRoles = new Set([
			"System Manager",
			"Accounts Manager",
			"RetailEdge Manager",
			"RetailEdgeManager",
			"RetailEdge Auditor",
			"RetailEdgeAuditor",
		]);
		return (frappe.user_roles || []).some((role) => refreshRoles.has(role));
	},
});
