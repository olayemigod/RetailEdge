import ProfessionalPurchaseOrderOverlay from "./professional_purchasing/ProfessionalPurchaseOrderOverlay.vue";

function mountRetailEdgeProfessionalPurchaseOrder(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Professional Purchase Order mount target is required");
	const app = edgeUI.createEdgeApp(ProfessionalPurchaseOrderOverlay);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.mountRetailEdgeProfessionalPurchaseOrder = mountRetailEdgeProfessionalPurchaseOrder;
}

export { mountRetailEdgeProfessionalPurchaseOrder };
export default ProfessionalPurchaseOrderOverlay;
