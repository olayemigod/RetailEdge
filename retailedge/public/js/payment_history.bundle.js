import PaymentHistoryPage from "./payment_management/PaymentHistoryPage.vue";

function mountPaymentHistoryPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
	}
	if (!target) throw new Error("Payment History mount target is required.");
	const app = edgeUI.createEdgeApp(PaymentHistoryPage);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.PaymentHistoryPage = PaymentHistoryPage;
	window.mountPaymentHistoryPage = mountPaymentHistoryPage;
}

export { mountPaymentHistoryPage };
export default PaymentHistoryPage;
