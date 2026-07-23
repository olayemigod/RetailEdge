export function installRetailEdgeWorkspaceRuntime(component) {
	if (!component || component.__retailedgeWorkspaceRuntimeInstalled) return component;

	const originalData = component.data;
	component.data = function () {
		const state = originalData.call(this);
		const selected = state.resourceOptions.some((option) => option.value === state.resource)
			? state.resource
			: state.resourceOptions[0]?.value || "branch-profiles";
		state.resource = selected;
		const route = new URLSearchParams(window.location.search || "");
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
