import SalesReportingPage from "./sales_reporting/SalesReportingPage.vue";

function mountSalesReportingPage(target, options = {}) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Sales reporting.");
	}
	if (!target) throw new Error("Sales reporting mount target is required.");
	const app = edgeUI.createEdgeApp(SalesReportingPage, {
		reportType: options.reportType || "sales_by_item",
	});
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.SalesReportingPage = SalesReportingPage;
	window.mountSalesReportingPage = mountSalesReportingPage;
}

export { mountSalesReportingPage };
export default SalesReportingPage;
