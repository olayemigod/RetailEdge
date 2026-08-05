frappe.pages['retailedge-business-hub'].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('RetailEdge Business Hub'),
		single_column: true,
	});
	wrapper.page = page;

	const loading = $('<div class="edge-boot-loading p-6 text-center text-muted"></div>')
		.text(__('Loading RetailEdge Business Hub...'))
		.appendTo(page.body);

	try {
		await requireAsset('edgesuite_ui.bundle.js');
		assertEdgeSuiteUIRuntime();
		await requireAsset('retailedge_business_hub.bundle.js');

		if (typeof window.mountRetailEdgeBusinessHub !== 'function') {
			throw new Error(__('RetailEdge Business Hub mount function is unavailable.'));
		}

		loading.remove();
		const root = $('<div class="retailedge-business-hub-root"></div>').appendTo(page.body);
		wrapper._retailedgeBusinessHub = window.mountRetailEdgeBusinessHub(root[0]);
	} catch (error) {
		loading.remove();
		renderFailure(page.body, error);
	}
};

frappe.pages['retailedge-business-hub'].on_page_show = function (wrapper) {
	const instance = wrapper._retailedgeBusinessHub;
	const component = instance && instance._instance && instance._instance.proxy;
	if (component && typeof component.refreshContext === 'function') {
		component.refreshContext();
	}
};

function requireAsset(asset) {
	return new Promise((resolve, reject) => {
		let completed = false;
		frappe.require(asset, () => {
			completed = true;
			resolve();
		});
		window.setTimeout(() => {
			if (!completed) {
				reject(new Error(__('Timed out loading {0}', [asset])));
			}
		}, 10000);
	});
}

function assertEdgeSuiteUIRuntime() {
	const runtime = window.EdgeSuiteUI;
	if (!runtime || typeof runtime.createEdgeApp !== 'function') {
		throw new Error(__('Standalone EdgeSuite UI runtime is unavailable or incompatible.'));
	}
	const components = runtime.components || runtime;
	const required = [
		'EdgeAppShell',
		'EdgePageLayout',
		'EdgePageHeader',
		'EdgeLoadingState',
		'EdgeErrorState',
		'EdgeEmptyState',
		'EdgeStatusBadge',
	];
	const missing = required.filter((name) => !components[name]);
	if (missing.length) {
		throw new Error(__('EdgeSuite UI is missing required components: {0}', [missing.join(', ')]));
	}
}

function renderFailure(target, error) {
	const message = error && error.message ? error.message : __('Unknown loading error.');
	$('<div class="alert alert-danger p-6 text-center"></div>')
		.append($('<strong></strong>').text(__('RetailEdge Business Hub failed to load')))
		.append($('<div class="mt-2"></div>').text(message))
		.appendTo(target);
}
