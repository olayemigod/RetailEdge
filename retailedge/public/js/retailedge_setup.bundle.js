import RetailEdgeSetup from "./retailedge_setup/RetailEdgeSetup.vue";

function mountRetailEdgeSetup(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("RetailEdge Setup mount target is required");
	const app = edgeUI.createEdgeApp(RetailEdgeSetup);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeSetup = RetailEdgeSetup;
	window.mountRetailEdgeSetup = mountRetailEdgeSetup;
}

export { mountRetailEdgeSetup };
export default RetailEdgeSetup;
