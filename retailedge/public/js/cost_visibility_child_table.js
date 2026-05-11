(function () {
	if (typeof frappe === "undefined" || !frappe.ui || !frappe.ui.form || !frappe.ui.form.on) {
		return;
	}

	window.retailedge = window.retailedge || {};
	const COST_VISIBILITY_CHILD_DOCTYPES = [
		"Material Request Item",
		"Purchase Invoice Item",
		"Purchase Order Item",
		"Purchase Receipt Item",
		"Quotation Item",
		"Sales Invoice Item",
		"Sales Order Item",
		"Delivery Note Item",
		"Stock Reconciliation Item",
		"Packed Item",
		"Item Default",
	];

	function getTargetFrm(frm) {
		if (frm && frm.doctype && frm.doctype !== "Stock Entry") {
			return cur_frm || frm;
		}

		return cur_frm || frm;
	}

	async function applyCostVisibilityFromChild(frm) {
		const targetFrm = getTargetFrm(frm);
		if (
			!targetFrm ||
			!window.retailedge ||
			!window.retailedge.costVisibility ||
			!window.retailedge.costVisibility.apply
		) {
			return;
		}

		await window.retailedge.costVisibility.apply(targetFrm);

		setTimeout(function () {
			window.retailedge.costVisibility.apply(targetFrm);
		}, 0);
		setTimeout(function () {
			window.retailedge.costVisibility.apply(targetFrm);
		}, 150);
	}

	COST_VISIBILITY_CHILD_DOCTYPES.forEach(function (doctype) {
		frappe.ui.form.on(doctype, {
			form_render(frm) {
				applyCostVisibilityFromChild(frm);
			},
		});
	});
})();
