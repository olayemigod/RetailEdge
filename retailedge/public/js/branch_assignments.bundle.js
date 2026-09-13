import BranchAssignments from "./branch_assignments/BranchAssignments.vue";

function mountRetailEdgeBranchAssignments(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Branch Assignments mount target is required");
	const app = edgeUI.createEdgeApp(BranchAssignments);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeBranchAssignments = BranchAssignments;
	window.mountRetailEdgeBranchAssignments = mountRetailEdgeBranchAssignments;
}

export { mountRetailEdgeBranchAssignments };
export default BranchAssignments;
