import BranchSetup from "./branch_setup/BranchSetup.vue";

function mountRetailEdgeBranchSetup(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Branch Setup mount target is required");
	const app = edgeUI.createEdgeApp(BranchSetup);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeBranchSetup = BranchSetup;
	window.mountRetailEdgeBranchSetup = mountRetailEdgeBranchSetup;
}

export { mountRetailEdgeBranchSetup };
export default BranchSetup;
