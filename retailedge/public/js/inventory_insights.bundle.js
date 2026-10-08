import InventoryInsightView from "./inventory_insights/InventoryInsightView.vue";

const PAGE_METHOD = "retailedge.inventory_insight_views.get_inventory_insight_view";

function mountInventoryInsightView(target, options = {}) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
	}
	if (!target) throw new Error("Inventory insight mount target is required.");
	if (!options.view) throw new Error("Inventory insight view is required.");
	const app = edgeUI.createEdgeApp(InventoryInsightView, {
		view: options.view,
		pageMethod: PAGE_METHOD,
	});
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.InventoryInsightView = InventoryInsightView;
	window.mountInventoryInsightView = mountInventoryInsightView;
}

export { mountInventoryInsightView };
export default InventoryInsightView;
