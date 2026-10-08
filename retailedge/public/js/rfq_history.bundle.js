import RfqHistoryPage from "./professional_purchasing/RfqHistoryPage.vue";

function mountRetailEdgeRfqHistoryPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") throw new Error("This page could not start. Refresh the page or contact your administrator.");
	if (!target) throw new Error("RFQ History mount target is required.");
	const app = edgeUI.createEdgeApp(RfqHistoryPage);
	app.mount(target);
	return app;
}
if (typeof window !== "undefined") {
	window.RfqHistoryPage = RfqHistoryPage;
	window.mountRetailEdgeRfqHistoryPage = mountRetailEdgeRfqHistoryPage;
}
export { mountRetailEdgeRfqHistoryPage };
export default RfqHistoryPage;
