import RetailEdgeDocumentWorkspace from "./retailedge_document_workspace/RetailEdgeDocumentWorkspace.vue";
import { installRetailEdgeWorkspaceRuntime } from "./retailedge_document_workspace/workspace_runtime";
import { createRetailEdgeApp } from "./retailedge_ui/app_factory";

let activeApp = null;
const WorkspaceComponent = installRetailEdgeWorkspaceRuntime(RetailEdgeDocumentWorkspace);

export function mountRetailEdgeDocumentWorkspace(target) {
	if (!target) throw new TypeError("RetailEdge Document Workspace mount target is required.");
	if (activeApp?.unmount) activeApp.unmount();
	activeApp = createRetailEdgeApp(WorkspaceComponent);
	activeApp.mount(target);
	return activeApp;
}

export function unmountRetailEdgeDocumentWorkspace() {
	if (activeApp?.unmount) activeApp.unmount();
	activeApp = null;
}

if (typeof window !== "undefined") {
	window.mountRetailEdgeDocumentWorkspace = mountRetailEdgeDocumentWorkspace;
	window.unmountRetailEdgeDocumentWorkspace = unmountRetailEdgeDocumentWorkspace;
}

export default WorkspaceComponent;
