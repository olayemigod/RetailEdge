import NativeERPNextWorkspace from "./native_visual_workspaces/NativeERPNextWorkspace.vue";

function mountNativeERPNextWorkspace(target, workspaceKey) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for the RetailEdge control workspace.");
	}
	if (!target) throw new Error("RetailEdge control workspace mount target is required.");
	if (!workspaceKey) throw new Error("RetailEdge control workspace key is required.");
	const app = edgeUI.createEdgeApp(NativeERPNextWorkspace, { workspaceKey });
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.NativeERPNextWorkspace = NativeERPNextWorkspace;
	window.mountNativeERPNextWorkspace = mountNativeERPNextWorkspace;
}

export { mountNativeERPNextWorkspace };
export default NativeERPNextWorkspace;
