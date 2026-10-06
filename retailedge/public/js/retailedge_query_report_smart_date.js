(() => {
	"use strict";

	if (typeof window === "undefined") return;
	window.retailedge = window.retailedge || {};

	const BINDING_KEY = "__retailedgeSmartDateBinding";
	const APP_KEY = "__retailedgeSmartDateApp";
	const HOST_KEY = "__retailedgeSmartDateHost";

	function getFieldname(filter) {
		return filter && (filter.fieldname || filter.df?.fieldname);
	}

	function findFilter(report, fieldname) {
		if (!fieldname) return null;
		if (typeof report?.get_filter === "function") {
			const filter = report.get_filter(fieldname, false);
			if (filter) return filter;
		}
		return (report?.filters || []).find((filter) => getFieldname(filter) === fieldname) || null;
	}

	function filterValue(report, filter, fieldname) {
		if (typeof report?.get_filter_value === "function") {
			return report.get_filter_value(fieldname, false) || "";
		}
		return filter?.get_value?.() || "";
	}

	function wrapperElement(filter) {
		const wrapper = filter?.$wrapper || filter?.wrapper;
		if (!wrapper) return null;
		if (wrapper.jquery && typeof wrapper.get === "function") return wrapper.get(0);
		return wrapper;
	}

	function hideFilterControl(filter) {
		if (filter?.$wrapper?.hide) {
			filter.$wrapper.hide();
			return;
		}
		const wrapper = wrapperElement(filter);
		if (wrapper?.style) wrapper.style.display = "none";
	}

	async function setFilterControlValue(filter, value) {
		if (!filter?.set_value) return;
		const originalOnChange = filter.on_change;
		filter.on_change = () => {};
		try {
			await Promise.resolve(filter.set_value(value));
		} finally {
			filter.on_change = originalOnChange;
		}
	}

	function initialSmartDate(fromDate, toDate) {
		if (!fromDate || !toDate) return {};
		return {
			expression: "custom",
			from_date: fromDate,
			to_date: toDate,
			label: fromDate === toDate ? fromDate : `${fromDate} – ${toDate}`,
		};
	}

	function mountPointBefore(filter) {
		const wrapper = wrapperElement(filter);
		if (!wrapper?.parentNode) return null;
		const host = document.createElement("div");
		host.className = "frappe-control retailedge-query-report-smart-date";
		host.style.minWidth = "220px";
		host.style.maxWidth = "100%";
		host.style.flex = "1 1 260px";
		wrapper.parentNode.insertBefore(host, wrapper);
		return host;
	}

	window.retailedge.setupDateRangePresets = function (
		report,
		presetField = "date_range_preset",
		fromField = "from_date",
		toField = "to_date"
	) {
		if (!report) return false;

		if (presetField && typeof presetField === "object") {
			const options = presetField;
			presetField = options.presetField || "date_range_preset";
			fromField = options.fromField || "from_date";
			toField = options.toField || "to_date";
		}

		const presetFilter = findFilter(report, presetField);
		const fromFilter = findFilter(report, fromField);
		const toFilter = findFilter(report, toField);
		if (!fromFilter || !toFilter) return false;

		hideFilterControl(presetFilter);
		hideFilterControl(fromFilter);
		hideFilterControl(toFilter);

		if (report[APP_KEY] && report[HOST_KEY]) return true;
		if (report[BINDING_KEY]) return true;

		const runtime = window.EdgeSuiteUI;
		const SmartDateRange = runtime?.getComponent?.("EdgeSmartDateRange") || runtime?.components?.EdgeSmartDateRange;
		const { createApp, defineComponent, h } = runtime?.Vue || {};
		if (!SmartDateRange || !createApp || !defineComponent || !h) {
			window.setTimeout(() => window.retailedge.setupDateRangePresets(report, {
				presetField,
				fromField,
				toField,
			}), 100);
			return false;
		}

		const host = mountPointBefore(presetFilter || fromFilter);
		if (!host) return false;
		report[BINDING_KEY] = true;

		const currentFrom = filterValue(report, fromFilter, fromField);
		const currentTo = filterValue(report, toFilter, toField);
		const initialValue = initialSmartDate(currentFrom, currentTo);

		const setExactPeriod = async (fromDate, toDate) => {
			const queryReport = report;
			queryReport._no_refresh = true;
			try {
				if (presetFilter) await setFilterControlValue(presetFilter, "Custom Period");
				await setFilterControlValue(fromFilter, fromDate || "");
				await setFilterControlValue(toFilter, toDate || "");
			} finally {
				queryReport._no_refresh = false;
			}
			if (typeof queryReport.refresh === "function") queryReport.refresh();
		};

		const Root = defineComponent({
			name: "RetailEdgeQueryReportSmartDate",
			data() {
				return { model: { ...initialValue } };
			},
			methods: {
				async onModelUpdate(value) {
					this.model = value && typeof value === "object" ? { ...value } : {};
					if (value?.from_date && value?.to_date) return;
					await setExactPeriod(value?.from_date || "", value?.to_date || "");
				},
				async onResolved(value) {
					if (!value?.from_date || !value?.to_date) {
						await this.onModelUpdate(value);
						return;
					}
					this.model = { ...value };
					await setExactPeriod(value.from_date, value.to_date);
				},
			},
			render() {
				return h(SmartDateRange, {
					modelValue: this.model,
					"onUpdate:modelValue": this.onModelUpdate,
					onResolved: this.onResolved,
					label: "Period",
					showPresets: false,
					presets: [],
				});
			},
		});

		try {
			const app = createApp(Root);
			app.mount(host);
			report[APP_KEY] = app;
			report[HOST_KEY] = host;
			return true;
		} catch (error) {
			report[BINDING_KEY] = false;
			host.remove();
			console.warn("RetailEdge Query Report smart-date mount failed", error);
			return false;
		}
	};

	// The shared EdgeSuite component owns fuzzy-date interpretation. Keep the
	// historical name unavailable so no report can accidentally revive the
	// RetailEdge-local preset parser while backend preset compatibility remains.
	window.retailedge.getPresetDates = undefined;
})();
