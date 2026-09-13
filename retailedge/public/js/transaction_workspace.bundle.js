import TransactionWorkspace from "./transaction_workspace/TransactionWorkspace.vue";

function mountRetailEdgeTransactionWorkspace(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Transaction Workspace mount target is required");
	const app = edgeUI.createEdgeApp(TransactionWorkspace);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeTransactionWorkspace = TransactionWorkspace;
	window.mountRetailEdgeTransactionWorkspace = mountRetailEdgeTransactionWorkspace;
}

export { mountRetailEdgeTransactionWorkspace };
export default TransactionWorkspace;
