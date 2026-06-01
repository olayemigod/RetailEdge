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

frappe.query_reports["RetailEdge Unmatched Bank Payment Events"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
		{ fieldname: "from_date", label: __("Date From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("Date To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "payment_event_type", label: __("Payment Event Type"), fieldtype: "Select", options: "All\nPayment Entry\nInvoice Payment Row\nPOS Payment Row", default: "All" },
		{ fieldname: "mode_of_payment", label: __("Mode of Payment"), fieldtype: "Data" },
		{ fieldname: "payment_account", label: __("Payment Account"), fieldtype: "Data" },
		{ fieldname: "include_already_matched", label: __("Include Already Matched"), fieldtype: "Check", default: 0 },
		{ fieldname: "include_cash", label: __("Include Cash"), fieldtype: "Check", default: 0, read_only: 1 }
	],
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
	},
	after_refresh(report) {
		forceOperationalPrimaryAction(report);
	}
};
