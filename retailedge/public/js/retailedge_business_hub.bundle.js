import RetailEdgeBusinessHub from "./retailedge_business_hub/RetailEdgeBusinessHub.vue";

function mountRetailEdgeBusinessHub(target) {
	if (typeof window === "undefined" || !window.EdgeSuiteUI) {
		throw new Error("Standalone EdgeSuite UI runtime not loaded.");
	}
	if (typeof window.EdgeSuiteUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI createEdgeApp API is unavailable.");
	}
	if (!target) {
		throw new Error("RetailEdge Business Hub mount target is unavailable.");
	}

	const app = window.EdgeSuiteUI.createEdgeApp(RetailEdgeBusinessHub);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.mountRetailEdgeBusinessHub = mountRetailEdgeBusinessHub;
}

export { mountRetailEdgeBusinessHub };
export default RetailEdgeBusinessHub;
