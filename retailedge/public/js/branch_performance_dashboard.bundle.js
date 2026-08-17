import BranchPerformanceDashboard from "./branch_performance_dashboard/BranchPerformanceDashboard.vue";

function mountBranchPerformanceDashboard(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Branch Performance Dashboard mount target is required");
	const app = edgeUI.createEdgeApp(BranchPerformanceDashboard);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.BranchPerformanceDashboard = BranchPerformanceDashboard;
	window.mountBranchPerformanceDashboard = mountBranchPerformanceDashboard;
}

export { mountBranchPerformanceDashboard };
export default BranchPerformanceDashboard;
