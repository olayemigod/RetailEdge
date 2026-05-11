(function () {
	if (typeof window === "undefined") {
		return;
	}

	window.retailedge = window.retailedge || {};

	const REPORT_HIDDEN_FIELDS = {
		"Stock Ledger": new Set([
			"incoming_rate",
			"valuation_rate",
			"in_out_rate",
			"stock_value",
			"stock_value_difference",
		]),
	};

	function shouldHideCostFields() {
		try {
			if (frappe.boot?.retailedge?.cost_visibility) {
				return Boolean(frappe.boot.retailedge.cost_visibility.hide_cost_price);
			}
		} catch (error) {
			// Ignore boot info errors.
		}

		try {
			const raw = sessionStorage.getItem("retailedge.cost_visibility_rules.v4");
			if (raw) {
				const parsed = JSON.parse(raw);
				return Boolean(parsed && parsed.hide_cost_price);
			}
		} catch (error) {
			// Ignore session storage errors.
		}

		return false;
	}

	function getHiddenFields(reportName) {
		return REPORT_HIDDEN_FIELDS[reportName] || null;
	}

	function patchReportSettings(queryReport) {
		if (!queryReport || !queryReport.report_settings || queryReport.report_settings.__retailedgePatched) {
			return;
		}

		const hiddenFields = getHiddenFields(queryReport.report_name);
		if (!hiddenFields) {
			return;
		}

		const settings = queryReport.report_settings;
		const originalAfterDatatableRender = settings.after_datatable_render;
		const originalGetDatatableOptions = settings.get_datatable_options;

		settings.get_datatable_options = function (options) {
			let nextOptions = options;
			if (originalGetDatatableOptions) {
				nextOptions = originalGetDatatableOptions.call(this, options) || options;
			}

			try {
				if (Array.isArray(nextOptions.columns)) {
					nextOptions.columns = nextOptions.columns.filter((column) => {
						return !hiddenFields.has(column?.fieldname || column?.id);
					});
				}
			} catch (error) {
				// Ignore datatable options patch errors.
			}

			return nextOptions;
		};

		settings.after_datatable_render = function (datatable) {
			hideRenderedColumns(queryReport, datatable);
			if (originalAfterDatatableRender) {
				originalAfterDatatableRender.call(this, datatable);
			}
		};

		settings.__retailedgePatched = true;
	}

	function hideRenderedColumns(queryReport, datatable) {
		if (!queryReport || !shouldHideCostFields()) {
			return;
		}

		const hiddenFields = getHiddenFields(queryReport.report_name);
		if (!hiddenFields) {
			return;
		}

		try {
			if (Array.isArray(queryReport.columns)) {
				queryReport.columns = queryReport.columns.map((column) => {
					if (column && hiddenFields.has(column.fieldname || column.id)) {
						return Object.assign({}, column, { hidden: 1 });
					}
					return column;
				});
			}
		} catch (error) {
			// Ignore column patch errors.
		}

		try {
			if (datatable?.options?.columns) {
				datatable.options.columns = datatable.options.columns.filter((column) => {
					return !hiddenFields.has(column?.fieldname || column?.id);
				});
			}
		} catch (error) {
			// Ignore datatable option filtering errors.
		}

		try {
			if (datatable?.datamanager?.columns) {
				datatable.datamanager.columns = datatable.datamanager.columns.filter((column) => {
					return !hiddenFields.has(column?.fieldname || column?.id);
				});
			}
		} catch (error) {
			// Ignore datamanager filtering errors.
		}

		try {
			if (queryReport.$report) {
				hiddenFields.forEach((fieldname) => {
					queryReport.$report.find(`[data-fieldname="${fieldname}"]`).hide();
					queryReport.$report.find(`.${fieldname}`).hide();
				});
			}
		} catch (error) {
			// Ignore DOM hide errors.
		}
	}

	function patchQueryReportPrototype() {
		if (
			typeof frappe === "undefined" ||
			!frappe.views ||
			!frappe.views.QueryReport ||
			frappe.views.QueryReport.prototype.__retailedgePatched
		) {
			return Boolean(frappe?.views?.QueryReport?.prototype?.__retailedgePatched);
		}

		const QueryReport = frappe.views.QueryReport;
		const originalGetReportSettings = QueryReport.prototype.get_report_settings;
		const originalPrepareReportData = QueryReport.prototype.prepare_report_data;
		const originalRenderDatatable = QueryReport.prototype.render_datatable;

		QueryReport.prototype.get_report_settings = function () {
			return originalGetReportSettings.call(this).then(() => {
				patchReportSettings(this);
			});
		};

		QueryReport.prototype.prepare_report_data = function (data) {
			const result = originalPrepareReportData.call(this, data);
			hideRenderedColumns(this, this.datatable);
			return result;
		};

		QueryReport.prototype.render_datatable = function () {
			patchReportSettings(this);
			hideRenderedColumns(this, this.datatable);
			const result = originalRenderDatatable.call(this);
			hideRenderedColumns(this, this.datatable);
			setTimeout(() => hideRenderedColumns(this, this.datatable), 0);
			setTimeout(() => hideRenderedColumns(this, this.datatable), 150);
			setTimeout(() => hideRenderedColumns(this, this.datatable), 500);
			return result;
		};

		QueryReport.prototype.__retailedgePatched = true;
		return true;
	}

	function registerQueryReportPatch(attempt) {
		if (patchQueryReportPrototype()) {
			return;
		}

		if ((attempt || 0) >= 20) {
			return;
		}

		setTimeout(function () {
			registerQueryReportPatch((attempt || 0) + 1);
		}, 500);
	}

	registerQueryReportPatch(0);
})();
