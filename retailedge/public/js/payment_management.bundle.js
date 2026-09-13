import PaymentManagement from "./payment_management/PaymentManagement.vue";
import PaymentHistoryPanel from "./payment_management/PaymentHistoryPanel.vue";

function mountComponent(target, component, label) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error(`EdgeSuite UI runtime is unavailable for ${label}.`);
	}
	if (!target) throw new Error(`${label} mount target is required.`);
	const app = edgeUI.createEdgeApp(component);
	app.mount(target);
	return app;
}

function mountPaymentManagementPage(target) {
	return mountComponent(target, PaymentManagement, "Payment Management");
}

function mountPaymentHistoryPanel(target) {
	return mountComponent(target, PaymentHistoryPanel, "Payment History");
}

if (typeof window !== "undefined") {
	window.PaymentManagementPage = PaymentManagement;
	window.PaymentHistoryPanel = PaymentHistoryPanel;
	window.mountPaymentManagementPage = mountPaymentManagementPage;
	window.mountPaymentHistoryPanel = mountPaymentHistoryPanel;
}

export { mountPaymentHistoryPanel, mountPaymentManagementPage };
export default PaymentManagement;
