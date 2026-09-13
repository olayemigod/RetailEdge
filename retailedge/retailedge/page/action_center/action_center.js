frappe.pages["action-center"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Action Centre"),
		single_column: true,
	});
	page.main.empty();
	const root = document.createElement("div");
	root.className = "retailedge-action-center-root";
	page.main.get(0).appendChild(root);
	frappe.require("action_center.bundle.js", () => {
		if (typeof window.retailedgeMountActionCenter === "function") {
			window.retailedgeMountActionCenter(root);
		}
	});
};
