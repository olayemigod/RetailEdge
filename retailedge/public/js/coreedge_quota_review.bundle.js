import CoreEdgeQuotaReview from "./coreedge_quota_review/CoreEdgeQuotaReview.vue";

function mountCoreEdgeQuotaReview(target) {
	if (!target) throw new Error("Quota Operations Review mount target is required.");
	if (!window.EdgeSuiteUI?.createEdgeApp) {
		throw new Error("EdgeSuite UI runtime is unavailable for Quota Operations Review.");
	}
	const app = window.EdgeSuiteUI.createEdgeApp(CoreEdgeQuotaReview);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.mountCoreEdgeQuotaReview = mountCoreEdgeQuotaReview;
}

export { mountCoreEdgeQuotaReview };
export default CoreEdgeQuotaReview;
