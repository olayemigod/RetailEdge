import ProfitabilityIntelligence from "./profitability_intelligence/ProfitabilityIntelligence.vue";

function mountProfitabilityIntelligence(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Profitability Intelligence mount target is required");
	const app = edgeUI.createEdgeApp(ProfitabilityIntelligence);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.ProfitabilityIntelligence = ProfitabilityIntelligence;
	window.mountProfitabilityIntelligence = mountProfitabilityIntelligence;
}

export { mountProfitabilityIntelligence };
export default ProfitabilityIntelligence;
