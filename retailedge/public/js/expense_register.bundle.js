import ExpenseRegister from "./expense_register/ExpenseRegister.vue";

function mountExpenseRegister(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Expense Register.");
	}
	if (!target) throw new Error("Expense Register mount target is required.");
	const app = edgeUI.createEdgeApp(ExpenseRegister);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.ExpenseRegister = ExpenseRegister;
	window.mountExpenseRegister = mountExpenseRegister;
}

export { mountExpenseRegister };
export default ExpenseRegister;
