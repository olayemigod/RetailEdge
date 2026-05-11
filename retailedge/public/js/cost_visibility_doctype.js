(function () {
	if (typeof frappe === "undefined" || !frappe.ui || !frappe.ui.form || !frappe.ui.form.on) {
		return;
	}

	window.retailedge = window.retailedge || {};
	const COST_VISIBILITY_DOCTYPES = [
		"Item",
		"Material Request",
		"Purchase Invoice",
		"Purchase Order",
		"Purchase Receipt",
		"Quotation",
		"Sales Invoice",
		"Sales Order",
		"Delivery Note",
		"Stock Reconciliation",
		"Stock Ledger Entry",
		"Bin",
		"Serial No",
		"Item Price",
		"Supplier Quotation",
	];

	async function applyCostVisibility(frm) {
		if (
			!window.retailedge ||
			!window.retailedge.costVisibility ||
			!window.retailedge.costVisibility.apply
		) {
			return;
		}

		await window.retailedge.costVisibility.apply(frm);

		setTimeout(function () {
			window.retailedge.costVisibility.apply(frm);
		}, 0);
		setTimeout(function () {
			window.retailedge.costVisibility.apply(frm);
		}, 150);
		setTimeout(function () {
			window.retailedge.costVisibility.apply(frm);
		}, 500);
	}

	COST_VISIBILITY_DOCTYPES.forEach(function (doctype) {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				applyCostVisibility(frm);
			},
			onload_post_render(frm) {
				applyCostVisibility(frm);
			},
		});
	});
})();
