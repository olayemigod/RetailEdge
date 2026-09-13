const COMPANY_DEPENDENT_FIELDS = [
	"default_pos_profile",
	"default_warehouse",
	"default_source_warehouse",
	"default_target_warehouse",
	"default_returns_warehouse",
	"default_cost_center",
	"default_sales_cost_center",
	"default_expense_cost_center",
	"default_pos_opening_cash_account",
	"default_cash_account",
	"default_bank_account",
	"default_card_pos_account",
	"default_mobile_money_account",
	"default_cash_mode_of_payment",
];

const BRANCH_USER_TABLE_FIELDS = ["default_cashiers", "default_managers", "default_auditors"];

const WAREHOUSE_FIELDS = [
	"default_warehouse",
	"default_source_warehouse",
	"default_target_warehouse",
	"default_returns_warehouse",
];

const COST_CENTER_FIELDS = [
	"default_cost_center",
	"default_sales_cost_center",
	"default_expense_cost_center",
];

const ACCOUNT_FIELDS = [
	"default_pos_opening_cash_account",
	"default_cash_account",
	"default_bank_account",
	"default_card_pos_account",
	"default_mobile_money_account",
];

const REASSIGNMENT_STATE_METHOD =
	"retailedge.retailedge.doctype.retailedge_branch_profile.retailedge_branch_profile.get_branch_profile_reassignment_state";
const REASSIGNMENT_METHOD =
	"retailedge.retailedge.doctype.retailedge_branch_profile.retailedge_branch_profile.reassign_branch_profile";
const REASSIGNMENT_BRANCH_QUERY =
	"retailedge.branch_profile_queries.search_reassignment_target_branches";

function companyFilters(frm, extra = {}) {
	return {
		filters: {
			...(frm.doc.company ? { company: frm.doc.company } : {}),
			...extra,
		},
	};
}

function applyBranchIdentityState(frm, state = null) {
	const isNew = frm.is_new();
	const editable = isNew || Boolean(state && state.identity_editable);
	frm.toggle_enable("company", editable);
	frm.toggle_enable("branch", editable && Boolean(frm.doc.company));
	frm.set_df_property("branch", "label", isNew ? __("Assign ERPNext Branch") : __("Branch"));

	let description;
	if (isNew) {
		description = __(
			"ERPNext Branches are global. Choose an unassigned Branch to establish its Company mapping in RetailEdge."
		);
	} else if (state && state.has_operational_history) {
		description = __(
			"This mapping has operational history. Use Change Company / Branch to preserve historical meaning before reassignment."
		);
	} else if (state && state.identity_editable) {
		description = __(
			"No operational history was found. Company and Branch can be corrected directly; dependent defaults will be cleared for revalidation."
		);
	} else {
		description = __(
			"RetailEdge is validating whether this Company ↔ Branch mapping can be edited safely."
		);
	}
	frm.set_df_property("branch", "description", description);
}

function setBranchQuery(frm) {
	frm.set_query("branch", () => ({
		query: "retailedge.branch_profile_queries.search_available_branch_setup_branches",
		filters: {
			company: frm.doc.company || "",
			profile_name: frm.doc.name || "",
		},
	}));
}

function setCompanyDependentQueries(frm) {
	setBranchQuery(frm);
	frm.set_query("default_pos_profile", () => companyFilters(frm, { disabled: 0 }));

	WAREHOUSE_FIELDS.forEach((fieldname) => {
		frm.set_query(fieldname, () => companyFilters(frm, { is_group: 0, disabled: 0 }));
	});

	COST_CENTER_FIELDS.forEach((fieldname) => {
		frm.set_query(fieldname, () => companyFilters(frm, { is_group: 0, disabled: 0 }));
	});

	ACCOUNT_FIELDS.forEach((fieldname) => {
		frm.set_query(fieldname, () => companyFilters(frm, { is_group: 0, disabled: 0 }));
	});
}

function clearIdentityDependentDefaults(frm) {
	COMPANY_DEPENDENT_FIELDS.forEach((fieldname) => {
		if (frm.doc[fieldname]) {
			frm.set_value(fieldname, null);
		}
	});
	BRANCH_USER_TABLE_FIELDS.forEach((fieldname) => {
		if ((frm.doc[fieldname] || []).length) {
			frm.clear_table(fieldname);
			frm.refresh_field(fieldname);
		}
	});
}

function addReassignmentAction(frm, state) {
	frm.remove_custom_button(__("Change Company / Branch"), __("Actions"));
	if (!state || !state.requires_controlled_reassignment || !state.can_reassign) {
		return;
	}
	frm.add_custom_button(
		__("Change Company / Branch"),
		() => openBranchReassignmentDialog(frm),
		__("Actions")
	);
}

function refreshBranchIdentityState(frm) {
	if (frm.is_new()) {
		frm.__retailedge_branch_identity_state = null;
		applyBranchIdentityState(frm);
		return;
	}

	// Fail safe while the server checks operational history.
	applyBranchIdentityState(frm, null);
	frappe
		.call({
			method: REASSIGNMENT_STATE_METHOD,
			args: { name: frm.doc.name },
		})
		.then((response) => {
			if (frm.doc.name !== response?.message?.name && frm.is_new()) {
				return;
			}
			const state = response.message || {};
			frm.__retailedge_branch_identity_state = state;
			applyBranchIdentityState(frm, state);
			addReassignmentAction(frm, state);
		})
		.catch(() => {
			applyBranchIdentityState(frm, null);
		});
}

function openBranchReassignmentDialog(frm) {
	let dialog;
	dialog = new frappe.ui.Dialog({
		title: __("Change Company / Branch"),
		fields: [
			{
				fieldname: "warning",
				fieldtype: "HTML",
				options: `<div class="alert alert-warning">${__(
					"RetailEdge will preserve the old mapping when operational history exists. Branch-specific defaults and assigned Branch users are cleared so they can be validated for the new context."
				)}</div>`,
			},
			{
				fieldname: "new_company",
				fieldtype: "Link",
				label: __("New Company"),
				options: "Company",
				reqd: 1,
				default: frm.doc.company,
			},
			{
				fieldname: "new_branch",
				fieldtype: "Link",
				label: __("New Branch"),
				options: "Branch",
				reqd: 1,
				default: frm.doc.branch,
				get_query: () => ({
					query: REASSIGNMENT_BRANCH_QUERY,
					filters: {
						company: dialog.get_value("new_company") || "",
						profile_name: frm.doc.name || "",
					},
				}),
			},
		],
		primary_action_label: __("Validate & Reassign"),
		primary_action(values) {
			if (!values.new_company || !values.new_branch) {
				return;
			}
			if (values.new_company === frm.doc.company && values.new_branch === frm.doc.branch) {
				frappe.msgprint(__("Choose a different Company or Branch."));
				return;
			}
			frappe.confirm(
				__(
					"Reassign this Branch Setup? RetailEdge will not change submitted ERPNext documents or historical transaction Branch values."
				),
				() => {
					dialog.get_primary_btn().prop("disabled", true);
					frappe
						.call({
							method: REASSIGNMENT_METHOD,
							args: {
								name: frm.doc.name,
								new_company: values.new_company,
								new_branch: values.new_branch,
							},
							freeze: true,
							freeze_message: __("Validating Branch reassignment..."),
						})
						.then((response) => {
							const result = response.message || {};
							dialog.hide();
							const historyMessage = result.historical_setup
								? __(" Historical mapping preserved as {0}.", [result.historical_setup])
								: "";
							frappe.show_alert({
								message: __("Branch assignment updated.{0}", [historyMessage]),
								indicator: "green",
							});
							return frm.reload_doc();
						})
						.finally(() => {
							dialog.get_primary_btn().prop("disabled", false);
						});
				}
			);
		},
	});

	dialog.fields_dict.new_company.df.onchange = () => {
		dialog.set_value("new_branch", null);
	};
	dialog.show();
}

frappe.ui.form.on("RetailEdge Branch Profile", {
	setup(frm) {
		setCompanyDependentQueries(frm);
	},
	refresh(frm) {
		if (frm.page && frm.page.set_title) {
			frm.page.set_title(__("Branch Setup"));
		}
		setCompanyDependentQueries(frm);
		refreshBranchIdentityState(frm);
	},
	company(frm) {
		if (!frm.__retailedge_branch_identity_state?.identity_editable && !frm.is_new()) {
			return;
		}
		if (frm.doc.branch) {
			frm.set_value("branch", null);
		}
		clearIdentityDependentDefaults(frm);
		setCompanyDependentQueries(frm);
	},
	branch(frm) {
		if (!frm.__retailedge_branch_identity_state?.identity_editable && !frm.is_new()) {
			return;
		}
		clearIdentityDependentDefaults(frm);
	},
});
