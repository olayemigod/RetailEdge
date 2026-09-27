import TransferStock from "./transfer_stock/TransferStock.vue";

function mountRetailEdgeTransferStock(target) {
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Transfer Stock mount target is required");
	const app = edgeUI.createEdgeApp(TransferStock);
	app.mount(target);
	return app;
}
if (typeof window !== "undefined") window.mountRetailEdgeTransferStock = mountRetailEdgeTransferStock;
export { mountRetailEdgeTransferStock };
export default TransferStock;
