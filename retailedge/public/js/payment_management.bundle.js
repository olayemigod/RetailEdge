import PaymentManagement from "./payment_management/PaymentManagement.vue";

function mountComponent(target, component, label) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error(`This page could not start. Refresh the page or contact your administrator.`);
	}
	if (!target) throw new Error(`${label} mount target is required.`);
	const app = edgeUI.createEdgeApp(component);
	app.mount(target);
	return app;
}

function mountPaymentManagementPage(target) {
	return mountComponent(target, PaymentManagement, "Payment Management");
}


if (typeof window !== "undefined") {
	window.PaymentManagementPage = PaymentManagement;
	window.mountPaymentManagementPage = mountPaymentManagementPage;
}

export { mountPaymentManagementPage };
export default PaymentManagement;
