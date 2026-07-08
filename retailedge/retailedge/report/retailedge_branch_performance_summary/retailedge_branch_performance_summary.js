function getPresetDates(preset) {
	return window.retailedge && window.retailedge.getPresetDates ? window.retailedge.getPresetDates(preset) : null;
}

function applyRetailEdgeSummaryCardDesign() {
	// Report summary cards are styled through native Frappe DOM selectors in CSS.
}

function scheduleRetailEdgeSummaryCardDesign() {
	// No-op: report summary card appearance is CSS-only.
}

function configureOperationalReportRefresh(report) {
	if (!report || report.__retailedgeAutoRefreshConfigured) {
		return;
	}
	report.__retailedgeAutoRefreshConfigured = true;
	report.ignore_prepared_report = true;
	report.prepared_report = false;
	report.prepared_report_name = null;
	report.prepared_report_document = null;
	report.__retailedgeAutoRefreshReady = true;
	(report.filters || []).forEach((filter) => {
		const originalOnChange = filter.on_change;
		filter.on_change = function (queryReport) {
			if (typeof originalOnChange === "function") {
				originalOnChange.call(this, queryReport || report);
			}
			if (!report.__retailedgeAutoRefreshReady) {
				return;
			}
			scheduleOperationalReportRefresh(queryReport || report);
		};
	});
}

function scheduleOperationalReportRefresh(report) {
	if (!report) {
		return;
	}
	if (report.__retailedgeRefreshTimer) {
		clearTimeout(report.__retailedgeRefreshTimer);
	}
	report.__retailedgeRefreshTimer = setTimeout(() => {
		report.refresh();
	}, 200);
}

function forceOperationalPrimaryAction(report) {
	if (!report || !report.page || typeof report.page.set_primary_action !== "function") {
		return;
	}
	report.page.set_primary_action(__("Refresh Report"), () => {
		report.refresh();
	});
}

frappe.query_reports["RetailEdge Branch Performance Summary"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
		},
		{
			fieldname: "pos_profile",
			label: __("POS Profile"),
			fieldtype: "Link",
			options: "POS Profile",
		},
		{
			fieldname: "cashier",
			label: __("Cashier"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "date_range_preset",
			label: __("Date Range Preset"),
			fieldtype: "Select",
			options: [
				"This Month",
				"Today",
				"Yesterday",
				"This Week",
				"This Quarter",
				"This Year",
				"Last Week",
				"Last Month",
				"Last Quarter",
				"Last Year",
				"Custom Period",
				"Full Branch History"
			].join("\n"),
			default: "This Month",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "payment_method",
			label: __("Payment Method"),
			fieldtype: "Select",
			options: "\nCash\nBank Transfer\nCard / POS\nMobile Money\nOther",
		},
		{
			fieldname: "only_pos_invoices",
			label: __("Only POS Invoices"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "include_unattributed",
			label: __("Include Unattributed"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "include_fallback_branch_resolution",
			label: __("Use Fallback Branch Resolution"),
			fieldtype: "Check",
			default: 0,
		},
	],
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
		window.retailedge.setupDateRangePresets(report);
		const originalRefresh = report.refresh.bind(report);
		report.refresh = function () {
			const fromDate = report.get_filter_value("from_date");
			const toDate = report.get_filter_value("to_date");
			if (fromDate && toDate && frappe.datetime.str_to_obj(fromDate) > frappe.datetime.str_to_obj(toDate)) {
				frappe.throw(__("From Date cannot be after To Date."));
			}
			if (fromDate && toDate) {
				const days = frappe.datetime.get_day_diff(toDate, fromDate) + 1;
				if (days > 60) {
					frappe.show_alert({
						message: __("Large date ranges may take longer to load."),
						indicator: "orange"
					});
				}
			}
			return originalRefresh();
		};

		scheduleRetailEdgeSummaryCardDesign(report);
	},

	after_refresh(report) {
		forceOperationalPrimaryAction(report);
		scheduleRetailEdgeSummaryCardDesign(report);
	},
};
