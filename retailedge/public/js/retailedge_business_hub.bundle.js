import RetailEdgeBusinessHub from "./retailedge_business_hub/RetailEdgeBusinessHub.vue";

function mountRetailEdgeBusinessHub(target) {
	if (typeof window === "undefined" || !window.EdgeSuiteUI) {
		throw new Error("Standalone EdgeSuite UI runtime not loaded.");
	}
	if (typeof window.EdgeSuiteUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI createEdgeApp API is unavailable.");
	}
	return window.EdgeSuiteUI.createEdgeApp(RetailEdgeBusinessHub, target);
}

if (typeof window !== "undefined") {
	window.mountRetailEdgeBusinessHub = mountRetailEdgeBusinessHub;
}

export { mountRetailEdgeBusinessHub };
export default RetailEdgeBusinessHub;
