(function () {
	if (typeof frappe === "undefined" || !frappe.ui || !frappe.ui.form || !frappe.ui.form.on) {
		return;
	}

	window.retailedge = window.retailedge || {};
	const FIELD_MAP = {
		"Sales Invoice": ["incoming_rate", "stock_uom_rate"],
		"Delivery Note": ["incoming_rate", "stock_uom_rate"],
		"Sales Order": ["valuation_rate", "gross_profit", "stock_uom_rate"],
		"Quotation": ["valuation_rate", "gross_profit", "stock_uom_rate"],
	};

	function shouldRun() {
		return Boolean(window.retailedge?.costVisibility?.shouldHide?.());
	}

	async function loadRules() {
		return window.retailedge?.costVisibility?.loadRules?.();
	}

	function hideByFieldname(wrapper, fieldname) {
		if (!wrapper || typeof $ === "undefined") return;
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
				if (control) control.style.display = "none";
			});
		});
	}

	function fieldsFor(doctype) {
		return FIELD_MAP[doctype] || [];
	}

	function hideOpenRow(gridRow, doctype) {
		if (!gridRow) return;
		fieldsFor(doctype).forEach((fieldname) => {
			try { gridRow.toggle_display?.(fieldname, false); } catch (error) {}
			try {
				if (gridRow.grid_form?.fields_dict?.[fieldname]) {
					gridRow.grid_form.fields_dict[fieldname].df.hidden = 1;
					gridRow.grid_form.fields_dict[fieldname].refresh();
				}
			} catch (error) {}
			if (gridRow.wrapper) hideByFieldname(gridRow.wrapper, fieldname);
			if (gridRow.grid_form?.wrapper) hideByFieldname(gridRow.grid_form.wrapper, fieldname);
		});
	}

	function hideGrid(frm) {
		const grid = frm.fields_dict?.items?.grid;
		if (!grid) return;
		fieldsFor(frm.doctype).forEach((fieldname) => {
			try { grid.toggle_display?.(fieldname, false); } catch (error) {}
			try { grid.update_docfield_property?.(fieldname, "hidden", 1); } catch (error) {}
			hideByFieldname(grid.wrapper, fieldname);
		});
		try { (grid.grid_rows || []).forEach((row) => hideOpenRow(row, frm.doctype)); } catch (error) {}
	}

	function bindGridRowEvents(frm) {
		const grid = frm.fields_dict?.items?.grid;
		if (!grid || !frm.wrapper || typeof $ === "undefined") return;
		const key = `__retailedgeBound_${frm.doctype.replace(/\s+/g, "_")}`;
		if (grid[key]) return;
		grid[key] = true;
		$(frm.wrapper).on(`grid-row-render.retailedge_${frm.doctype.toLowerCase().replace(/\s+/g, "_")}`, function (_event, gridRow) {
			if (!shouldRun()) return;
			hideOpenRow(gridRow, frm.doctype);
			setTimeout(() => hideOpenRow(gridRow, frm.doctype), 0);
			setTimeout(() => hideOpenRow(gridRow, frm.doctype), 150);
			setTimeout(() => hideOpenRow(gridRow, frm.doctype), 500);
		});
	}

	async function apply(frm) {
		await loadRules();
		if (!shouldRun()) return;
		hideGrid(frm);
		bindGridRowEvents(frm);
		setTimeout(() => hideGrid(frm), 0);
		setTimeout(() => hideGrid(frm), 150);
		setTimeout(() => hideGrid(frm), 500);
	}

	["Sales Invoice", "Delivery Note", "Sales Order", "Quotation"].forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) { apply(frm); },
			onload_post_render(frm) { apply(frm); },
			items_on_form_rendered(frm) { apply(frm); },
			items_add(frm) { apply(frm); },
		});
	});

	[
		"Sales Invoice Item",
		"Delivery Note Item",
		"Sales Order Item",
		"Quotation Item",
	].forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			form_render(frm) {
				const targetFrm = cur_frm;
				if (targetFrm && FIELD_MAP[targetFrm.doctype]) apply(targetFrm);
			},
		});
	});
})();
