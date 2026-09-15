import ManagedReviewReport from "./managed_review_reports/ManagedReviewReport.vue";

window.mountManagedReviewReport = function mountManagedReviewReport(target, surfaceKey) {
	if (!target) return null;
	if (!window.EdgeSuiteUI?.createEdgeApp) throw new Error("Required interface runtime is unavailable.");
	const app = window.EdgeSuiteUI.createEdgeApp(ManagedReviewReport, { surfaceKey });
	app.mount(target);
	return app;
};
