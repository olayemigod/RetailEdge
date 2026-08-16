import StockMovementHistory from "./stock_movement_history/StockMovementHistory.vue";

function mountStockMovementHistory(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Stock Movement History.");
	}
	if (!target) {
		throw new Error("Stock Movement History mount target is required.");
	}
	const app = edgeUI.createEdgeApp(StockMovementHistory);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.StockMovementHistory = StockMovementHistory;
	window.mountStockMovementHistory = mountStockMovementHistory;
}

export { mountStockMovementHistory };
export default StockMovementHistory;
