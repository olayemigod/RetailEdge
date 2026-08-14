import * as Vue from "vue";
import SalespersonPerformanceDashboard from "./salesperson_performance_dashboard/SalespersonPerformanceDashboard.vue";

function mountSalespersonPerformanceDashboard(target) {
	if (typeof window === "undefined") return null;

	if (!window.EdgeUI) {
		throw new Error("EdgeSuite UI runtime not loaded: window.EdgeUI is undefined");
	}
	if (!window.EdgeUI.createEdgeApp) {
		throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	}

	console.log("EdgeUI version:", window.EdgeUI.version);
	return window.EdgeUI.createEdgeApp(SalespersonPerformanceDashboard, target);
}

if (typeof window !== "undefined") {
	window.SalespersonPerformanceDashboard = SalespersonPerformanceDashboard;
	window.mountSalespersonPerformanceDashboard = mountSalespersonPerformanceDashboard;
}

export { mountSalespersonPerformanceDashboard };
export default SalespersonPerformanceDashboard;
