(function () {
	if (typeof frappe === "undefined") {
		return;
	}

	window.retailedge = window.retailedge || {};

	const HIDDEN_LIST_FIELDS = {
		"Purchase Receipt": [
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
			"per_billed",
			"in_words",
		],
		"Purchase Invoice": [
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
			"outstanding_amount",
			"paid_amount",
		],
		"Purchase Order": [
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
			"per_received",
			"per_billed",
			"in_words",
		],
	};

	function shouldRun() {
		return Boolean(window.retailedge?.costVisibility?.shouldHide?.());
	}

	async function loadRules() {
		return window.retailedge?.costVisibility?.loadRules?.();
	}

	function fieldsFor(doctype) {
		return HIDDEN_LIST_FIELDS[doctype] || [];
	}

	function hideListDom(listview) {
		if (!listview || !listview.$result || typeof $ === "undefined") {
			return;
		}

		fieldsFor(listview.doctype).forEach((fieldname) => {
			try {
				listview.$result.find(`.list-row-col.${fieldname}`).hide();
			} catch (error) {
				// Ignore row DOM hide errors.
			}
		});
	}

	function filterListColumns(listview) {
		if (!listview || !Array.isArray(listview.columns)) {
			return;
		}

		const hidden = new Set(fieldsFor(listview.doctype));
		listview.columns = listview.columns.filter((column) => {
			return !(column?.type === "Field" && column?.df?.fieldname && hidden.has(column.df.fieldname));
		});
	}

	async function apply(listview) {
		await loadRules();
		if (!shouldRun()) {
			return;
		}

		filterListColumns(listview);
		hideListDom(listview);

		setTimeout(function () {
			filterListColumns(listview);
			hideListDom(listview);
		}, 0);
		setTimeout(function () {
			filterListColumns(listview);
			hideListDom(listview);
		}, 150);
	}

	["Purchase Receipt", "Purchase Invoice", "Purchase Order"].forEach((doctype) => {
		frappe.listview_settings[doctype] = Object.assign(frappe.listview_settings[doctype] || {}, {
			onload(listview) {
				apply(listview);
			},
			before_render() {
				const listview = cur_list;
				if (listview && listview.doctype === doctype) {
					filterListColumns(listview);
				}
			},
			refresh(listview) {
				apply(listview);
			},
		});
	});
})();
