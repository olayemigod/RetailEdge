import StockAdjustment from "./stock_adjustment/StockAdjustment.vue";

function mountRetailEdgeStockAdjustment(target) {
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Stock Adjustment mount target is required");
	const app = edgeUI.createEdgeApp(StockAdjustment);
	app.mount(target);
	return app;
}
if (typeof window !== "undefined") window.mountRetailEdgeStockAdjustment = mountRetailEdgeStockAdjustment;
export { mountRetailEdgeStockAdjustment };
export default StockAdjustment;
