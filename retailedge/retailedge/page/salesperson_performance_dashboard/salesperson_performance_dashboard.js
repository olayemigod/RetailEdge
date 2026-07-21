// salesperson_performance_dashboard.js
console.log("[BOOT] Salesperson Performance Dashboard controller evaluated");

try {
	frappe.pages["salesperson-performance-dashboard"].on_page_load = async function (wrapper) {
		console.log("[BOOT] Salesperson Performance Dashboard on_page_load");
		try {
			const $bootLoading = $(
				'<div class="edge-boot-loading p-6 text-center text-muted" style="padding: 20px; font-size: 16px;">' +
					__("Loading Salesperson Performance Dashboard...") +
					"</div>"
			).appendTo(wrapper);

			const requireAsync = function (asset, options = {}) {
				const optional = Boolean(options.optional);
				const timeout = Number(options.timeout || 5000);

				return new Promise((resolve, reject) => {
					let completed = false;

					frappe.require(asset, () => {
						completed = true;
						console.log("[BOOT] Loaded:", asset);
						resolve(true);
					});

					setTimeout(() => {
						if (completed) return;
						if (optional) {
							console.info("[BOOT] Optional asset unavailable:", asset);
							resolve(false);
							return;
						}
						reject(new Error("Timed out loading " + asset));
					}, timeout);
				});
			};

			const page = frappe.ui.make_app_page({
				parent: wrapper,
				title: __("Salesperson Performance Dashboard"),
				single_column: true,
			});
			wrapper.page = page;
			wrapper._bootLoading = $bootLoading;

			// Shared EdgeUI enhances the page when present, but RetailEdge owns a
			// compatible local runtime so a standalone product installation remains usable.
			if (!window.EdgeUI?.createEdgeApp) {
				await requireAsync("edgeui.bundle.js", { optional: true, timeout: 750 });
			}

			await requireAsync("salesperson_performance.bundle.js");

			if (typeof window.mountSalespersonPerformanceDashboard !== "function") {
				throw new Error("Salesperson Performance Dashboard mount function is unavailable");
			}

			try {
				if (wrapper._bootLoading) {
					wrapper._bootLoading.remove();
					wrapper._bootLoading = null;
				}
				const root = $('<div class="retailedge-dashboard-root"></div>').appendTo(page.body);
				wrapper.vue_app = await window.mountSalespersonPerformanceDashboard(root[0]);
				console.log("[BOOT] Salesperson Performance Dashboard mounted");
			} catch (error) {
				console.error("Salesperson Performance Dashboard mount failed:", error);
				throw error;
			}
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
			detail.textContent = error.message || String(error);
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
