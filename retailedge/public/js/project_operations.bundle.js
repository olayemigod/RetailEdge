import ProjectOperations from "./project_operations/ProjectOperations.vue";

function mountProjectOperationsPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
	}
	if (!target) throw new Error("Project Operations mount target is required.");
	const app = edgeUI.createEdgeApp(ProjectOperations);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.ProjectOperationsPage = ProjectOperations;
	window.mountProjectOperationsPage = mountProjectOperationsPage;
}

export { mountProjectOperationsPage };
export default ProjectOperations;
