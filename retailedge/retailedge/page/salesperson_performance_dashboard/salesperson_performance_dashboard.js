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

	// Track visits defensively to ignore stale callbacks on navigate away
	wrapper.current_visit_id = (wrapper.current_visit_id || 0) + 1;
	const visit_id = wrapper.current_visit_id;

	// Cleanly unmount old vue instance
	if (wrapper.vue_app) {
		try {
			wrapper.vue_app.unmount();
		} catch (e) {
			console.error("Error unmounting Salesperson Performance Dashboard Vue app:", e);
		}
		wrapper.vue_app = null;
	}

	$(page.body).empty();

	// Show loading placeholder
	const $loading = $('<div class="edge-preview-loading-placeholder p-6 text-center text-muted">' + __('Loading design system & dashboard assets...') + '</div>')
		.appendTo(page.body);

	// 1. Lazy load CoreEdge EdgeUI first
	frappe.require('edgeui.bundle.js', () => {
		if (wrapper.current_visit_id !== visit_id) return;

		if (!window.EdgeUI) {
			$loading.remove();
			$('<div class="alert alert-danger p-6 text-center">' + __('Failed to load EdgeSuite UI shared bundle.') + '</div>')
				.appendTo(page.body);
			return;
		}

		// 2. Lazy load RetailEdge dashboard bundle second
		frappe.require('salesperson_performance.bundle.js', () => {
			if (wrapper.current_visit_id !== visit_id) return;

			$loading.remove();

			if (!window.SalespersonPerformanceDashboard) {
				$('<div class="alert alert-danger p-6 text-center">' + __('Failed to load Salesperson Performance Dashboard bundle.') + '</div>')
					.appendTo(page.body);
				return;
			}

			const { createEdgeApp } = window.EdgeUI;
			const DashboardComponent = window.SalespersonPerformanceDashboard;

			// Create mount container
			const root = $('<div class="retailedge-dashboard-root"></div>').appendTo(page.body);

			// Bootstrap Vue app using CoreEdge helper
			wrapper.vue_app = createEdgeApp(DashboardComponent, root[0]);
		});
	});
};
