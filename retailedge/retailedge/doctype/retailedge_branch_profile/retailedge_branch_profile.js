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
];

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

function companyFilters(frm, extra = {}) {
	return {
		filters: {
			...(frm.doc.company ? { company: frm.doc.company } : {}),
			...extra,
		},
	};
}

function setCompanyDependentQueries(frm) {
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

function clearCompanyDependentDefaults(frm) {
	COMPANY_DEPENDENT_FIELDS.forEach((fieldname) => {
		if (frm.doc[fieldname]) {
			frm.set_value(fieldname, null);
		}
	});
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
	},
	company(frm) {
		clearCompanyDependentDefaults(frm);
		setCompanyDependentQueries(frm);
	},
});
