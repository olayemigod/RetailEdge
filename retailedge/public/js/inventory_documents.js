(function () {
	if (typeof frappe === "undefined" || !frappe.ui || !frappe.ui.form || !frappe.ui.form.on) {
		return;
	}

	window.retailedge = window.retailedge || {};
	const FIELD_MAP = {
		"Item": ["valuation_rate", "standard_rate", "last_purchase_rate"],
		"Stock Reconciliation": [
			"total_amount",
			"difference_amount",
			"valuation_rate",
			"amount",
			"current_valuation_rate",
			"current_amount",
		],
		"Stock Ledger Entry": ["incoming_rate", "valuation_rate", "stock_value", "stock_value_difference"],
		"Bin": ["valuation_rate", "stock_value"],
		"Serial No": ["purchase_rate"],
	};
	const CHILD_FIELD_MAP = {
		"Stock Reconciliation": ["valuation_rate", "amount", "current_valuation_rate", "current_amount"],
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

	function hideParent(frm) {
		(FIELD_MAP[frm.doctype] || []).forEach((fieldname) => {
			try { frm.toggle_display?.(fieldname, false); } catch (error) {}
			try { frm.set_df_property(fieldname, "hidden", 1); } catch (error) {}
			hideByFieldname(frm.wrapper, fieldname);
		});
	}

	function hideGrid(frm) {
		const grid = frm.fields_dict?.items?.grid;
		if (!grid) return;
		(CHILD_FIELD_MAP[frm.doctype] || []).forEach((fieldname) => {
			try { grid.toggle_display?.(fieldname, false); } catch (error) {}
			try { grid.update_docfield_property?.(fieldname, "hidden", 1); } catch (error) {}
			hideByFieldname(grid.wrapper, fieldname);
		});
		try {
			(grid.grid_rows || []).forEach((gridRow) => {
				(CHILD_FIELD_MAP[frm.doctype] || []).forEach((fieldname) => {
					try { gridRow.toggle_display?.(fieldname, false); } catch (error) {}
					if (gridRow.wrapper) hideByFieldname(gridRow.wrapper, fieldname);
					if (gridRow.grid_form?.wrapper) hideByFieldname(gridRow.grid_form.wrapper, fieldname);
				});
			});
		} catch (error) {}
	}

	async function apply(frm) {
		await loadRules();
		if (!shouldRun()) return;
		hideParent(frm);
		hideGrid(frm);
		setTimeout(() => { hideParent(frm); hideGrid(frm); }, 0);
		setTimeout(() => { hideParent(frm); hideGrid(frm); }, 150);
	}

	["Item", "Stock Reconciliation", "Stock Ledger Entry", "Bin", "Serial No"].forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) { apply(frm); },
			onload_post_render(frm) { apply(frm); },
			items_on_form_rendered(frm) { apply(frm); },
			items_add(frm) { apply(frm); },
		});
	});

	frappe.ui.form.on("Stock Reconciliation Item", {
		form_render(frm) {
			const targetFrm = cur_frm;
			if (targetFrm?.doctype === "Stock Reconciliation") apply(targetFrm);
		},
	});
})();
