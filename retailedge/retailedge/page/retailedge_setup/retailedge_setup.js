frappe.pages["retailedge-setup"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("RetailEdge Setup"), single_column: true });
	wrapper.page = page;
	const root = document.createElement("div");
	root.className = "retailedge-setup-page";
	page.body.append(root);
	renderSetup(root);
};

frappe.pages["retailedge-setup"].on_page_show = function (wrapper) {
	const root = wrapper.querySelector(".retailedge-setup-page");
	if (root) renderSetup(root);
};

async function renderSetup(root) {
	root.innerHTML = '<div class="text-muted p-6">' + __("Loading RetailEdge Setup...") + "</div>";
	try {
		const response = await frappe.call({ method: "retailedge.retailedge.page.retailedge_setup.retailedge_setup.get_setup_context" });
		const resources = response.message?.resources || [];
		root.innerHTML = "";
		const intro = document.createElement("div");
		intro.className = "mb-5";
		intro.innerHTML = `<h2>${__("Business Setup")}</h2><p class="text-muted">${__("Configure the RetailEdge records used by daily operations. Advanced forms remain available when you need the full configuration.")}</p>`;
		root.append(intro);
		if (!resources.length) {
			const empty = document.createElement("div");
			empty.className = "alert alert-secondary";
			empty.textContent = __("You do not currently have permission to view RetailEdge setup records.");
			root.append(empty);
			return;
		}
		const grid = document.createElement("div");
		grid.className = "row g-4";
		resources.forEach((resource) => grid.append(buildResourceCard(resource)));
		root.append(grid);
	} catch (error) {
		root.innerHTML = "";
		const alert = document.createElement("div");
		alert.className = "alert alert-danger";
		alert.textContent = error?.message || __("RetailEdge Setup failed to load.");
		root.append(alert);
	}
}

function buildResourceCard(resource) {
	const column = document.createElement("div");
	column.className = "col-12 col-md-6";
	const card = document.createElement("div");
	card.className = "card h-100 shadow-sm";
	const body = document.createElement("div");
	body.className = "card-body d-flex flex-column gap-3";
	const heading = document.createElement("div");
	const countText = resource.count === null ? "" : `<span class="badge badge-light ml-2">${resource.count}</span>`;
	heading.innerHTML = `<h4 class="mb-1">${frappe.utils.escape_html(resource.label)} ${countText}</h4><p class="text-muted mb-0">${frappe.utils.escape_html(resource.description)}</p>`;
	body.append(heading);
	const actions = document.createElement("div");
	actions.className = "d-flex flex-wrap gap-2 mt-auto";
	if (resource.managed_in_page) {
		const manageButton = document.createElement("button");
		manageButton.className = "btn btn-primary btn-sm";
		manageButton.textContent = __("Manage Here");
		manageButton.addEventListener("click", () => {
			if (resource.key === "settings") openRetailEdgeSettings();
			if (resource.key === "expense_categories") openExpenseCategoryManager(resource);
			if (resource.key === "branches") openBranchProfileManager(resource);
			if (resource.key === "statement_mappings") openStatementMappingManager(resource);
		});
		actions.append(manageButton);
	} else {
		const openButton = document.createElement("button");
		openButton.className = "btn btn-primary btn-sm";
		openButton.textContent = resource.singleton ? __("Open Setup") : __("View Records");
		openButton.addEventListener("click", () => openNativeResource(resource));
		actions.append(openButton);
	}
	const advancedButton = document.createElement("button");
	advancedButton.className = "btn btn-default btn-sm";
	advancedButton.textContent = __("Open Full Form");
	advancedButton.addEventListener("click", () => openNativeResource(resource));
	actions.append(advancedButton);
	if (!resource.managed_in_page && !resource.singleton && resource.can_create) {
		const addButton = document.createElement("button");
		addButton.className = "btn btn-default btn-sm";
		addButton.textContent = __("Add New");
		addButton.addEventListener("click", () => openNewNativeResource(resource));
		actions.append(addButton);
	}
	body.append(actions);
	card.append(body);
	column.append(card);
	return column;
}

function roleTableField(fieldname, label, rows) {
	return {
		fieldtype: "Table",
		fieldname,
		label,
		options: fieldname === "posting_date_allowed_roles" ? "RetailEdge Posting Date Role" : fieldname === "cost_price_hidden_roles" ? "RetailEdge Hidden Cost Price Role" : "RetailEdge Daily Sales Audit Reviewer Role",
		data: Array.isArray(rows) ? rows : [],
		fields: [{ fieldtype: "Link", fieldname: "role", label: __("Role"), options: "Role", in_list_view: 1, reqd: 1 }],
	};
}

async function openRetailEdgeSettings() {
	const response = await frappe.call({ method: "retailedge.retailedge.page.retailedge_setup.retailedge_setup.get_retailedge_settings" });
	const data = response.message || {};
	const values = data.values || {};
	const fields = [
		{ fieldtype: "Section Break", label: __("Posting Date Control") },
		{ fieldtype: "Check", fieldname: "enable_posting_date_control", label: __("Enable Posting Date Control"), default: Number(values.enable_posting_date_control || 0) },
		{ fieldtype: "Check", fieldname: "allow_pos_posting_date_override", label: __("Allow POS Posting Date Override"), depends_on: "eval:doc.enable_posting_date_control", default: Number(values.allow_pos_posting_date_override || 0) },
		roleTableField("posting_date_allowed_roles", __("Roles Allowed to Change Posting Date"), values.posting_date_allowed_roles),
		{ fieldtype: "Section Break", label: __("Cost Visibility") },
		{ fieldtype: "Check", fieldname: "hide_cost_price_for_selected_roles", label: __("Hide Cost Price for Selected Roles"), default: Number(values.hide_cost_price_for_selected_roles || 0) },
		roleTableField("cost_price_hidden_roles", __("Roles With Hidden Cost Price"), values.cost_price_hidden_roles),
		{ fieldtype: "Section Break", label: __("Sales & Payment Audit") },
		{ fieldtype: "Check", fieldname: "enable_sales_payment_audit", label: __("Enable Sales & Payment Audit"), default: Number(values.enable_sales_payment_audit || 0) },
		{ fieldtype: "Section Break", label: __("Cashier Expense") },
		{ fieldtype: "Check", fieldname: "enable_cashier_expense_workflow", label: __("Enable Cashier Expense Workflow"), default: Number(values.enable_cashier_expense_workflow || 0) },
		{ fieldtype: "Check", fieldname: "require_cashier_expense_attachment", label: __("Require Attachment for Cashier Expense"), depends_on: "eval:doc.enable_cashier_expense_workflow", default: Number(values.require_cashier_expense_attachment || 0) },
		{ fieldtype: "Check", fieldname: "include_cashier_expenses_in_variance_report", label: __("Include Cashier Expenses in Variance Report"), depends_on: "eval:doc.enable_cashier_expense_workflow", default: Number(values.include_cashier_expenses_in_variance_report || 0) },
		{ fieldtype: "Check", fieldname: "require_open_shift_for_cashier_expense", label: __("Require Open POS Shift for Cashier Expense"), depends_on: "eval:doc.enable_cashier_expense_workflow", default: Number(values.require_open_shift_for_cashier_expense || 0) },
		{ fieldtype: "Check", fieldname: "allow_cashier_expense_date_edit", label: __("Allow Cashier Expense Date Editing"), depends_on: "eval:doc.enable_cashier_expense_workflow", default: Number(values.allow_cashier_expense_date_edit || 0) },
		{ fieldtype: "Check", fieldname: "include_draft_cashier_expenses_in_cash_check", label: __("Include Draft Expenses in Cash Check"), depends_on: "eval:doc.enable_cashier_expense_workflow", default: Number(values.include_draft_cashier_expenses_in_cash_check || 0) },
		{ fieldtype: "Check", fieldname: "include_rejected_cashier_expenses_in_cash_check", label: __("Include Rejected Expenses in Cash Check"), depends_on: "eval:doc.enable_cashier_expense_workflow", default: Number(values.include_rejected_cashier_expenses_in_cash_check || 0) },
		{ fieldtype: "Check", fieldname: "allow_cashier_expense_without_cash_account", label: __("Allow Expense Without Cash Account"), depends_on: "eval:doc.enable_cashier_expense_workflow", default: Number(values.allow_cashier_expense_without_cash_account || 0) },
		{ fieldtype: "Section Break", label: __("Daily Audit Readiness") },
		{ fieldtype: "Check", fieldname: "include_draft_cashier_expenses_in_daily_audit", label: __("Include Draft Expenses"), default: Number(values.include_draft_cashier_expenses_in_daily_audit || 0) },
		{ fieldtype: "Check", fieldname: "include_submitted_cashier_expenses_in_daily_audit", label: __("Include Submitted Expenses"), default: Number(values.include_submitted_cashier_expenses_in_daily_audit || 0) },
		{ fieldtype: "Check", fieldname: "include_pending_ledger_cashier_expenses_in_daily_audit", label: __("Include Pending Ledger Expenses"), default: Number(values.include_pending_ledger_cashier_expenses_in_daily_audit || 0) },
		{ fieldtype: "Check", fieldname: "include_rejected_cashier_expenses_in_daily_audit", label: __("Include Rejected Expenses"), default: Number(values.include_rejected_cashier_expenses_in_daily_audit || 0) },
		{ fieldtype: "Check", fieldname: "exclude_cancelled_cashier_expenses_from_daily_audit", label: __("Exclude Cancelled Expenses"), default: Number(values.exclude_cancelled_cashier_expenses_from_daily_audit || 0) },
		{ fieldtype: "Section Break", label: __("Daily Sales Audit") },
		{ fieldtype: "Check", fieldname: "enable_daily_sales_audit", label: __("Enable Daily Sales Audit"), default: Number(values.enable_daily_sales_audit || 0) },
		{ fieldtype: "Check", fieldname: "require_pos_closing_shift_for_daily_audit", label: __("Require POS Closing Shift"), depends_on: "eval:doc.enable_daily_sales_audit", default: Number(values.require_pos_closing_shift_for_daily_audit || 0) },
		{ fieldtype: "Check", fieldname: "include_cashier_expenses_in_daily_sales_audit_preview", label: __("Include Cashier Expenses in Audit Preview"), depends_on: "eval:doc.enable_daily_sales_audit", default: Number(values.include_cashier_expenses_in_daily_sales_audit_preview || 0) },
		{ fieldtype: "Check", fieldname: "include_rejected_cashier_expenses_in_daily_sales_audit_preview", label: __("Include Rejected Expenses in Audit Preview"), depends_on: "eval:doc.enable_daily_sales_audit", default: Number(values.include_rejected_cashier_expenses_in_daily_sales_audit_preview || 0) },
		{ fieldtype: "Currency", fieldname: "daily_sales_audit_variance_tolerance", label: __("Variance Tolerance"), depends_on: "eval:doc.enable_daily_sales_audit", default: values.daily_sales_audit_variance_tolerance || 0 },
		{ fieldtype: "Check", fieldname: "allow_self_review_daily_sales_audit", label: __("Allow Self Review"), depends_on: "eval:doc.enable_daily_sales_audit", default: Number(values.allow_self_review_daily_sales_audit || 0) },
		roleTableField("daily_sales_audit_reviewer_roles", __("Daily Sales Audit Reviewer Roles"), values.daily_sales_audit_reviewer_roles),
		{ fieldtype: "Section Break", label: __("Branch Defaults") },
		{ fieldtype: "Check", fieldname: "enable_branch_default_application", label: __("Enable Branch Defaults"), default: Number(values.enable_branch_default_application || 0) },
		{ fieldtype: "Check", fieldname: "apply_branch_default_warehouse", label: __("Apply Default Warehouse"), depends_on: "eval:doc.enable_branch_default_application", default: Number(values.apply_branch_default_warehouse || 0) },
		{ fieldtype: "Check", fieldname: "apply_branch_default_cost_center", label: __("Apply Default Cost Center"), depends_on: "eval:doc.enable_branch_default_application", default: Number(values.apply_branch_default_cost_center || 0) },
		{ fieldtype: "Check", fieldname: "apply_branch_default_accounts", label: __("Apply Default Accounts"), depends_on: "eval:doc.enable_branch_default_application", default: Number(values.apply_branch_default_accounts || 0) },
		{ fieldtype: "Check", fieldname: "apply_branch_default_pos_profile", label: __("Apply Default POS Profile"), depends_on: "eval:doc.enable_branch_default_application", default: Number(values.apply_branch_default_pos_profile || 0) },
		{ fieldtype: "Section Break", label: __("Advanced Settings") },
		{ fieldtype: "HTML", fieldname: "advanced_note", options: `<div class="alert alert-secondary mb-0">${__("Platform integration and bank matching/reconciliation settings remain in the full form so they stay aligned with their dedicated workflows.")}</div>` },
	];
	const dialog = new frappe.ui.Dialog({ title: __("RetailEdge Settings"), size: "extra-large", fields });
	if (data.can_write) {
		dialog.set_primary_action(__("Save"), async () => {
			await frappe.call({ method: "retailedge.retailedge.page.retailedge_setup.retailedge_setup.save_retailedge_settings", type: "POST", args: { values: dialog.get_values() } });
			dialog.hide();
			frappe.show_alert({ message: __("RetailEdge Settings saved"), indicator: "green" });
		});
	}
	dialog.show();
}

async function openExpenseCategoryManager(resource) {
	const response = await frappe.call({ method: "retailedge.retailedge.page.retailedge_setup.retailedge_setup.get_expense_categories" });
	const data = response.message || {};
	const rows = Array.isArray(data.rows) ? data.rows : [];
	const dialog = new frappe.ui.Dialog({ title: __("Expense Categories"), size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "category_list" }] });
	const container = dialog.fields_dict.category_list.$wrapper?.[0] || dialog.fields_dict.category_list.wrapper;
	renderExpenseCategoryList(container, rows, Boolean(data.can_create), resource, dialog);
	dialog.show();
}

function renderExpenseCategoryList(container, rows, canCreate, resource, parentDialog) {
	container.innerHTML = "";
	const toolbar = document.createElement("div");
	toolbar.className = "d-flex justify-content-between align-items-center mb-3";
	const summary = document.createElement("div"); summary.className = "text-muted"; summary.textContent = __("{0} categories", [rows.length]); toolbar.append(summary);
	if (canCreate) {
		const add = document.createElement("button"); add.className = "btn btn-primary btn-sm"; add.textContent = __("Add Expense Category"); add.addEventListener("click", () => openExpenseCategoryEditor(null, resource, parentDialog)); toolbar.append(add);
	}
	container.append(toolbar);
	if (!rows.length) { const empty = document.createElement("div"); empty.className = "alert alert-secondary"; empty.textContent = __("No Expense Categories have been created yet."); container.append(empty); return; }
	const table = document.createElement("div"); table.className = "table-responsive";
	table.innerHTML = `<table class="table table-hover table-bordered"><thead><tr><th>${__("Category")}</th><th>${__("Code")}</th><th>${__("Company")}</th><th>${__("Expense Account")}</th><th>${__("Status")}</th><th>${__("Action")}</th></tr></thead><tbody></tbody></table>`;
	const tbody = table.querySelector("tbody");
	rows.forEach((row) => {
		const tr = document.createElement("tr");
		[row.category_name || row.name, row.category_code || "—", row.company || "—", row.expense_account || "—", row.is_active ? __("Active") : __("Inactive")].forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); });
		const actionCell = document.createElement("td"); const edit = document.createElement("button"); edit.className = "btn btn-xs btn-default"; edit.textContent = __("Edit"); edit.addEventListener("click", () => openExpenseCategoryEditor(row, resource, parentDialog)); actionCell.append(edit); tr.append(actionCell); tbody.append(tr);
	});
	container.append(table);
}

function openExpenseCategoryEditor(row, resource, parentDialog) {
	const editing = Boolean(row?.name);
	const dialog = new frappe.ui.Dialog({
		title: editing ? __("Edit Expense Category") : __("Add Expense Category"),
		fields: [
			{ fieldtype: "Data", fieldname: "category_name", label: __("Category Name"), reqd: 1, read_only: editing ? 1 : 0, default: row?.category_name || "" },
			{ fieldtype: "Data", fieldname: "category_code", label: __("Category Code"), default: row?.category_code || "" },
			{ fieldtype: "Link", fieldname: "company", label: __("Company"), options: "Company", default: row?.company || "" },
			{ fieldtype: "Link", fieldname: "expense_account", label: __("Expense Account"), options: "Account", default: row?.expense_account || "" },
			{ fieldtype: "Link", fieldname: "default_cost_center", label: __("Default Cost Center"), options: "Cost Center", default: row?.default_cost_center || "" },
			{ fieldtype: "Check", fieldname: "is_active", label: __("Active"), default: row ? Number(row.is_active) : 1 },
			{ fieldtype: "Small Text", fieldname: "description", label: __("Description"), default: row?.description || "" },
			{ fieldtype: "Small Text", fieldname: "notes", label: __("Notes"), default: row?.notes || "" },
		],
		primary_action_label: __("Save"),
		primary_action: async (values) => {
			await frappe.call({ method: "retailedge.retailedge.page.retailedge_setup.retailedge_setup.save_expense_category", type: "POST", args: { values, name: row?.name || "" } });
			dialog.hide(); parentDialog.hide(); frappe.show_alert({ message: __("Expense Category saved"), indicator: "green" }); await openExpenseCategoryManager(resource);
		},
	});
	const companyField = dialog.fields_dict.company;
	const accountField = dialog.fields_dict.expense_account;
	const costCenterField = dialog.fields_dict.default_cost_center;
	accountField.get_query = () => ({ filters: { company: companyField.get_value() || undefined, root_type: "Expense", is_group: 0, disabled: 0 } });
	costCenterField.get_query = () => ({ filters: { company: companyField.get_value() || undefined, is_group: 0 } });
	companyField.df.onchange = () => { accountField.set_value(""); costCenterField.set_value(""); };
	dialog.show();
}

async function openBranchProfileManager(resource) {
	const response = await frappe.call({ method: "retailedge.retailedge.page.retailedge_setup.retailedge_setup.get_branch_profiles" });
	const data = response.message || {};
	const rows = Array.isArray(data.rows) ? data.rows : [];
	const dialog = new frappe.ui.Dialog({ title: __("Branch Profiles"), size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "profile_list" }] });
	const container = dialog.fields_dict.profile_list.$wrapper?.[0] || dialog.fields_dict.profile_list.wrapper;
	renderBranchProfileList(container, rows, Boolean(data.can_create), resource, dialog);
	dialog.show();
}

function renderBranchProfileList(container, rows, canCreate, resource, parentDialog) {
	container.innerHTML = "";
	const toolbar = document.createElement("div"); toolbar.className = "d-flex justify-content-between align-items-center mb-3";
	const summary = document.createElement("div"); summary.className = "text-muted"; summary.textContent = __("{0} branch profiles", [rows.length]); toolbar.append(summary);
	if (canCreate) { const add = document.createElement("button"); add.className = "btn btn-primary btn-sm"; add.textContent = __("Add Branch Profile"); add.addEventListener("click", () => openBranchProfileEditor(null, resource, parentDialog)); toolbar.append(add); }
	container.append(toolbar);
	if (!rows.length) { const empty = document.createElement("div"); empty.className = "alert alert-secondary"; empty.textContent = __("No Branch Profiles have been created yet."); container.append(empty); return; }
	const table = document.createElement("div"); table.className = "table-responsive";
	table.innerHTML = `<table class="table table-hover table-bordered"><thead><tr><th>${__("Profile")}</th><th>${__("Company")}</th><th>${__("Branch")}</th><th>${__("Default")}</th><th>${__("Status")}</th><th>${__("Action")}</th></tr></thead><tbody></tbody></table>`;
	const tbody = table.querySelector("tbody");
	rows.forEach((row) => { const tr = document.createElement("tr"); [row.profile_name || row.name, row.company || "—", row.branch || "—", row.is_default_for_company ? __("Yes") : __("No"), row.enabled ? __("Enabled") : __("Disabled")].forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); }); const actionCell = document.createElement("td"); const edit = document.createElement("button"); edit.className = "btn btn-xs btn-default"; edit.textContent = __("Edit"); edit.addEventListener("click", () => openBranchProfileEditor(row, resource, parentDialog)); actionCell.append(edit); tr.append(actionCell); tbody.append(tr); });
	container.append(table);
}

function branchUserTable(fieldname, label, rows) {
	return {
		fieldtype: "Table",
		fieldname,
		label,
		options: "RetailEdge Branch Profile User",
		data: Array.isArray(rows) ? rows : [],
		fields: [
			{ fieldtype: "Link", fieldname: "user", label: __("User"), options: "User", in_list_view: 1, reqd: 1, get_query: () => ({ filters: { enabled: 1 } }) },
			{ fieldtype: "Check", fieldname: "is_default", label: __("Default"), in_list_view: 1 },
			{ fieldtype: "Small Text", fieldname: "notes", label: __("Notes"), in_list_view: 1 },
		],
	};
}

async function openBranchProfileEditor(row, resource, parentDialog) {
	const editing = Boolean(row?.name);
	let details = row || {};
	if (editing) {
		const response = await frappe.call({ method: "retailedge.retailedge.page.retailedge_setup.retailedge_setup.get_branch_profile_details", args: { name: row.name } });
		details = response.message || row;
	}
	const fields = [
		{ fieldtype: "Section Break", label: __("Profile") }, { fieldtype: "Data", fieldname: "profile_name", label: __("Profile Name"), reqd: 1, read_only: editing ? 1 : 0, default: details.profile_name || "" }, { fieldtype: "Check", fieldname: "enabled", label: __("Enabled"), default: details.name ? Number(details.enabled) : 1 }, { fieldtype: "Link", fieldname: "company", label: __("Company"), options: "Company", reqd: 1, default: details.company || "" }, { fieldtype: "Link", fieldname: "branch", label: __("Branch"), options: "Branch", reqd: 1, default: details.branch || "" }, { fieldtype: "Check", fieldname: "is_default_for_company", label: __("Default for Company"), default: Number(details.is_default_for_company || 0) },
		{ fieldtype: "Section Break", label: __("POS Defaults") }, { fieldtype: "Link", fieldname: "default_pos_profile", label: __("Default POS Profile"), options: "POS Profile", default: details.default_pos_profile || "" }, { fieldtype: "Link", fieldname: "default_pos_opening_cash_account", label: __("POS Opening Cash Account"), options: "Account", default: details.default_pos_opening_cash_account || "" }, { fieldtype: "Link", fieldname: "default_cash_mode_of_payment", label: __("Cash Mode of Payment"), options: "Mode of Payment", default: details.default_cash_mode_of_payment || "" },
		{ fieldtype: "Section Break", label: __("Warehouse Defaults") }, { fieldtype: "Link", fieldname: "default_warehouse", label: __("Default Warehouse"), options: "Warehouse", default: details.default_warehouse || "" }, { fieldtype: "Link", fieldname: "default_source_warehouse", label: __("Source Warehouse"), options: "Warehouse", default: details.default_source_warehouse || "" }, { fieldtype: "Link", fieldname: "default_target_warehouse", label: __("Target Warehouse"), options: "Warehouse", default: details.default_target_warehouse || "" }, { fieldtype: "Link", fieldname: "default_returns_warehouse", label: __("Returns Warehouse"), options: "Warehouse", default: details.default_returns_warehouse || "" },
		{ fieldtype: "Section Break", label: __("Accounting Defaults") }, { fieldtype: "Link", fieldname: "default_cost_center", label: __("Default Cost Center"), options: "Cost Center", default: details.default_cost_center || "" }, { fieldtype: "Link", fieldname: "default_sales_cost_center", label: __("Sales Cost Center"), options: "Cost Center", default: details.default_sales_cost_center || "" }, { fieldtype: "Link", fieldname: "default_expense_cost_center", label: __("Expense Cost Center"), options: "Cost Center", default: details.default_expense_cost_center || "" }, { fieldtype: "Link", fieldname: "default_cash_account", label: __("Cash Account"), options: "Account", default: details.default_cash_account || "" }, { fieldtype: "Link", fieldname: "default_bank_account", label: __("Bank Account"), options: "Account", default: details.default_bank_account || "" }, { fieldtype: "Link", fieldname: "default_card_pos_account", label: __("Card/POS Settlement Account"), options: "Account", default: details.default_card_pos_account || "" }, { fieldtype: "Link", fieldname: "default_mobile_money_account", label: __("Mobile Money Account"), options: "Account", default: details.default_mobile_money_account || "" },
		{ fieldtype: "Section Break", label: __("Operational Users") },
		branchUserTable("default_cashiers", __("Default Cashiers"), details.default_cashiers),
		branchUserTable("default_managers", __("Default Managers"), details.default_managers),
		branchUserTable("default_auditors", __("Default Auditors"), details.default_auditors),
		{ fieldtype: "Section Break", label: __("Controls") }, { fieldtype: "Check", fieldname: "enable_cashier_expense_control", label: __("Enable Cashier Expense Control"), default: details.name ? Number(details.enable_cashier_expense_control) : 1 }, { fieldtype: "Check", fieldname: "enable_daily_sales_audit", label: __("Enable Daily Sales Audit"), default: details.name ? Number(details.enable_daily_sales_audit) : 1 }, { fieldtype: "Check", fieldname: "enable_transaction_branch_attribution", label: __("Enable Transaction Branch Attribution"), default: details.name ? Number(details.enable_transaction_branch_attribution) : 1 }, { fieldtype: "Check", fieldname: "require_pos_closing_shift_for_audit", label: __("Require POS Closing Shift for Audit"), default: Number(details.require_pos_closing_shift_for_audit || 0) }, { fieldtype: "Currency", fieldname: "variance_tolerance", label: __("Variance Tolerance"), default: details.variance_tolerance || 0 }, { fieldtype: "Small Text", fieldname: "notes", label: __("Notes"), default: details.notes || "" },
	];
	const dialog = new frappe.ui.Dialog({ title: editing ? __("Edit Branch Profile") : __("Add Branch Profile"), size: "extra-large", fields, primary_action_label: __("Save"), primary_action: async (values) => { await frappe.call({ method: "retailedge.retailedge.page.retailedge_setup.retailedge_setup.save_branch_profile", type: "POST", args: { values, name: row?.name || "" } }); dialog.hide(); parentDialog.hide(); frappe.show_alert({ message: __("Branch Profile saved"), indicator: "green" }); await openBranchProfileManager(resource); } });
	configureBranchProfileQueries(dialog);
	dialog.show();
}

function configureBranchProfileQueries(dialog) {
	const companyField = dialog.fields_dict.company;
	const companyFilters = () => ({ company: companyField.get_value() || undefined });
	const branchField = dialog.fields_dict.branch; branchField.get_query = () => ({ filters: companyFilters() });
	const posField = dialog.fields_dict.default_pos_profile; posField.get_query = () => ({ filters: companyFilters() });
	["default_warehouse", "default_source_warehouse", "default_target_warehouse", "default_returns_warehouse"].forEach((fieldname) => { dialog.fields_dict[fieldname].get_query = () => ({ filters: { ...companyFilters(), is_group: 0, disabled: 0 } }); });
	["default_cost_center", "default_sales_cost_center", "default_expense_cost_center"].forEach((fieldname) => { dialog.fields_dict[fieldname].get_query = () => ({ filters: { ...companyFilters(), is_group: 0 } }); });
	["default_pos_opening_cash_account", "default_cash_account", "default_bank_account", "default_card_pos_account", "default_mobile_money_account"].forEach((fieldname) => { dialog.fields_dict[fieldname].get_query = () => ({ filters: { ...companyFilters(), is_group: 0, disabled: 0 } }); });
	companyField.df.onchange = () => { ["branch", "default_pos_profile", "default_pos_opening_cash_account", "default_warehouse", "default_source_warehouse", "default_target_warehouse", "default_returns_warehouse", "default_cost_center", "default_sales_cost_center", "default_expense_cost_center", "default_cash_account", "default_bank_account", "default_card_pos_account", "default_mobile_money_account"].forEach((fieldname) => dialog.fields_dict[fieldname].set_value("")); };
}

async function openStatementMappingManager(resource) {
	const response = await frappe.call({ method: "retailedge.retailedge.page.retailedge_setup.retailedge_setup.get_statement_mappings" });
	const data = response.message || {};
	const rows = Array.isArray(data.rows) ? data.rows : [];
	const dialog = new frappe.ui.Dialog({ title: __("Bank Statement Mapping"), size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "mapping_list" }] });
	const container = dialog.fields_dict.mapping_list.$wrapper?.[0] || dialog.fields_dict.mapping_list.wrapper;
	container.innerHTML = "";
	const toolbar = document.createElement("div"); toolbar.className = "d-flex justify-content-between align-items-center mb-3";
	const summary = document.createElement("div"); summary.className = "text-muted"; summary.textContent = __("{0} mapping templates", [rows.length]); toolbar.append(summary);
	if (data.can_create) { const add = document.createElement("button"); add.className = "btn btn-primary btn-sm"; add.textContent = __("Add Mapping Template"); add.addEventListener("click", () => openStatementMappingEditor(null, resource, dialog)); toolbar.append(add); }
	container.append(toolbar);
	if (!rows.length) { const empty = document.createElement("div"); empty.className = "alert alert-secondary"; empty.textContent = __("No bank statement mapping templates have been created yet."); container.append(empty); dialog.show(); return; }
	const table = document.createElement("div"); table.className = "table-responsive"; table.innerHTML = `<table class="table table-hover table-bordered"><thead><tr><th>${__("Template")}</th><th>${__("Company")}</th><th>${__("Statement Type")}</th><th>${__("Payment Category")}</th><th>${__("Status")}</th><th>${__("Action")}</th></tr></thead><tbody></tbody></table>`;
	const tbody = table.querySelector("tbody");
	rows.forEach((row) => { const tr = document.createElement("tr"); [row.template_name || row.name, row.company || "—", row.statement_type || "—", row.payment_category || "—", row.enabled ? __("Enabled") : __("Disabled")].forEach((value) => { const td = document.createElement("td"); td.textContent = value; tr.append(td); }); const actionCell = document.createElement("td"); const edit = document.createElement("button"); edit.className = "btn btn-xs btn-default"; edit.textContent = __("Edit"); edit.addEventListener("click", () => openStatementMappingEditor(row, resource, dialog)); actionCell.append(edit); tr.append(actionCell); tbody.append(tr); });
	container.append(table);
	dialog.show();
}

function openStatementMappingEditor(row, resource, parentDialog) {
	const editing = Boolean(row?.name);
	const fields = [
		{ fieldtype: "Section Break", label: __("Template") }, { fieldtype: "Data", fieldname: "template_name", label: __("Template Name"), reqd: 1, read_only: editing ? 1 : 0, default: row?.template_name || "" }, { fieldtype: "Check", fieldname: "enabled", label: __("Enabled"), default: row ? Number(row.enabled) : 1 }, { fieldtype: "Link", fieldname: "company", label: __("Company"), options: "Company", default: row?.company || "" }, { fieldtype: "Select", fieldname: "statement_type", label: __("Statement Type"), reqd: 1, options: "Bank Transfer\nCard / POS Settlement\nMobile Money\nOther", default: row?.statement_type || "Bank Transfer" }, { fieldtype: "Select", fieldname: "payment_category", label: __("Payment Category"), reqd: 1, options: "Bank Transfer\nCard / POS\nMobile Money\nOther", default: row?.payment_category || "Bank Transfer" }, { fieldtype: "Data", fieldname: "bank_or_provider_name", label: __("Bank or Provider Name"), default: row?.bank_or_provider_name || "" },
		{ fieldtype: "Section Break", label: __("Statement Columns") }, { fieldtype: "Data", fieldname: "date_column", label: __("Date Column"), default: row?.date_column || "" }, { fieldtype: "Data", fieldname: "value_date_column", label: __("Value Date Column"), default: row?.value_date_column || "" }, { fieldtype: "Data", fieldname: "reference_column", label: __("Reference Column"), default: row?.reference_column || "" }, { fieldtype: "Data", fieldname: "narration_column", label: __("Narration Column"), default: row?.narration_column || "" }, { fieldtype: "Data", fieldname: "debit_column", label: __("Debit Column"), default: row?.debit_column || "" }, { fieldtype: "Data", fieldname: "credit_column", label: __("Credit Column"), default: row?.credit_column || "" }, { fieldtype: "Data", fieldname: "amount_column", label: __("Amount Column"), default: row?.amount_column || "" }, { fieldtype: "Data", fieldname: "balance_column", label: __("Balance Column"), default: row?.balance_column || "" }, { fieldtype: "Data", fieldname: "account_column", label: __("Account Column"), default: row?.account_column || "" }, { fieldtype: "Data", fieldname: "party_column", label: __("Party Column"), default: row?.party_column || "" }, { fieldtype: "Data", fieldname: "channel_column", label: __("Channel Column"), default: row?.channel_column || "" }, { fieldtype: "Data", fieldname: "branch_column", label: __("Branch Column"), default: row?.branch_column || "" }, { fieldtype: "Data", fieldname: "currency_column", label: __("Currency Column"), default: row?.currency_column || "" },
		{ fieldtype: "Section Break", label: __("Formats & Defaults") }, { fieldtype: "Data", fieldname: "date_format", label: __("Date Format"), default: row?.date_format || "" }, { fieldtype: "Data", fieldname: "amount_format", label: __("Amount Format"), default: row?.amount_format || "" }, { fieldtype: "Select", fieldname: "debit_credit_mode", label: __("Debit Credit Mode"), options: "\nSeparate Debit/Credit Columns\nSigned Amount Column\nCredit Only Amount Column", default: row?.debit_credit_mode || "" }, { fieldtype: "Link", fieldname: "default_account", label: __("Default Account"), options: "Account", default: row?.default_account || "" }, { fieldtype: "Small Text", fieldname: "reference_keywords", label: __("Reference Keywords"), default: row?.reference_keywords || "" }, { fieldtype: "Small Text", fieldname: "narration_keywords", label: __("Narration Keywords"), default: row?.narration_keywords || "" }, { fieldtype: "Small Text", fieldname: "notes", label: __("Notes"), default: row?.notes || "" },
	];
	const dialog = new frappe.ui.Dialog({ title: editing ? __("Edit Mapping Template") : __("Add Mapping Template"), size: "extra-large", fields, primary_action_label: __("Save"), primary_action: async (values) => { await frappe.call({ method: "retailedge.retailedge.page.retailedge_setup.retailedge_setup.save_statement_mapping", type: "POST", args: { values, name: row?.name || "" } }); dialog.hide(); parentDialog.hide(); frappe.show_alert({ message: __("Mapping Template saved"), indicator: "green" }); await openStatementMappingManager(resource); } });
	const companyField = dialog.fields_dict.company;
	const accountField = dialog.fields_dict.default_account;
	accountField.get_query = () => ({ filters: { company: companyField.get_value() || undefined, is_group: 0, disabled: 0 } });
	companyField.df.onchange = () => accountField.set_value("");
	dialog.show();
}

function doctypeSlug(doctype) { return String(doctype || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
function openNativeResource(resource) { window.open(`/app/${doctypeSlug(resource.doctype)}`, "_blank", "noopener,noreferrer"); }
function openNewNativeResource(resource) { window.open(`/app/${doctypeSlug(resource.doctype)}/new`, "_blank", "noopener,noreferrer"); }
