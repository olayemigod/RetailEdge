import SupplierDocumentReview from "./supplier_document_review/SupplierDocumentReview.vue";

function mountSupplierDocumentReviewPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Supplier Document Review.");
	}
	if (!target) throw new Error("Supplier Document Review mount target is required.");
	const app = edgeUI.createEdgeApp(SupplierDocumentReview);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.SupplierDocumentReviewPage = SupplierDocumentReview;
	window.mountSupplierDocumentReviewPage = mountSupplierDocumentReviewPage;
}

export { mountSupplierDocumentReviewPage };
export default SupplierDocumentReview;
