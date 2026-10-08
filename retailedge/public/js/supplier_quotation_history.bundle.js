import SupplierQuotationHistoryPage from "./professional_purchasing/SupplierQuotationHistoryPage.vue";

function mountRetailEdgeSupplierQuotationHistoryPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") throw new Error("This page could not start. Refresh the page or contact your administrator.");
	if (!target) throw new Error("Supplier Quotation History mount target is required.");
	const app = edgeUI.createEdgeApp(SupplierQuotationHistoryPage);
	app.mount(target);
	return app;
}
if (typeof window !== "undefined") {
	window.SupplierQuotationHistoryPage = SupplierQuotationHistoryPage;
	window.mountRetailEdgeSupplierQuotationHistoryPage = mountRetailEdgeSupplierQuotationHistoryPage;
}
export { mountRetailEdgeSupplierQuotationHistoryPage };
export default SupplierQuotationHistoryPage;
