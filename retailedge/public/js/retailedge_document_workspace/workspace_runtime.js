const EXTRA_RESOURCE_OPTIONS = Object.freeze([
	{ value: "expense-categories", label: "Expense Categories" },
	{ value: "statement-mapping-templates", label: "Statement Mapping Templates" },
]);

function mergeResourceOptions(options = []) {
	const seen = new Set();
	return [...options, ...EXTRA_RESOURCE_OPTIONS].filter((option) => {
		if (!option?.value || seen.has(option.value)) return false;
		seen.add(option.value);
		return true;
	});
}

export function installRetailEdgeWorkspaceRuntime(component) {
	if (!component || component.__retailedgeWorkspaceRuntimeInstalled) return component;

	const originalData = component.data;
	component.data = function () {
		const state = originalData.call(this);
		state.resourceOptions = mergeResourceOptions(state.resourceOptions);
		const route = new URLSearchParams(window.location.search || "");
		const requested = route.get("resource") || state.resource;
		const selected = state.resourceOptions.some((option) => option.value === requested)
			? requested
			: state.resourceOptions[0]?.value || "branch-profiles";
		state.resource = selected;
		state.mode = selected === "settings" || route.get("name") || route.get("new") === "1" ? "form" : "list";
		return state;
	};

	component.methods.childLinkSearch = function (field, query) {
		const childDoctype = this.resource === "settings"
			? "RetailEdge Posting Date Role"
			: "RetailEdge Branch Profile User";
		return this.call("retailedge.document_workspace.get_link_options", {
			resource: this.resource,
			fieldname: field.fieldname,
			query,
			values: this.model,
			child_doctype: childDoctype,
			page_length: 20,
		});
	};

	component.methods.changeResource = async function () {
		const previous = this.definition?.resource || "branch-profiles";
		if (!this.confirmDiscard()) {
			this.resource = previous;
			return;
		}
		this.search = "";
		this.filters = {};
		this.mode = this.resource === "settings" ? "form" : "list";
		await this.loadDefinition();
	};

	component.__retailedgeWorkspaceRuntimeInstalled = true;
	return component;
}
