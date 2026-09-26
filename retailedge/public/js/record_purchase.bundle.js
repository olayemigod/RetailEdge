import RecordPurchase from "./record_purchase/RecordPurchase.vue";

function mountRetailEdgeRecordPurchase(target) {
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Record Purchase mount target is required");
	const app = edgeUI.createEdgeApp(RecordPurchase);
	app.mount(target);
	return app;
}
if (typeof window !== "undefined") window.mountRetailEdgeRecordPurchase = mountRetailEdgeRecordPurchase;
export { mountRetailEdgeRecordPurchase };
export default RecordPurchase;
