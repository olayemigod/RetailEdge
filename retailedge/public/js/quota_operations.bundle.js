import QuotaOperationsCenter from "./quota_operations/QuotaOperationsCenter.vue";

function mountQuotaOperationsPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Quota Operations.");
	}
	if (!target) throw new Error("Quota Operations mount target is required.");
	const app = edgeUI.createEdgeApp(QuotaOperationsCenter);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.QuotaOperationsCenter = QuotaOperationsCenter;
	window.mountQuotaOperationsPage = mountQuotaOperationsPage;
}

export { mountQuotaOperationsPage };
export default QuotaOperationsCenter;
