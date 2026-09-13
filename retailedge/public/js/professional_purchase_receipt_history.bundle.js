import ProfessionalPurchaseReceiptHistoryOverlay from "./professional_purchasing/ProfessionalPurchaseReceiptHistoryOverlay.vue";

function mountRetailEdgeProfessionalPurchaseReceiptHistory(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Professional Purchase Receipt history mount target is required");
	const app = edgeUI.createEdgeApp(ProfessionalPurchaseReceiptHistoryOverlay);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.mountRetailEdgeProfessionalPurchaseReceiptHistory = mountRetailEdgeProfessionalPurchaseReceiptHistory;
}

export { mountRetailEdgeProfessionalPurchaseReceiptHistory };
export default ProfessionalPurchaseReceiptHistoryOverlay;
