import BusinessExpenses from "./business_expenses/BusinessExpenses.vue";

function mountRetailEdgeBusinessExpenses(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
	}
	if (!target) throw new Error("Business Expenses mount target is required.");
	const app = edgeUI.createEdgeApp(BusinessExpenses);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeBusinessExpenses = BusinessExpenses;
	window.mountRetailEdgeBusinessExpenses = mountRetailEdgeBusinessExpenses;
}

export { mountRetailEdgeBusinessExpenses };
export default BusinessExpenses;
