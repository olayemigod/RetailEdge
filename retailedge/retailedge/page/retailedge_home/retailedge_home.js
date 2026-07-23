frappe.pages["retailedge-home"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("RetailEdge Home"),
		single_column: true,
	});
	wrapper.page = page;

	const loading = $(
		'<div class="edge-boot-loading text-center text-muted" style="padding: 24px;">' +
			__("Loading RetailEdge Home…") +
			"</div>",
	).appendTo(page.body);

	try {
		await new Promise((resolve, reject) => {
			let completed = false;
			frappe.require("retailedge_home.bundle.js", () => {
				completed = true;
				resolve();
			});
			window.setTimeout(() => {
				if (!completed) reject(new Error("Timed out loading RetailEdge Home assets."));
			}, 8000);
		});

		if (typeof window.mountRetailEdgeHome !== "function") {
			throw new Error("RetailEdge Home mount function is unavailable.");
		}

		loading.remove();
		const target = $('<div class="retailedge-home-root"></div>').appendTo(page.body);
		wrapper.retailedge_home_app = window.mountRetailEdgeHome(target[0]);
	} catch (error) {
		loading.remove();
		const message = error?.message || String(error);
		$(
			'<div class="alert alert-danger" style="margin: 20px;"><strong>' +
				__("RetailEdge Home failed to load") +
				"</strong><div></div></div>",
		)
			.find("div")
			.text(message)
			.end()
			.appendTo(page.body);
	}
};
