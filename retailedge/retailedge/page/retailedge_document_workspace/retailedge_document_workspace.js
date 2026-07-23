async function mountRetailEdgeDocumentWorkspacePage(wrapper) {
	if (wrapper.__retailedge_document_workspace_mounting || wrapper.retailedge_document_workspace_app) return;
	wrapper.__retailedge_document_workspace_mounting = true;
	const page = wrapper.page;
	const loading = $(
		'<div class="edge-boot-loading text-center text-muted" style="padding: 24px;">' +
			__("Loading RetailEdge Setup Workspace…") +
			"</div>",
	).appendTo(page.body);

	try {
		const requireAsync = (asset, timeout = 8000) =>
			new Promise((resolve, reject) => {
				let completed = false;
				frappe.require(asset, () => {
					completed = true;
					resolve();
				});
				window.setTimeout(() => {
					if (!completed) reject(new Error(`Timed out loading ${asset}.`));
				}, timeout);
			});

		await requireAsync("edgeui.bundle.js");
		await requireAsync("retailedge_document_workspace.bundle.js");
		if (typeof window.mountRetailEdgeDocumentWorkspace !== "function") {
			throw new Error("RetailEdge Setup Workspace mount function is unavailable.");
		}

		loading.remove();
		page.body.find(".retailedge-document-workspace-root, .retailedge-document-workspace-error").remove();
		const target = $('<div class="retailedge-document-workspace-root"></div>').appendTo(page.body);
		wrapper.retailedge_document_workspace_app = window.mountRetailEdgeDocumentWorkspace(target[0]);
	} catch (error) {
		loading.remove();
		page.body.find(".retailedge-document-workspace-error").remove();
		const block = $('<div class="alert alert-danger retailedge-document-workspace-error" style="margin: 20px;"></div>').appendTo(page.body);
		$("<strong></strong>").text(__("RetailEdge Setup Workspace failed to load")).appendTo(block);
		$("<div></div>").text(error?.message || String(error)).appendTo(block);
	} finally {
		wrapper.__retailedge_document_workspace_mounting = false;
	}
}

frappe.pages["retailedge-document-workspace"].on_page_load = function (wrapper) {
	wrapper.page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("RetailEdge Setup Workspace"),
		single_column: true,
	});
	mountRetailEdgeDocumentWorkspacePage(wrapper);
};

frappe.pages["retailedge-document-workspace"].on_page_show = function (wrapper) {
	if (wrapper.page && !wrapper.retailedge_document_workspace_app) {
		mountRetailEdgeDocumentWorkspacePage(wrapper);
	}
};

frappe.pages["retailedge-document-workspace"].on_page_hide = function (wrapper) {
	if (wrapper.retailedge_document_workspace_app?.unmount) {
		wrapper.retailedge_document_workspace_app.unmount();
		wrapper.retailedge_document_workspace_app = null;
	}
	wrapper.page?.body?.find(".retailedge-document-workspace-root")?.remove();
};
