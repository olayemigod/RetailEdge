function getPresetDates(preset) {
	let today = frappe.datetime.str_to_obj(frappe.datetime.get_today());
	let from_date, to_date;

	switch (preset) {
		case "Today":
			from_date = today;
			to_date = today;
			break;
		case "Yesterday":
			let yesterday = new Date(today);
			yesterday.setDate(yesterday.getDate() - 1);
			from_date = yesterday;
			to_date = yesterday;
			break;
		case "This Week":
			let day = today.getDay();
			let diff = today.getDate() - day + (day === 0 ? -6 : 1);
			from_date = new Date(today.setDate(diff));
			to_date = frappe.datetime.str_to_obj(frappe.datetime.get_today());
			break;
		case "This Month":
			from_date = frappe.datetime.str_to_obj(frappe.datetime.month_start());
			to_date = frappe.datetime.str_to_obj(frappe.datetime.get_today());
			break;
		case "This Quarter":
			let currentQuarterMonth = Math.floor(today.getMonth() / 3) * 3;
			from_date = new Date(today.getFullYear(), currentQuarterMonth, 1);
			to_date = frappe.datetime.str_to_obj(frappe.datetime.get_today());
			break;
		case "This Year":
			from_date = new Date(today.getFullYear(), 0, 1);
			to_date = frappe.datetime.str_to_obj(frappe.datetime.get_today());
			break;
		case "Last Week":
			let lastWeekStart = new Date(today);
			let day2 = lastWeekStart.getDay();
			let diff2 = lastWeekStart.getDate() - day2 + (day2 === 0 ? -6 : 1) - 7;
			from_date = new Date(lastWeekStart.setDate(diff2));
			to_date = new Date(from_date);
			to_date.setDate(to_date.getDate() + 6);
			break;
		case "Last Month":
			let firstOfThisMonth = new Date(today.getFullYear(), today.getMonth(), 1);
			let lastOfLastMonth = new Date(firstOfThisMonth);
			lastOfLastMonth.setDate(lastOfLastMonth.getDate() - 1);
			from_date = new Date(lastOfLastMonth.getFullYear(), lastOfLastMonth.getMonth(), 1);
			to_date = lastOfLastMonth;
			break;
		case "Last Quarter":
			let currentQuarterStartMonth = Math.floor(today.getMonth() / 3) * 3;
			let firstOfThisQuarter = new Date(today.getFullYear(), currentQuarterStartMonth, 1);
			to_date = new Date(firstOfThisQuarter);
			to_date.setDate(to_date.getDate() - 1);
			let lastQuarterStartMonth = Math.floor(to_date.getMonth() / 3) * 3;
			from_date = new Date(to_date.getFullYear(), lastQuarterStartMonth, 1);
			break;
		case "Last Year":
			from_date = new Date(today.getFullYear() - 1, 0, 1);
			to_date = new Date(today.getFullYear() - 1, 11, 31);
			break;
		case "Full Branch History":
			from_date = new Date(2000, 0, 1);
			to_date = frappe.datetime.str_to_obj(frappe.datetime.get_today());
			break;
		default:
			return null;
	}

	return {
		from_date: frappe.datetime.obj_to_str(from_date),
		to_date: frappe.datetime.obj_to_str(to_date)
	};
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
			on_change: function (queryReport) {
				const val = queryReport.get_filter_value("date_range_preset");
				if (val && val !== "Custom Period") {
					const dates = getPresetDates(val);
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
			reqd: 1,
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
			reqd: 1,
			on_change: function (queryReport) {
				if (!queryReport.__programmatic_date_change) {
					queryReport.set_filter_value("date_range_preset", "Custom Period");
				}
			}
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
