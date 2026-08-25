import ProfessionalSelling from "./professional_selling/ProfessionalSelling.vue";

function mountRetailEdgeProfessionalSelling(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Professional Selling mount target is required");
	const app = edgeUI.createEdgeApp(ProfessionalSelling);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeProfessionalSelling = ProfessionalSelling;
	window.mountRetailEdgeProfessionalSelling = mountRetailEdgeProfessionalSelling;
}

export { mountRetailEdgeProfessionalSelling };
export default ProfessionalSelling;
