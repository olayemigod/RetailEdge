import SalespersonPerformanceDashboard from "./salesperson_performance_dashboard/SalespersonPerformanceDashboardV2.vue";

function mountSalespersonPerformanceDashboard(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) {
		throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	}
	if (!target) {
		throw new Error("Salesperson Performance Dashboard mount target is required");
	}
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
