import DocumentOutputSharing from "./document_output_sharing/DocumentOutputSharing.vue";

function mountRetailEdgeDocumentOutputSharing(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Document Output & Sharing mount target is required");
	const app = edgeUI.createEdgeApp(DocumentOutputSharing);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeDocumentOutputSharing = DocumentOutputSharing;
	window.mountRetailEdgeDocumentOutputSharing = mountRetailEdgeDocumentOutputSharing;
}

export { mountRetailEdgeDocumentOutputSharing };
export default DocumentOutputSharing;
