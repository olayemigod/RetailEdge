import ProfessionalPurchaseReceiptPreviewOverlay from "./professional_purchasing/ProfessionalPurchaseReceiptPreviewOverlay.vue";

function mountRetailEdgeProfessionalPurchaseReceiptPreview(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Professional Purchase Receipt preview mount target is required");
	const app = edgeUI.createEdgeApp(ProfessionalPurchaseReceiptPreviewOverlay);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.mountRetailEdgeProfessionalPurchaseReceiptPreview = mountRetailEdgeProfessionalPurchaseReceiptPreview;
}

export { mountRetailEdgeProfessionalPurchaseReceiptPreview };
export default ProfessionalPurchaseReceiptPreviewOverlay;
