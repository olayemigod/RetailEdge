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
	const ADVANCE_CONTEXT_METHOD = "retailedge.advanced_payments.get_sales_invoice_advance_context";
	const APPLY_ADVANCE_METHOD = "retailedge.payment_application.apply_customer_advance";

	function shouldRun() {
		return Boolean(window.retailedge?.costVisibility?.shouldHide?.());
	}

	async function loadRules() {
		return window.retailedge?.costVisibility?.loadRules?.();
	}

	function callMethod(method, args = {}) {
		return new Promise((resolve, reject) => {
			frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject });
		});
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

	function advanceLabel(row) {
		const amount = frappe.format(row.unallocated_amount || 0, { fieldtype: "Currency" });
		return `${row.name} · ${amount} available`;
	}

	function openAdvanceDialog(frm, context) {
		const advances = Array.isArray(context.eligible_advances) ? context.eligible_advances : [];
		if (!advances.length) {
			frappe.msgprint({
				title: __("Customer Advances"),
				message: __("No eligible unapplied customer advance is available for this invoice."),
				indicator: "blue",
			});
			return;
		}
		const byName = Object.fromEntries(advances.map((row) => [row.name, row]));
		const first = advances[0];
		const maxFor = (row) => Math.min(Number(context.outstanding_amount || 0), Number(row?.unallocated_amount || 0));
		const dialog = new frappe.ui.Dialog({
			title: __("Apply Customer Advance"),
			fields: [
				{ fieldtype: "Data", fieldname: "invoice", label: __("Sales Invoice"), default: frm.doc.name, read_only: 1 },
				{ fieldtype: "Data", fieldname: "customer", label: __("Customer"), default: context.customer || frm.doc.customer, read_only: 1 },
				{
					fieldtype: "Select",
					fieldname: "payment_entry",
					label: __("Customer Advance"),
					reqd: 1,
					options: advances.map((row) => ({ label: advanceLabel(row), value: row.name })),
					default: first.name,
					onchange() {
						const selected = byName[dialog.get_value("payment_entry")];
						dialog.set_value("allocated_amount", maxFor(selected));
					},
				},
				{
					fieldtype: "Currency",
					fieldname: "allocated_amount",
					label: __("Amount to Apply"),
					reqd: 1,
					default: maxFor(first),
					description: __("Apply all or part of the selected advance. ERPNext Payment Reconciliation remains the accounting authority."),
				},
			],
			primary_action_label: __("Apply Advance"),
			async primary_action(values) {
				const selected = byName[values.payment_entry];
				const amount = Number(values.allocated_amount || 0);
				const maximum = maxFor(selected);
				if (!selected || amount <= 0 || amount > maximum) {
					frappe.msgprint(__("Amount to Apply must be greater than zero and cannot exceed the invoice outstanding amount or selected advance balance."));
					return;
				}
				dialog.get_primary_btn().prop("disabled", true);
				try {
					await callMethod(APPLY_ADVANCE_METHOD, {
						sales_invoice: frm.doc.name,
						payment_entry: values.payment_entry,
						allocated_amount: amount,
					});
					dialog.hide();
					frappe.show_alert({ message: __("Customer advance applied through ERPNext Payment Reconciliation."), indicator: "green" });
					await frm.reload_doc();
				} catch (error) {
					dialog.get_primary_btn().prop("disabled", false);
				}
			},
		});
		dialog.show();
	}

	async function addAdvanceAction(frm) {
		if (
			frm.doctype !== "Sales Invoice"
			|| frm.doc.docstatus !== 1
			|| frm.doc.is_return
			|| Number(frm.doc.outstanding_amount || 0) <= 0
			|| !frm.doc.customer
		) return;
		try {
			const context = await callMethod(ADVANCE_CONTEXT_METHOD, { sales_invoice: frm.doc.name, limit: 50 });
			if (!context.currency_supported || !Array.isArray(context.eligible_advances) || !context.eligible_advances.length) return;
			frm.add_custom_button(__("Apply Customer Advance"), () => openAdvanceDialog(frm, context), __("Payments"));
		} catch (error) {
			// The RetailEdge action is optional; standard ERPNext Sales Invoice must remain usable.
		}
	}

	["Sales Invoice", "Delivery Note", "Sales Order", "Quotation"].forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			refresh(frm) {
				apply(frm);
				if (doctype === "Sales Invoice") addAdvanceAction(frm);
			},
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
