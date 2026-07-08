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

frappe.query_reports["RetailEdge Invoice Payment Audit"] = {
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
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
	},

	after_refresh(report) {
		forceOperationalPrimaryAction(report);
		scheduleRetailEdgeSummaryCardDesign(report);
	},

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
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
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
			fieldname: "audit_status",
			label: __("Audit Status"),
			fieldtype: "Select",
			options: [
				"",
				"Credit",
				"Partially Paid",
				"Fully Paid Pending Audit",
				"Payment Rows Missing",
				"Payment Account Mismatch",
				"Payment Amount Mismatch",
				"Split Payment",
				"Overpaid",
				"Underpaid",
				"Pending Verification",
				"Ready for Verification",
				"Verified in Daily Audit",
				"Variance Found",
				"Cancelled",
				"Unknown",
			].join("\n"),
		},
		{
			fieldname: "risk_level",
			label: __("Risk Level"),
			fieldtype: "Select",
			options: "\nLow\nMedium\nHigh",
		},
		{
			fieldname: "payment_category",
			label: __("Payment Category"),
			fieldtype: "Select",
			options: "\nCash\nBank Transfer\nCard / POS\nMobile Money\nCredit\nOther",
		},
		{
			fieldname: "only_issues",
			label: __("Only Issues"),
			fieldtype: "Check",
			default: 0,
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
				"Full History"
			].join("\n"),
			default: "This Month",
			on_change: function (queryReport) {
				const val = queryReport.get_filter_value("date_range_preset");
				if (val && val !== "Custom Period") {
					const dates = window.retailedge && window.retailedge.getPresetDates ? window.retailedge.getPresetDates(val) : null;
					if (dates) {
						queryReport.__programmatic_date_change = true;
						queryReport.set_filter_value("from_date", dates.from_date);
						queryReport.set_filter_value("to_date", dates.to_date);
						queryReport.__programmatic_date_change = false;
					}
				}
			}
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			on_change: function (queryReport) {
				if (!queryReport.__programmatic_date_change) {
					queryReport.set_filter_value("date_range_preset", "Custom Period");
				}
			}
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			on_change: function (queryReport) {
				if (!queryReport.__programmatic_date_change) {
					queryReport.set_filter_value("date_range_preset", "Custom Period");
				}
			}
		},
	],
};
