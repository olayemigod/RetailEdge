frappe.ui.form.on("RetailEdge Daily Sales Audit", {
	async refresh(frm) {
		frm.set_intro(
			__(
				"This audit is a RetailEdge preview/control document. It does not modify Sales Invoices, POS shifts, payments, or accounting records in this phase."
			)
		);

		setup_context_queries(frm);
		await refresh_context_options(frm);

		if (frm.doc.docstatus === 0 && has_daily_sales_audit_reviewer_role()) {
			frm.add_custom_button(__("Resolve Audit Context"), async () => {
				const resolved = await resolve_audit_context(frm, { trigger_field: "manual", manual: true });
				if (!resolved) {
					return;
				}
				const parts = [];
				for (const fieldname of context_fields()) {
					if (resolved[fieldname]) {
						parts.push(`${frappe.meta.get_label(frm.doctype, fieldname, frm.doc.name) || fieldname}: ${resolved[fieldname]}`);
					}
				}
				frappe.show_alert({
					message: parts.length ? __("Resolved: {0}", [parts.join(", ")]) : __("No additional context was resolved."),
					indicator: "blue",
				});
			});

			frm.add_custom_button(__("Refresh Preview"), () => {
				frappe.call({
					method: "retailedge.api.refresh_daily_sales_audit_preview",
					args: { audit_name: frm.doc.name },
					callback: () => frm.reload_doc(),
				});
			});
		}
	},

	async company(frm) {
		await handle_context_change(frm, "company");
	},

	async branch(frm) {
		await handle_context_change(frm, "branch");
	},

	async pos_profile(frm) {
		await handle_context_change(frm, "pos_profile");
	},

	async cashier(frm) {
		await handle_context_change(frm, "cashier");
	},

	async audit_date(frm) {
		await handle_context_change(frm, "audit_date");
	},

	async pos_opening_shift(frm) {
		await handle_context_change(frm, "pos_opening_shift");
	},

	async pos_closing_shift(frm) {
		await handle_context_change(frm, "pos_closing_shift");
	},
});

function context_fields() {
	return [
		"company",
		"branch",
		"pos_profile",
		"cashier",
		"audit_date",
		"pos_opening_shift",
		"pos_closing_shift",
	];
}

function context_field_order() {
	return [
		"company",
		"branch",
		"pos_profile",
		"cashier",
		"audit_date",
		"pos_opening_shift",
		"pos_closing_shift",
	];
}

function setup_context_queries(frm) {
	frm.set_query("branch", () => ({}));
	frm.set_query("pos_profile", () => build_name_filter(frm, "pos_profiles"));
	frm.set_query("cashier", () => ({
		query: "retailedge.daily_sales_audit.search_daily_sales_audit_cashiers",
		filters: get_context_filters(frm),
	}));
	frm.set_query("pos_opening_shift", () => ({
		query: "retailedge.daily_sales_audit.search_daily_sales_audit_opening_shifts",
		filters: get_context_filters(frm),
	}));
	frm.set_query("pos_closing_shift", () => ({
		query: "retailedge.daily_sales_audit.search_daily_sales_audit_closing_shifts",
		filters: get_context_filters(frm),
	}));
}

function build_name_filter(frm, option_key) {
	const options = frm.__daily_sales_audit_options || {};
	const rows = options[option_key] || [];
	if (!rows.length) {
		if (Object.prototype.hasOwnProperty.call(options, option_key)) {
			return {
				filters: {
					name: ["in", ["__no_match__"]],
				},
			};
		}
		return {};
	}
	return {
		filters: {
			name: ["in", rows],
		},
	};
}

function get_context_filters(frm) {
	const filters = {};
	for (const fieldname of context_fields()) {
		if (frm.doc[fieldname]) {
			filters[fieldname] = frm.doc[fieldname];
		}
	}
	return filters;
}

async function refresh_context_options(frm) {
	const response = await frappe.call({
		method: "retailedge.api.get_daily_sales_audit_context_options",
		args: { filters: get_context_filters(frm) },
	});
	frm.__daily_sales_audit_options = response.message || {};
	return frm.__daily_sales_audit_options;
}

async function resolve_audit_context(frm, { trigger_field = null, manual = false } = {}) {
	if (frm.__resolving_daily_audit_context) {
		return null;
	}
	frm.__resolving_daily_audit_context = true;
	try {
		const response = await frappe.call({
			method: "retailedge.api.resolve_daily_sales_audit_context_from_selection",
			args: { filters: get_context_filters(frm) },
		});
		const resolved = response.message || {};
		await apply_resolved_context(frm, resolved, trigger_field, manual);
		await clear_unresolved_dependent_fields(frm, resolved, trigger_field);
		await refresh_context_options(frm);
		refresh_dependent_fields(frm);
		if (manual && resolved.messages && resolved.messages.length) {
			frappe.show_alert({
				message: resolved.messages.join(" "),
				indicator: "blue",
			});
		}
		return resolved;
	} finally {
		frm.__resolving_daily_audit_context = false;
	}
}

async function apply_resolved_context(frm, resolved, trigger_field, manual) {
	const source_map = resolved.source_map || {};
	const updates = {};
	for (const fieldname of context_fields()) {
		const value = resolved[fieldname];
		if (!value) {
			continue;
		}
		if (should_apply_resolved_value(frm, fieldname, value, trigger_field, manual, source_map[fieldname])) {
			updates[fieldname] = value;
		}
	}
	await apply_field_updates(frm, updates);
}

function should_apply_resolved_value(frm, fieldname, value, trigger_field, manual, source) {
	const current = frm.doc[fieldname];
	if (!value || current === value) {
		return false;
	}
	if (!current) {
		return true;
	}
	if (manual) {
		return ["pos_opening_shift", "pos_closing_shift"].includes(trigger_field) || !current;
	}
	if (trigger_field === "pos_opening_shift") {
		return ["company", "branch", "pos_profile", "cashier", "audit_date", "pos_closing_shift"].includes(fieldname);
	}
	if (trigger_field === "pos_closing_shift") {
		return ["company", "branch", "pos_profile", "cashier", "audit_date", "pos_opening_shift"].includes(fieldname);
	}
	if (trigger_field === "branch") {
		return fieldname === "pos_profile" && !frm.doc.pos_profile;
	}
	if (trigger_field === "pos_profile") {
		if (fieldname === "cashier") {
			return source === "Cashier Shift Match";
		}
		return ["company", "branch"].includes(fieldname) && !current;
	}
	if (trigger_field === "cashier") {
		if (fieldname === "branch") {
			return ["POS Opening Shift", "POS Closing Shift"].includes(source) && !current;
		}
		return ["pos_profile", "pos_opening_shift", "pos_closing_shift"].includes(fieldname) && !current;
	}
	return false;
}

function get_dependent_context_fields(trigger_field) {
	const order = context_field_order();
	const index = order.indexOf(trigger_field);
	if (index === -1) {
		return [];
	}
	return order.slice(index + 1);
}

function get_fields_to_clear_on_change(trigger_field) {
	const clear_map = {
		company: ["branch", "pos_profile", "cashier", "pos_opening_shift", "pos_closing_shift"],
		branch: ["pos_profile", "cashier", "pos_opening_shift", "pos_closing_shift"],
		pos_profile: ["cashier", "pos_opening_shift", "pos_closing_shift"],
		cashier: ["pos_opening_shift", "pos_closing_shift"],
		audit_date: ["pos_opening_shift", "pos_closing_shift"],
		pos_opening_shift: ["pos_closing_shift"],
		pos_closing_shift: [],
		manual: [],
	};
	return clear_map[trigger_field] || [];
}

async function clear_context_fields(frm, fieldnames) {
	const updates = {};
	for (const fieldname of fieldnames) {
		if (!fieldname || !frm.doc[fieldname]) {
			continue;
		}
		updates[fieldname] = "";
	}
	await apply_field_updates(frm, updates);
}

async function clear_dependent_context_fields(frm, trigger_field) {
	const fields_to_clear = get_fields_to_clear_on_change(trigger_field);
	if (!fields_to_clear.length) {
		return;
	}
	await clear_context_fields(frm, fields_to_clear);
}

async function clear_unresolved_dependent_fields(frm, resolved, trigger_field) {
	const dependent_fields = get_dependent_context_fields(trigger_field);
	if (!dependent_fields.length) {
		return;
	}
	const fields_to_clear = [];
	for (const fieldname of dependent_fields) {
		if (!frm.doc[fieldname]) {
			continue;
		}
		if (resolved[fieldname] && frm.doc[fieldname] === resolved[fieldname]) {
			continue;
		}
		if (resolved[fieldname]) {
			continue;
		}
		fields_to_clear.push(fieldname);
	}
	await clear_context_fields(frm, fields_to_clear);
}

async function apply_field_updates(frm, updates) {
	const entries = Object.entries(updates || {});
	if (!entries.length) {
		return;
	}
	for (const [fieldname, value] of entries) {
		await frm.set_value(fieldname, value);
	}
}

function refresh_dependent_fields(frm) {
	for (const fieldname of ["branch", "pos_profile", "cashier", "pos_opening_shift", "pos_closing_shift"]) {
		frm.refresh_field(fieldname);
	}
}

async function handle_context_change(frm, trigger_field) {
	if (frm.__resolving_daily_audit_context) {
		return;
	}
	await clear_dependent_context_fields(frm, trigger_field);
	await refresh_context_options(frm);
	await resolve_audit_context(frm, { trigger_field });
}

function has_daily_sales_audit_reviewer_role() {
	const roles = new Set(frappe.user_roles || []);
	return [
		"System Manager",
		"Accounts Manager",
		"Accounts User",
		"RetailEdge Manager",
		"RetailEdgeManager",
		"RetailEdge Branch Manager",
		"RetailEdgeBranchManager",
		"RetailEdge Auditor",
		"RetailEdgeAuditor",
	].some((role) => roles.has(role));
}
