(function () {
	if (typeof frappe === "undefined" || !frappe.ui || !frappe.ui.form || !frappe.ui.form.on) {
		return;
	}

	window.retailedge = window.retailedge || {};
	const MATERIAL_REQUEST_ITEM_FIELDS = [
		"rate",
		"price_list_rate",
		"amount",
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

	function hideOpenRow(gridRow) {
		if (!gridRow) {
			return;
		}

		MATERIAL_REQUEST_ITEM_FIELDS.forEach((fieldname) => {
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

		MATERIAL_REQUEST_ITEM_FIELDS.forEach((fieldname) => {
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

	function bindGridRowEvents(frm) {
		const grid = frm.fields_dict && frm.fields_dict.items && frm.fields_dict.items.grid;
		if (!grid || !frm.wrapper || typeof $ === "undefined") {
			return;
		}

		if (grid.__retailedgeBoundMaterialRequest) {
			return;
		}

		grid.__retailedgeBoundMaterialRequest = true;

		$(frm.wrapper).on("grid-row-render.retailedge_material_request", function (_event, gridRow) {
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

	async function applyMaterialRequestProtection(frm) {
		await loadRules();
		if (!shouldRun()) {
			return;
		}

		hideGrid(frm);
		bindGridRowEvents(frm);

		setTimeout(function () {
			hideGrid(frm);
		}, 0);
		setTimeout(function () {
			hideGrid(frm);
		}, 150);
		setTimeout(function () {
			hideGrid(frm);
		}, 500);
	}

	frappe.ui.form.on("Material Request", {
		refresh(frm) {
			applyMaterialRequestProtection(frm);
		},
		onload_post_render(frm) {
			applyMaterialRequestProtection(frm);
		},
		items_on_form_rendered(frm) {
			applyMaterialRequestProtection(frm);
		},
		items_add(frm) {
			applyMaterialRequestProtection(frm);
		},
	});

	frappe.ui.form.on("Material Request Item", {
		form_render(frm) {
			const targetFrm = frm && frm.doctype === "Material Request" ? frm : cur_frm;
			if (targetFrm && targetFrm.doctype === "Material Request") {
				applyMaterialRequestProtection(targetFrm);
			}
		},
	});
})();
