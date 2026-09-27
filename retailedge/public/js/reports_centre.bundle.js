import ReportsCentre from "./reports_centre/ReportsCentre.vue";

function mountReportsCentre(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) {
		throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	}
	if (!target) throw new Error("Reports Centre mount target is required");
	const app = edgeUI.createEdgeApp(ReportsCentre);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.ReportsCentre = ReportsCentre;
	window.mountReportsCentre = mountReportsCentre;
}

export { mountReportsCentre };
export default ReportsCentre;
