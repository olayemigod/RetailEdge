import PaymentManagement from "./payment_management/PaymentManagement.vue";

function mountPaymentManagementPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Payment Management.");
	}
	if (!target) throw new Error("Payment Management mount target is required.");
	const app = edgeUI.createEdgeApp(PaymentManagement);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.PaymentManagementPage = PaymentManagement;
	window.mountPaymentManagementPage = mountPaymentManagementPage;
}

export { mountPaymentManagementPage };
export default PaymentManagement;
