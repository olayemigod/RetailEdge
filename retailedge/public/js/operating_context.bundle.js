import OperatingContext from "./operating_context/OperatingContext.vue";

function mountRetailEdgeOperatingContext(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Operating Context mount target is required");
	const app = edgeUI.createEdgeApp(OperatingContext);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeOperatingContext = OperatingContext;
	window.mountRetailEdgeOperatingContext = mountRetailEdgeOperatingContext;
}

export { mountRetailEdgeOperatingContext };
export default OperatingContext;
