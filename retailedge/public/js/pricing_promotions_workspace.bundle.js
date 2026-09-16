import PricingPromotionsWorkspace from "./pricing_promotions/PricingPromotionsWorkspace.vue";

function mountPricingPromotionsWorkspace(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("Application interface runtime is unavailable.");
	}
	if (!target) throw new Error("Pricing & Promotions mount target is required.");
	const app = edgeUI.createEdgeApp(PricingPromotionsWorkspace);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.mountPricingPromotionsWorkspace = mountPricingPromotionsWorkspace;
}

export { mountPricingPromotionsWorkspace };
export default PricingPromotionsWorkspace;
