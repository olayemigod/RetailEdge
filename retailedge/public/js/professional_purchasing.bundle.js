import ProfessionalPurchasing from "./professional_purchasing/ProfessionalPurchasing.vue";

function mountRetailEdgeProfessionalPurchasing(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Professional Purchasing mount target is required");
	const app = edgeUI.createEdgeApp(ProfessionalPurchasing);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeProfessionalPurchasing = ProfessionalPurchasing;
	window.mountRetailEdgeProfessionalPurchasing = mountRetailEdgeProfessionalPurchasing;
}

export { mountRetailEdgeProfessionalPurchasing };
export default ProfessionalPurchasing;
