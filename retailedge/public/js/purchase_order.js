(function () {
	if (typeof frappe === "undefined" || !frappe.ui || !frappe.ui.form || !frappe.ui.form.on) {
		return;
	}

	window.retailedge = window.retailedge || {};
	const ITEM_FIELDS = [
		"price_list_rate",
		"base_price_list_rate",
		"last_purchase_rate",
		"rate",
		"amount",
		"base_rate",
		"base_amount",
		"net_rate",
		"net_amount",
		"base_net_rate",
		"base_net_amount",
		"stock_uom_rate",
	];
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

	function hideOpenRow(gridRow) {
		if (!gridRow) return;
		ITEM_FIELDS.forEach((fieldname) => {
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

	function hideParentTotals(frm) {
		PARENT_TOTAL_FIELDS.forEach((fieldname) => {
			try { frm.toggle_display?.(fieldname, false); } catch (error) {}
			try { frm.set_df_property(fieldname, "hidden", 1); } catch (error) {}
			hideByFieldname(frm.wrapper, fieldname);
		});
	}

	function hideGrid(frm) {
		const grid = frm.fields_dict?.items?.grid;
		if (!grid) return;
		ITEM_FIELDS.forEach((fieldname) => {
			try { grid.toggle_display?.(fieldname, false); } catch (error) {}
			try { grid.update_docfield_property?.(fieldname, "hidden", 1); } catch (error) {}
			hideByFieldname(grid.wrapper, fieldname);
		});
		try { (grid.grid_rows || []).forEach(hideOpenRow); } catch (error) {}
	}

	function bindGridRowEvents(frm) {
		const grid = frm.fields_dict?.items?.grid;
		if (!grid || !frm.wrapper || typeof $ === "undefined" || grid.__retailedgeBoundPurchaseOrder) return;
		grid.__retailedgeBoundPurchaseOrder = true;
		$(frm.wrapper).on("grid-row-render.retailedge_purchase_order", function (_event, gridRow) {
			if (!shouldRun()) return;
			hideOpenRow(gridRow);
			setTimeout(() => hideOpenRow(gridRow), 0);
			setTimeout(() => hideOpenRow(gridRow), 150);
			setTimeout(() => hideOpenRow(gridRow), 500);
		});
	}

	async function apply(frm) {
		await loadRules();
		if (!shouldRun()) return;
		hideParentTotals(frm);
		hideGrid(frm);
		bindGridRowEvents(frm);
		setTimeout(() => { hideParentTotals(frm); hideGrid(frm); }, 0);
		setTimeout(() => { hideParentTotals(frm); hideGrid(frm); }, 150);
		setTimeout(() => { hideParentTotals(frm); hideGrid(frm); }, 500);
	}

	frappe.ui.form.on("Purchase Order", {
		refresh(frm) { apply(frm); },
		onload_post_render(frm) { apply(frm); },
		items_on_form_rendered(frm) { apply(frm); },
		items_add(frm) { apply(frm); },
	});
	frappe.ui.form.on("Purchase Order Item", {
		form_render(frm) {
			const targetFrm = frm?.doctype === "Purchase Order" ? frm : cur_frm;
			if (targetFrm?.doctype === "Purchase Order") apply(targetFrm);
		},
	});
})();
