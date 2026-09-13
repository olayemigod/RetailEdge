import SalesDashboard from "./sales_dashboard/SalesDashboard.vue";

function mountSalesDashboard(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Sales Overview mount target is required");
	const app = edgeUI.createEdgeApp(SalesDashboard);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.SalesDashboard = SalesDashboard;
	window.mountSalesDashboard = mountSalesDashboard;
}

export { mountSalesDashboard };
export default SalesDashboard;
