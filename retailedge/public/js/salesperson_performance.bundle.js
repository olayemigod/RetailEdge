import * as Vue from "vue";
import SalespersonPerformanceDashboard from "./salesperson_performance_dashboard/SalespersonPerformanceDashboard.vue";

function mountSalespersonPerformanceDashboard(target) {
	if (typeof window === "undefined") return null;

	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI) {
		throw new Error("EdgeSuite UI runtime not loaded: window.EdgeSuiteUI is undefined");
	}
	if (typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	}
	if (!target) {
		throw new Error("Salesperson Performance Dashboard mount target is required");
	}

	console.log("EdgeSuite UI version:", edgeUI.version);
	const app = edgeUI.createEdgeApp(SalespersonPerformanceDashboard);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.SalespersonPerformanceDashboard = SalespersonPerformanceDashboard;
	window.mountSalespersonPerformanceDashboard = mountSalespersonPerformanceDashboard;
}

export { mountSalespersonPerformanceDashboard };
export default SalespersonPerformanceDashboard;
