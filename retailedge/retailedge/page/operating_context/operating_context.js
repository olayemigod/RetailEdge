frappe.pages["operating-context"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Operating Context"),
		single_column: true,
	});
	wrapper.retailedgeOperatingContextState = {
		page,
		loading: false,
		companyControl: null,
		branchControl: null,
		current: null,
		data: null,
	};
	buildOperatingContextPage(wrapper);
};

frappe.pages["operating-context"].on_page_show = function (wrapper) {
	loadOperatingContext(wrapper);
};

function buildOperatingContextPage(wrapper) {
	const state = wrapper.retailedgeOperatingContextState;
	const page = state.page;
	const container = document.createElement("div");
	container.className = "retailedge-operating-context";
	container.innerHTML = `
		<div class="frappe-card" style="padding: 20px; max-width: 760px;">
			<h3 style="margin-top: 0;">${__("Choose where new work starts")}</h3>
			<p class="text-muted">${__(
				"Your Operating Branch guides new drafts and defaults. Existing documents keep their saved company, branch, stock location, and accounting values."
			)}</p>
			<div class="retailedge-operating-context-current" style="margin: 18px 0;"></div>
			<div class="retailedge-operating-context-fields"></div>
			<div class="retailedge-operating-context-blockers" style="margin-top: 16px;"></div>
		</div>
	`;
	page.main.append(container);

	const fields = container.querySelector(".retailedge-operating-context-fields");
	const companyParent = document.createElement("div");
	const branchParent = document.createElement("div");
	fields.append(companyParent, branchParent);

	state.companyControl = frappe.ui.form.make_control({
		parent: companyParent,
		df: {
			fieldtype: "Select",
			fieldname: "operating_company",
			label: __("Operating Company"),
			options: [],
			reqd: 1,
		},
		render_input: true,
	});
	state.branchControl = frappe.ui.form.make_control({
		parent: branchParent,
		df: {
			fieldtype: "Select",
			fieldname: "operating_branch",
			label: __("Operating Branch"),
			options: [],
			reqd: 1,
		},
		render_input: true,
	});

	state.companyControl.df.onchange = async () => {
		const company = state.companyControl.get_value();
		await loadOperatingContext(wrapper, { company, preserveCompanySelection: true });
	};

	page.set_primary_action(__("Use Selected Branch"), async () => {
		await switchOperatingContext(wrapper);
	});
	page.add_inner_button(__("Restore Default"), async () => {
		await clearOperatingContext(wrapper);
	});
}

async function loadOperatingContext(wrapper, options = {}) {
	const state = wrapper.retailedgeOperatingContextState;
	if (!state || state.loading) return;
	state.loading = true;
	try {
		const response = await frappe.call({
			method: "retailedge.operating_context.get_allowed_operating_contexts",
			args: { company: options.company || "" },
		});
		const data = response.message || {};
		state.data = data;
		state.current = data.current || {};

		setSelectOptions(state.companyControl, data.companies || []);
		const selectedCompany = options.preserveCompanySelection
			? options.company || data.selected_company || ""
			: data.current?.company || data.selected_company || "";
		await state.companyControl.set_value(selectedCompany);

		setSelectOptions(state.branchControl, data.branches || []);
		const currentBranchMatchesCompany = data.current?.company === selectedCompany;
		const selectedBranch = currentBranchMatchesCompany ? data.current?.branch || "" : "";
		await state.branchControl.set_value(
			(data.branches || []).includes(selectedBranch) ? selectedBranch : ""
		);
		renderCurrentContext(wrapper);
		renderSwitchBlockers(wrapper);
	} catch (error) {
		frappe.msgprint({
			title: __("Unable to load Operating Context"),
			message: error?.message || __("The permitted Company and Branch options could not be loaded."),
			indicator: "red",
		});
	} finally {
		state.loading = false;
	}
}

function setSelectOptions(control, values) {
	const options = ["", ...(Array.isArray(values) ? values : [])];
	control.df.options = options.join("\n");
	control.refresh();
}

function renderCurrentContext(wrapper) {
	const state = wrapper.retailedgeOperatingContextState;
	const target = wrapper.querySelector(".retailedge-operating-context-current");
	if (!target) return;
	const current = state.current || {};
	target.textContent = "";
	const heading = document.createElement("div");
	heading.className = "text-muted small";
	heading.textContent = __("Current operating context");
	const value = document.createElement("div");
	value.style.fontWeight = "600";
	value.style.marginTop = "4px";
	value.textContent = current.company
		? `${current.company}${current.branch ? ` · ${current.branch}` : ""}`
		: __("No operating context selected");
	target.append(heading, value);
}

function renderSwitchBlockers(wrapper) {
	const state = wrapper.retailedgeOperatingContextState;
	const target = wrapper.querySelector(".retailedge-operating-context-blockers");
	if (!target) return;
	target.textContent = "";
	const blockers = state.data?.switch_blockers || [];
	for (const blocker of blockers) {
		const note = document.createElement("div");
		note.className = "alert alert-warning";
		note.textContent = blocker.message || __("Active work may prevent switching Branch.");
		target.append(note);
	}
}

async function switchOperatingContext(wrapper) {
	const state = wrapper.retailedgeOperatingContextState;
	const company = state.companyControl?.get_value() || "";
	const branch = state.branchControl?.get_value() || "";
	if (!company || !branch) {
		frappe.msgprint(__("Choose both Operating Company and Operating Branch."));
		return;
	}

	if (showClientSwitchBlocker()) return;

	const response = await frappe.call({
		method: "retailedge.operating_context.switch_operating_context",
		args: { company, branch },
		freeze: true,
		freeze_message: __("Updating operating branch..."),
	});
	state.current = response.message || {};
	invalidateRetailEdgeContextCache();
	frappe.show_alert({ message: __("Operating branch updated."), indicator: "green" });
	await loadOperatingContext(wrapper);
}

async function clearOperatingContext(wrapper) {
	if (showClientSwitchBlocker()) return;

	await frappe.call({
		method: "retailedge.operating_context.clear_operating_context",
		freeze: true,
		freeze_message: __("Restoring default operating branch..."),
	});
	invalidateRetailEdgeContextCache();
	frappe.show_alert({ message: __("Default operating branch restored."), indicator: "green" });
	await loadOperatingContext(wrapper);
}

function showClientSwitchBlocker() {
	const clientBlocker = getClientSwitchBlocker();
	if (!clientBlocker) return false;
	frappe.msgprint({
		title: __("Finish current work before switching"),
		message: clientBlocker,
		indicator: "orange",
	});
	return true;
}

function getClientSwitchBlocker() {
	try {
		const guard = window.retailedgeOperatingContextGuard;
		if (guard && typeof guard.getBlocker === "function") {
			return guard.getBlocker() || "";
		}
	} catch (error) {
		return __("The current transaction state could not be verified. Finish the current work before switching Branch.");
	}
	return "";
}

function invalidateRetailEdgeContextCache() {
	window.__retailedgeBusinessHubContextCache = null;
	window.__retailedgeBusinessHubContextRequest = null;
	window.retailedgeInstallProductMenu?.({ force: true });
	document.dispatchEvent(new CustomEvent("retailedge-operating-context-changed"));
}
