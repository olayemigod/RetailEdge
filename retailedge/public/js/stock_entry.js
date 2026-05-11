(function () {
	if (typeof frappe === "undefined" || !frappe.ui || !frappe.ui.form || !frappe.ui.form.on) {
		return;
	}

	window.retailedge = window.retailedge || {};
	const STOCK_ENTRY_PARENT_FIELDS = [
		"total_incoming_value",
		"total_outgoing_value",
		"value_difference",
	];
	const STOCK_ENTRY_ITEM_FIELDS = [
		"basic_rate",
		"basic_amount",
		"amount",
		"additional_cost",
		"landed_cost_voucher_amount",
		"valuation_rate",
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

	function hideParentFields(frm) {
		STOCK_ENTRY_PARENT_FIELDS.forEach((fieldname) => {
			try {
				frm.toggle_display(fieldname, false);
			} catch (error) {
				// Ignore toggle errors.
			}

			try {
				frm.set_df_property(fieldname, "hidden", 1);
			} catch (error) {
				// Ignore property errors.
			}

			hideByFieldname(frm.wrapper, fieldname);
		});
	}

	function hideGridColumns(frm) {
		const grid = frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
		if (!grid) {
			return;
		}

		STOCK_ENTRY_ITEM_FIELDS.forEach((fieldname) => {
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
				hideOpenRow(gridRow);
			});
		} catch (error) {
			// Ignore row iteration errors.
		}
	}

	function hideOpenRow(gridRow) {
		if (!gridRow) {
			return;
		}

		STOCK_ENTRY_ITEM_FIELDS.forEach((fieldname) => {
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
				// Ignore grid form field errors.
			}

			if (gridRow.wrapper) {
				hideByFieldname(gridRow.wrapper, fieldname);
			}

			if (gridRow.grid_form && gridRow.grid_form.wrapper) {
				hideByFieldname(gridRow.grid_form.wrapper, fieldname);
			}
		});
	}

	function bindGridRowEvents(frm) {
		const grid = frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
		if (!grid || !frm.wrapper || typeof $ === "undefined") {
			return;
		}

		if (grid.__retailedgeBound) {
			return;
		}

		grid.__retailedgeBound = true;

		$(frm.wrapper).on("grid-row-render.retailedge_stock_entry", function (_event, gridRow) {
			if (!shouldRun()) {
				return;
			}

			hideOpenRow(gridRow);
			setTimeout(function () {
				hideOpenRow(gridRow);
			}, 0);
			setTimeout(function () {
				hideOpenRow(gridRow);
			}, 150);
			setTimeout(function () {
				hideOpenRow(gridRow);
			}, 500);
		});
	}

	async function applyStockEntryProtection(frm) {
		await loadRules();
		if (!shouldRun()) {
			return;
		}

		hideParentFields(frm);
		hideGridColumns(frm);
		bindGridRowEvents(frm);

		setTimeout(function () {
			hideParentFields(frm);
			hideGridColumns(frm);
		}, 0);
		setTimeout(function () {
			hideParentFields(frm);
			hideGridColumns(frm);
		}, 150);
		setTimeout(function () {
			hideParentFields(frm);
			hideGridColumns(frm);
		}, 500);
	}

	frappe.ui.form.on("Stock Entry", {
		refresh(frm) {
			applyStockEntryProtection(frm);
		},
		onload_post_render(frm) {
			applyStockEntryProtection(frm);
		},
		items_on_form_rendered(frm) {
			applyStockEntryProtection(frm);
		},
		items_add(frm) {
			applyStockEntryProtection(frm);
		},
	});

	frappe.ui.form.on("Stock Entry Detail", {
		form_render(frm) {
			const targetFrm = frm && frm.doctype === "Stock Entry" ? frm : cur_frm;
			if (targetFrm && targetFrm.doctype === "Stock Entry") {
				applyStockEntryProtection(targetFrm);
			}
		},
	});
})();
