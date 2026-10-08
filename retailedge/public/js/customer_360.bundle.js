import Customer360 from "./customer_360/Customer360.vue";

function mountCustomer360(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
	}
	if (!target) throw new Error("Customer 360 mount target is required.");
	const app = edgeUI.createEdgeApp(Customer360);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.Customer360 = Customer360;
	window.mountCustomer360 = mountCustomer360;
}

export { mountCustomer360 };
export default Customer360;
