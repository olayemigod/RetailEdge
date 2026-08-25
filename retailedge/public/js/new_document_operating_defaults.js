(function () {
	if (typeof frappe === "undefined" || !frappe.ui?.form?.on) return;

	const SUPPORTED_DOCTYPES = [
		"Sales Order",
		"Delivery Note",
		"Sales Invoice",
		"POS Invoice",
		"Purchase Order",
		"Purchase Receipt",
		"Purchase Invoice",
		"Material Request",
		"Stock Entry",
	];

	const SAFE_SCALAR_FIELDS = [
		"company",
		"branch",
		"retailedge_branch",
		"retailedge_branch_source",
		"set_warehouse",
		"target_warehouse",
		"from_warehouse",
		"source_warehouse",
		"to_warehouse",
		"cost_center",
		"payment_account",
		"pos_profile",
		"retailedge_branch_resolution_note",
	];

	function isEmpty(value) {
		return value === undefined || value === null || value === "";
	}

	function isEligibleNewForm(frm) {
		return Boolean(
			frm &&
			frm.is_new?.() &&
			Number(frm.doc?.docstatus || 0) === 0 &&
			SUPPORTED_DOCTYPES.includes(frm.doctype)
		);
	}

	function getRequestState(frm) {
		frm.__retailedgeOperatingDefaults = frm.__retailedgeOperatingDefaults || {
			loading: false,
			loaded: false,
		};
		return frm.__retailedgeOperatingDefaults;
	}

	function buildPayload(frm) {
		const payload = frappe.model?.get_docinfo ? { ...frm.doc } : JSON.parse(JSON.stringify(frm.doc || {}));
		delete payload.__islocal;
		delete payload.__unsaved;
		return payload;
	}

	function seedFieldValue(response, fieldname) {
		const seed = response?.seed || {};
		if (!(seed.applied || []).includes(fieldname)) return undefined;
		if (fieldname === "company") return seed.company || "";
		if (fieldname === "branch" || fieldname === "retailedge_branch") return seed.branch || "";
		if (fieldname === "retailedge_branch_source") return "Operating Context";
		return undefined;
	}

	async function applyScalarDefaults(frm, response) {
		const changes = response?.changes || {};
		for (const fieldname of SAFE_SCALAR_FIELDS) {
			if (!frm.fields_dict?.[fieldname]) continue;
			if (!isEmpty(frm.doc?.[fieldname])) continue;

			let proposed = seedFieldValue(response, fieldname);
			if (isEmpty(proposed) && Object.prototype.hasOwnProperty.call(changes, fieldname)) {
				proposed = changes[fieldname];
			}
			if (isEmpty(proposed) || Array.isArray(proposed) || typeof proposed === "object") continue;
			if (!isEmpty(frm.doc?.[fieldname])) continue;
			await frm.set_value(fieldname, proposed);
		}
	}

	async function applyOperatingDefaults(frm) {
		if (!isEligibleNewForm(frm)) return;
		const state = getRequestState(frm);
		if (state.loading || state.loaded) return;
		state.loading = true;
		try {
			const response = await frappe.call({
				method: "retailedge.new_document_defaults.get_new_document_operating_defaults",
				args: {
					doctype: frm.doctype,
					values: buildPayload(frm),
				},
			});
			if (!isEligibleNewForm(frm)) return;
			await applyScalarDefaults(frm, response.message || {});
			state.loaded = true;
		} catch (error) {
			// Defaults are a convenience layer. Native ERPNext form loading must continue
			// even when RetailEdge cannot safely resolve an operating default.
			console.warn("RetailEdge operating defaults could not be applied", error);
		} finally {
			state.loading = false;
		}
	}

	SUPPORTED_DOCTYPES.forEach((doctype) => {
		frappe.ui.form.on(doctype, {
			onload(frm) {
				applyOperatingDefaults(frm);
			},
		});
	});

	window.retailedge = window.retailedge || {};
	window.retailedge.applyNewDocumentOperatingDefaults = applyOperatingDefaults;
})();
