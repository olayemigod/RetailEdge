import RfqHistoryPage from "./professional_purchasing/RfqHistoryPage.vue";

function mountRetailEdgeRfqHistoryPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") throw new Error("EdgeSuite UI runtime is unavailable for RFQ History.");
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
