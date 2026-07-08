frappe.pages['salesperson-performance-dashboard'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Salesperson Performance Dashboard'),
		single_column: true
	});
	wrapper.page = page;
};

frappe.pages['salesperson-performance-dashboard'].on_page_show = function(wrapper) {
	const page = wrapper.page;

	wrapper.current_visit_id = (wrapper.current_visit_id || 0) + 1;
	const visit_id = wrapper.current_visit_id;

	if (wrapper.vue_app) {
		try {
			wrapper.vue_app.unmount();
		} catch (e) {
			console.error('Error unmounting Salesperson Performance Dashboard Vue app:', e);
		}
		wrapper.vue_app = null;
	}

	$(page.body).empty();

	const $loading = $('<div class="edge-preview-loading-placeholder p-6 text-center text-muted">' + __('Loading design system & salesperson performance dashboard assets...') + '</div>')
		.appendTo(page.body);

	const showLoadFailure = function(message, missing) {
		$loading.remove();
		const missingText = missing && missing.length ? '<div class="mt-2">' + __('Missing components: ') + missing.join(', ') + '</div>' : '';
		$('<div class="alert alert-danger p-6 text-center"><strong>' + __('EdgeSuite UI failed to load') + '</strong><div>' + message + '</div>' + missingText + '</div>')
			.appendTo(page.body);
	};

	const requiredComponents = [
		'EdgeAppShell',
		'EdgePageLayout',
		'EdgeFilterBar',
		'EdgeStatCard',
		'EdgeStatusBadge',
		'EdgeLoadingState',
		'EdgeEmptyState',
		'EdgeErrorState'
	];

	frappe.require('edgeui.bundle.js', () => {
		if (wrapper.current_visit_id !== visit_id) return;

		const edgeComponents = (window.EdgeUI && (window.EdgeUI.components || window.EdgeUI)) || {};
		const missing = requiredComponents.filter((name) => !edgeComponents[name]);
		if (!window.EdgeUI || missing.length) {
			showLoadFailure(__('Required EdgeSuite shell components could not be resolved.'), missing);
			return;
		}

		frappe.require('salesperson_performance.bundle.js', () => {
			if (wrapper.current_visit_id !== visit_id) return;

			$loading.remove();

			if (!window.SalespersonPerformanceDashboard || !window.mountSalespersonPerformanceDashboard) {
				showLoadFailure(__('Failed to load Salesperson Performance Dashboard bundle or mount helper.'), []);
				return;
			}

			try {
				const root = $('<div class="retailedge-dashboard-root"></div>').appendTo(page.body);
				wrapper.vue_app = window.mountSalespersonPerformanceDashboard(root[0]);
			} catch (e) {
				showLoadFailure(__('Error mounting Salesperson Performance Dashboard: ') + e.message, []);
			}
		});
	});
};
