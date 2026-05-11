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
		frm.events.apply_read_only_context(frm);
		if (frm.is_new() && !frm.__cashier_context_loaded) {
			frm.events.load_cashier_context(frm);
		}
		frm.events.add_review_actions(frm);
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
					message: __("Expense amount exceeds available shift cash."),
					indicator: "orange",
				},
				5
			);
		}
	},

	apply_read_only_context(frm) {
		const settings = frm.__cashier_expense_settings || {};
		const allowDateEdit = cint(settings.allow_cashier_expense_date_edit || 0);
		frm.set_df_property("expense_date", "read_only", allowDateEdit ? 0 : 1);

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
		].forEach((fieldname) => {
			frm.set_df_property(fieldname, "read_only", 1);
		});
	},

	add_review_actions(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 1 || !frm.events.user_is_reviewer()) {
			return;
		}

		if (frm.doc.expense_status === "Submitted") {
			frm.add_custom_button(__("Approve"), () => {
				frm.events.prompt_review_action(frm, {
					title: __("Approve Cashier Expense"),
					label: __("Remarks"),
					required: 0,
					method: "retailedge.api.approve_cashier_expense",
				});
			});
			frm.add_custom_button(__("Reject"), () => {
				frm.events.prompt_review_action(frm, {
					title: __("Reject Cashier Expense"),
					label: __("Remarks"),
					required: 1,
					method: "retailedge.api.reject_cashier_expense",
				});
			});
		}

		if (["Rejected", "Pending Ledger"].includes(frm.doc.expense_status)) {
			frm.add_custom_button(__("Reopen"), () => {
				frm.events.prompt_review_action(frm, {
					title: __("Reopen Cashier Expense"),
					label: __("Remarks"),
					required: 0,
					method: "retailedge.api.reopen_cashier_expense",
				});
			});
		}
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
});
