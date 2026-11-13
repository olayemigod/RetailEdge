import CashierMyWork from "./cashier_my_work/CashierMyWork.vue";

function mountCashierMyWork(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
	}
	if (!target) throw new Error("RetailEdge My Work mount target is required.");
	const app = edgeUI.createEdgeApp(CashierMyWork);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.CashierMyWork = CashierMyWork;
	window.mountCashierMyWork = mountCashierMyWork;
}

export { mountCashierMyWork };
export default CashierMyWork;
