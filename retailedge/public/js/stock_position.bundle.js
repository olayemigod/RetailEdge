import StockPosition from "./stock_position/StockPosition.vue";

function mountStockPosition(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Stock Position.");
	}
	if (!target) throw new Error("Stock Position mount target is required.");
	const app = edgeUI.createEdgeApp(StockPosition);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.StockPosition = StockPosition;
	window.mountStockPosition = mountStockPosition;
}

export { mountStockPosition };
export default StockPosition;
