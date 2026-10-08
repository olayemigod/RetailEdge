import PurchaseReceiptHistoryPage from "./professional_purchasing/PurchaseReceiptHistoryPage.vue";

function mountRetailEdgePurchaseReceiptHistoryPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
	}
	if (!target) throw new Error("Purchase Receipt History mount target is required.");
	const app = edgeUI.createEdgeApp(PurchaseReceiptHistoryPage);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.PurchaseReceiptHistoryPage = PurchaseReceiptHistoryPage;
	window.mountRetailEdgePurchaseReceiptHistoryPage = mountRetailEdgePurchaseReceiptHistoryPage;
}

export { mountRetailEdgePurchaseReceiptHistoryPage };
export default PurchaseReceiptHistoryPage;
