// salesperson_performance_dashboard.js
console.log("[BOOT] Salesperson Performance Dashboard controller evaluated");

try {
	frappe.pages["salesperson-performance-dashboard"].on_page_load = async function (wrapper) {
		console.log("[BOOT] Salesperson Performance Dashboard on_page_load");
		const bootLoading = $(
			'<div class="edge-boot-loading text-center text-muted" style="padding: 24px;">' +
				__("Loading EdgeSuite UI for Salesperson Performance Dashboard…") +
				"</div>",
		).appendTo(wrapper);
		wrapper._bootLoading = bootLoading;

		try {
			const page = frappe.ui.make_app_page({
				parent: wrapper,
				title: __("Salesperson Performance Dashboard"),
				single_column: true,
			});
			wrapper.page = page;

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

			await requireAsync("edgesuite_ui.bundle.js");
			await requireAsync("salesperson_performance.bundle.js");

			if (typeof window.mountSalespersonPerformanceDashboard !== "function") {
				throw new Error("Salesperson Performance Dashboard mount function is unavailable.");
			}

			bootLoading.remove();
			wrapper._bootLoading = null;
			const target = $('<div class="retailedge-dashboard-root"></div>').appendTo(page.body);
			wrapper.vue_app = window.mountSalespersonPerformanceDashboard(target[0]);
			console.log("[BOOT] Salesperson Performance Dashboard mounted");
		} catch (error) {
			console.error("[BOOT] Salesperson Performance Dashboard failed:", error);
			if (wrapper._bootLoading) {
				wrapper._bootLoading.remove();
				wrapper._bootLoading = null;
			}
			const errorBlock = document.createElement("div");
			errorBlock.className = "alert alert-danger p-6 text-center";
			const title = document.createElement("strong");
			title.textContent = __("Salesperson Performance Dashboard failed to load");
			const detail = document.createElement("div");
			detail.textContent = error?.message || String(error);
			errorBlock.appendChild(title);
			errorBlock.appendChild(detail);
			wrapper.appendChild(errorBlock);
		}
	};

	frappe.pages["salesperson-performance-dashboard"].on_page_show = function (wrapper) {
		const page = wrapper.page;
		if (!page) {
			console.log("[BOOT] Salesperson Performance Dashboard page shell is unavailable");
			return;
		}
		console.log("[BOOT] Salesperson Performance Dashboard page shown");
	};
} catch (error) {
	console.error("[BOOT] Fatal Salesperson Performance Dashboard controller error:", error);
}
