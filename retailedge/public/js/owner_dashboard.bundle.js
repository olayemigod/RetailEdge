import OwnerDashboard from "./owner_dashboard/OwnerDashboard.vue";

function mountOwnerDashboard(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Owner Dashboard mount target is required");
	const app = edgeUI.createEdgeApp(OwnerDashboard);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.OwnerDashboard = OwnerDashboard;
	window.mountOwnerDashboard = mountOwnerDashboard;
}

export { mountOwnerDashboard };
export default OwnerDashboard;
