import BankStatementImports from "./bank_statement_imports/BankStatementImports.vue";

function mountRetailEdgeBankStatementImports(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Bank Statement Imports.");
	}
	if (!target) throw new Error("Bank Statement Imports mount target is required.");
	const app = edgeUI.createEdgeApp(BankStatementImports);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeBankStatementImports = BankStatementImports;
	window.mountRetailEdgeBankStatementImports = mountRetailEdgeBankStatementImports;
}

export { mountRetailEdgeBankStatementImports };
export default BankStatementImports;
