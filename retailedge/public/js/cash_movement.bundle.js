import CashMovement from "./cash_movement/CashMovement.vue";

function mountCashMovement(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Cash Movement.");
	}
	if (!target) throw new Error("Cash Movement mount target is required.");
	const app = edgeUI.createEdgeApp(CashMovement);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.CashMovement = CashMovement;
	window.mountCashMovement = mountCashMovement;
}

export { mountCashMovement };
export default CashMovement;
