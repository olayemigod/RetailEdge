frappe.pages["business-control-center"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Business Control Centre"),
		single_column: true,
	});
	frappe.require("business_control_center.bundle.js").then(() => {
		window.retailedgeMountBusinessControlCenter?.(wrapper);
	});
};
