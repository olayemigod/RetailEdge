(function () {
	if (typeof frappe === "undefined") {
		return;
	}

	window.retailedge = window.retailedge || {};
	frappe.listview_settings = frappe.listview_settings || {};

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

	function activeIdentity() {
		return (
			frappe.boot?.edgesuite_ui_identity?.retailedge ||
			frappe.boot?.retailedge_ui_identity ||
			{}
		);
	}

	function activeBranch() {
		return clean(activeIdentity().active_branch);
	}

	function activeCompany() {
		return clean(activeIdentity().active_company);
	}

	function companyWide() {
		return Boolean(activeIdentity().company_wide);
	}

	function metaHasField(listview, fieldname) {
		const fields = listview?.meta?.fields || [];
		return fields.some((field) => field?.fieldname === fieldname);
	}

	function branchField(listview) {
		const configured = BRANCH_FIELD_BY_DOCTYPE[listview?.doctype];
		return configured && metaHasField(listview, configured) ? configured : "";
	}

	function companyField(listview) {
		return metaHasField(listview, "company") ? "company" : "";
	}

	function isFieldFilter(filter, doctype, fieldname) {
		if (!fieldname || !Array.isArray(filter)) return false;
		const filterDoctype = clean(filter[0]);
		return (!filterDoctype || filterDoctype === doctype) && filter[1] === fieldname;
	}

	function exactFilter(filters, doctype, fieldname, value) {
		const matches = filters.filter((filter) => isFieldFilter(filter, doctype, fieldname));
		return (
			matches.length === 1 &&
			matches[0][2] === "=" &&
			clean(matches[0][3]) === clean(value)
		);
	}

	async function apply(listview) {
		const branch = activeBranch();
		const company = activeCompany();
		const isCompanyWide = companyWide();
		const branchFieldname = branchField(listview);
		const companyFieldname = companyField(listview);
		if (!listview?.filter_area || !branchFieldname) {
			return;
		}
		if (!isCompanyWide && !branch) {
			return;
		}
		// Company-wide view is allowed only where the list can retain the active
		// Company as a hard boundary. Native permissions remain authoritative too.
		if (isCompanyWide && (!company || !companyFieldname)) {
			return;
		}

		const currentFilters = listview.filter_area.get?.() || listview.filters || [];
		const branchFilters = currentFilters.filter((filter) =>
			isFieldFilter(filter, listview.doctype, branchFieldname)
		);
		const companyFilters = companyFieldname
			? currentFilters.filter((filter) => isFieldFilter(filter, listview.doctype, companyFieldname))
			: [];
		const branchMatches = isCompanyWide
			? branchFilters.length === 0
			: exactFilter(currentFilters, listview.doctype, branchFieldname, branch);
		const companyMatches = !companyFieldname || !company
			? companyFilters.length === 0
			: exactFilter(currentFilters, listview.doctype, companyFieldname, company);
		if (branchMatches && companyMatches) {
			return;
		}

		const preservedFilters = currentFilters.filter(
			(filter) =>
				!isFieldFilter(filter, listview.doctype, branchFieldname) &&
				!isFieldFilter(filter, listview.doctype, companyFieldname)
		);
		const nextFilters = [...preservedFilters];
		if (companyFieldname && company) {
			nextFilters.push([listview.doctype, companyFieldname, "=", company]);
		}
		if (!isCompanyWide) {
			nextFilters.push([listview.doctype, branchFieldname, "=", branch]);
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
		activeCompany,
		companyWide,
		apply,
		install,
	};

	Object.keys(BRANCH_FIELD_BY_DOCTYPE).forEach(register);
})();
