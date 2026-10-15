(function () {
	if (typeof frappe === "undefined") {
		return;
	}

	window.retailedge = window.retailedge || {};

	const BRANCH_FIELD_BY_DOCTYPE = {
		"Sales Invoice": "retailedge_branch",
		"POS Invoice": "retailedge_branch",
		"Sales Order": "retailedge_branch",
		"Delivery Note": "retailedge_branch",
		Quotation: "retailedge_branch",
		"Payment Entry": "retailedge_branch",
		"Payment Request": "retailedge_branch",
		"Bank Transaction": "retailedge_branch",
		"Material Request": "retailedge_branch",
		"Stock Entry": "retailedge_branch",
		"Stock Reconciliation": "retailedge_branch",
		"Pick List": "retailedge_branch",
		"Packing Slip": "retailedge_branch",
		"Purchase Order": "retailedge_branch",
		"Purchase Receipt": "retailedge_branch",
		"Purchase Invoice": "retailedge_branch",
		"Supplier Quotation": "retailedge_branch",
		"Request for Quotation": "retailedge_branch",
		"POS Opening Shift": "retailedge_branch",
		"POS Closing Shift": "retailedge_branch",
		"POS Profile": "retailedge_branch",
		"RetailEdge Cashier Expense": "branch",
		"RetailEdge Business Expense": "branch",
	};

	function clean(value) {
		return String(value || "").trim();
	}

	function activeBranch() {
		return clean(
			frappe.boot?.retailedge_ui_identity?.active_branch ||
				frappe.boot?.edgesuite_ui_identity?.retailedge?.active_branch
		);
	}

	function branchField(listview) {
		const configured = BRANCH_FIELD_BY_DOCTYPE[listview?.doctype];
		if (!configured) return "";
		const fields = listview?.meta?.fields || [];
		return fields.some((field) => field?.fieldname === configured) ? configured : "";
	}

	function isBranchFilter(filter, doctype, fieldname) {
		if (!Array.isArray(filter)) return false;
		const filterDoctype = clean(filter[0]);
		return (!filterDoctype || filterDoctype === doctype) && filter[1] === fieldname;
	}

	async function apply(listview) {
		const branch = activeBranch();
		const fieldname = branchField(listview);
		if (!branch || !fieldname || !listview?.filter_area) {
			return;
		}

		const currentFilters = listview.filter_area.get?.() || listview.filters || [];
		const preservedFilters = currentFilters.filter(
			(filter) => !isBranchFilter(filter, listview.doctype, fieldname)
		);
		const nextFilters = [
			...preservedFilters,
			[listview.doctype, fieldname, "=", branch],
		];

		const currentBranchFilters = currentFilters.filter((filter) =>
			isBranchFilter(filter, listview.doctype, fieldname)
		);
		if (
			currentBranchFilters.length === 1 &&
			currentBranchFilters[0][2] === "=" &&
			clean(currentBranchFilters[0][3]) === branch
		) {
			return;
		}

		await listview.filter_area.clear(false);
		await listview.filter_area.set(nextFilters);
	}

	function install(listview) {
		if (!listview || listview.__retailedgeWorkingBranchScopeInstalled) {
			return;
		}
		listview.__retailedgeWorkingBranchScopeInstalled = true;

		const originalBeforeRefresh = listview.before_refresh?.bind(listview);
		listview.before_refresh = function () {
			const nativeRefresh = originalBeforeRefresh ? originalBeforeRefresh() : Promise.resolve();
			return Promise.resolve(nativeRefresh).then(() => apply(listview));
		};
	}

	function register(doctype) {
		const existing = frappe.listview_settings[doctype] || {};
		const existingOnload = existing.onload;
		frappe.listview_settings[doctype] = Object.assign({}, existing, {
			onload(listview) {
				if (typeof existingOnload === "function") {
					existingOnload.call(this, listview);
				}
				install(listview);
			},
		});
	}

	window.retailedge.workingBranchDocumentScope = {
		activeBranch,
		apply,
		install,
	};

	Object.keys(BRANCH_FIELD_BY_DOCTYPE).forEach(register);
})();
