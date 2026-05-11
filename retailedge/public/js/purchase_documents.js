(function () {
	if (typeof frappe === "undefined" || !frappe.ui || !frappe.ui.form || !frappe.ui.form.on) {
		return;
	}

	window.retailedge = window.retailedge || {};

	const FIELD_MAP = {
		"Purchase Receipt": [
			"price_list_rate",
			"base_price_list_rate",
			"rate",
			"amount",
			"base_rate",
			"base_amount",
			"stock_uom_rate",
			"net_rate",
			"net_amount",
			"base_net_rate",
			"base_net_amount",
			"valuation_rate",
			"sales_incoming_rate",
			"rm_supp_cost",
			"landed_cost_voucher_amount",
			"amount_difference_with_purchase_invoice",
			"billed_amt",
		],
		"Purchase Invoice": [
			"price_list_rate",
			"base_price_list_rate",
			"rate",
			"amount",
			"base_rate",
			"base_amount",
			"stock_uom_rate",
			"net_rate",
			"net_amount",
			"base_net_rate",
			"base_net_amount",
			"valuation_rate",
			"sales_incoming_rate",
			"rm_supp_cost",
			"landed_cost_voucher_amount",
		],
	};
	const PARENT_TOTAL_FIELDS = [
		"base_total",
		"base_net_total",
		"total",
		"net_total",
		"base_total_taxes_and_charges",
		"total_taxes_and_charges",
		"base_grand_total",
		"grand_total",
		"rounding_adjustment",
		"base_rounded_total",
		"rounded_total",
		"in_words",
	];

	function shouldRun() {
		return Boolean(
			window.retailedge &&
				window.retailedge.costVisibility &&
				window.retailedge.costVisibility.shouldHide &&
				window.retailedge.costVisibility.shouldHide()
		);
	}

	async function loadRules() {
		if (
			!window.retailedge ||
			!window.retailedge.costVisibility ||
			!window.retailedge.costVisibility.loadRules
		) {
			return null;
		}

		return window.retailedge.costVisibility.loadRules();
	}

	function hideByFieldname(wrapper, fieldname) {
		if (!wrapper || typeof $ === "undefined") {
			return;
		}

		const $wrapper = wrapper.jquery ? wrapper : $(wrapper);
		[
			`.frappe-control[data-fieldname="${fieldname}"]`,
			`.form-group[data-fieldname="${fieldname}"]`,
			`.grid-static-col[data-fieldname="${fieldname}"]`,
			`.control-input[data-fieldname="${fieldname}"]`,
			`.fields_order[data-fieldname="${fieldname}"]`,
			`[data-fieldname="${fieldname}"]`,
		].forEach((selector) => {
			$wrapper.find(selector).each((_, node) => {
				const control = node.closest
					? node.closest(".frappe-control, .form-group, .grid-static-col, .control-input, .fields_order")
					: node;
				if (control) {
					control.style.display = "none";
				}
			});
		});
	}

	function getItemFields(doctype) {
		return FIELD_MAP[doctype] || [];
	}

	function hideParentTotals(frm) {
		PARENT_TOTAL_FIELDS.forEach((fieldname) => {
			try {
				if (frm.toggle_display) {
					frm.toggle_display(fieldname, false);
				}
			} catch (error) {
				// Ignore parent toggle errors.
			}

			try {
				frm.set_df_property(fieldname, "hidden", 1);
			} catch (error) {
				// Ignore parent property errors.
			}

			hideByFieldname(frm.wrapper, fieldname);
		});
	}

	function hideOpenRow(gridRow, doctype) {
		if (!gridRow) {
			return;
		}

		getItemFields(doctype).forEach((fieldname) => {
			try {
				if (gridRow.toggle_display) {
					gridRow.toggle_display(fieldname, false);
				}
			} catch (error) {
				// Ignore row toggle errors.
			}

			try {
				if (gridRow.grid_form && gridRow.grid_form.fields_dict && gridRow.grid_form.fields_dict[fieldname]) {
					gridRow.grid_form.fields_dict[fieldname].df.hidden = 1;
					gridRow.grid_form.fields_dict[fieldname].refresh();
				}
			} catch (error) {
				// Ignore row form field errors.
			}

			if (gridRow.wrapper) {
				hideByFieldname(gridRow.wrapper, fieldname);
			}

			if (gridRow.grid_form && gridRow.grid_form.wrapper) {
				hideByFieldname(gridRow.grid_form.wrapper, fieldname);
			}
		});
	}

	function hideGrid(frm) {
		const grid = frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
		if (!grid) {
			return;
		}

		getItemFields(frm.doctype).forEach((fieldname) => {
			try {
				grid.toggle_display(fieldname, false);
			} catch (error) {
				// Ignore grid toggle errors.
			}

			try {
				grid.update_docfield_property(fieldname, "hidden", 1);
			} catch (error) {
				// Ignore grid property errors.
			}

			hideByFieldname(grid.wrapper, fieldname);
		});

		try {
			(grid.grid_rows || []).forEach((gridRow) => {
				hideOpenRow(gridRow, frm.doctype);
			});
		} catch (error) {
			// Ignore row iteration errors.
		}
	}

	function bindGridRowEvents(frm) {
		const grid = frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
		if (!grid || !frm.wrapper || typeof $ === "undefined") {
			return;
		}

		const key = frm.doctype === "Purchase Invoice" ? "__retailedgeBoundPurchaseInvoice" : "__retailedgeBoundPurchaseReceipt";
		if (grid[key]) {
			return;
		}

		grid[key] = true;

		$(frm.wrapper).on(`grid-row-render.retailedge_${frm.doctype.toLowerCase().replace(/\s+/g, "_")}`, function (_event, gridRow) {
			if (!shouldRun()) {
				return;
			}

			hideOpenRow(gridRow, frm.doctype);
			setTimeout(function () {
				hideOpenRow(gridRow, frm.doctype);
			}, 0);
			setTimeout(function () {
				hideOpenRow(gridRow, frm.doctype);
			}, 150);
			setTimeout(function () {
				hideOpenRow(gridRow, frm.doctype);
			}, 500);
		});
	}

	async function applyPurchaseProtection(frm) {
		await loadRules();
		if (!shouldRun()) {
			return;
		}

		hideParentTotals(frm);
		hideGrid(frm);
		bindGridRowEvents(frm);

		setTimeout(function () {
			hideParentTotals(frm);
			hideGrid(frm);
		}, 0);
		setTimeout(function () {
			hideParentTotals(frm);
			hideGrid(frm);
		}, 150);
		setTimeout(function () {
			hideParentTotals(frm);
			hideGrid(frm);
		}, 500);
	}

	frappe.ui.form.on("Purchase Receipt", {
		refresh(frm) {
			applyPurchaseProtection(frm);
		},
		onload_post_render(frm) {
			applyPurchaseProtection(frm);
		},
		items_on_form_rendered(frm) {
			applyPurchaseProtection(frm);
		},
		items_add(frm) {
			applyPurchaseProtection(frm);
		},
	});

	frappe.ui.form.on("Purchase Invoice", {
		refresh(frm) {
			applyPurchaseProtection(frm);
		},
		onload_post_render(frm) {
			applyPurchaseProtection(frm);
		},
		items_on_form_rendered(frm) {
			applyPurchaseProtection(frm);
		},
		items_add(frm) {
			applyPurchaseProtection(frm);
		},
	});

	frappe.ui.form.on("Purchase Receipt Item", {
		form_render(frm) {
			const targetFrm = frm && frm.doctype === "Purchase Receipt" ? frm : cur_frm;
			if (targetFrm && targetFrm.doctype === "Purchase Receipt") {
				applyPurchaseProtection(targetFrm);
			}
		},
	});

	frappe.ui.form.on("Purchase Invoice Item", {
		form_render(frm) {
			const targetFrm = frm && frm.doctype === "Purchase Invoice" ? frm : cur_frm;
			if (targetFrm && targetFrm.doctype === "Purchase Invoice") {
				applyPurchaseProtection(targetFrm);
			}
		},
	});
})();
