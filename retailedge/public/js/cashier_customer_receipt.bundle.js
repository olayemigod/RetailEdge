import CashierCustomerReceipt from "./cashier_customer_receipt/CashierCustomerReceipt.vue";

function mountCashierCustomerReceipt(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
	}
	if (!target) throw new Error("Receive Payment mount target is required.");
	const app = edgeUI.createEdgeApp(CashierCustomerReceipt);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.CashierCustomerReceipt = CashierCustomerReceipt;
	window.mountCashierCustomerReceipt = mountCashierCustomerReceipt;
}

export { mountCashierCustomerReceipt };
export default CashierCustomerReceipt;
