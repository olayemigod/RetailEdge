import SalesQualityIntelligence from "./sales_quality_intelligence/SalesQualityIntelligence.vue";

function mountSalesQualityIntelligence(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Discount & Sales Quality.");
	}
	if (!target) throw new Error("Discount & Sales Quality mount target is required.");
	const app = edgeUI.createEdgeApp(SalesQualityIntelligence, {
		pageMethod: "retailedge.sales_quality_intelligence.get_sales_quality_intelligence",
		exportMethod: "retailedge.sales_quality_intelligence.get_sales_quality_intelligence_export",
	});
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.SalesQualityIntelligence = SalesQualityIntelligence;
	window.mountSalesQualityIntelligence = mountSalesQualityIntelligence;
}

export { mountSalesQualityIntelligence };
export default SalesQualityIntelligence;
