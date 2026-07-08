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

	const $loading = $('<div class="edge-preview-loading-placeholder p-6 text-center text-muted">' + __('Loading salesperson performance dashboard assets...') + '</div>')
		.appendTo(page.body);

	frappe.require('salesperson_performance.bundle.js', () => {
		if (wrapper.current_visit_id !== visit_id) return;

		$loading.remove();

		if (!window.SalespersonPerformanceDashboard || !window.mountSalespersonPerformanceDashboard) {
			$('<div class="alert alert-danger p-6 text-center">' + __('Failed to load Salesperson Performance Dashboard bundle or mount helper.') + '</div>')
				.appendTo(page.body);
			return;
		}

		try {
			const root = $('<div class="retailedge-dashboard-root"></div>').appendTo(page.body);
			wrapper.vue_app = window.mountSalespersonPerformanceDashboard(root[0]);
		} catch (e) {
			$('<div class="alert alert-danger p-6 text-center">' + __('Error mounting Salesperson Performance Dashboard: ') + e.message + '</div>')
				.appendTo(page.body);
		}
	});
};
