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

frappe.query_reports["RetailEdge Unmatched Bank Transactions"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
		{ fieldname: "bank_account", label: __("Bank Account"), fieldtype: "Link", options: "Bank Account" },
		{ fieldname: "from_date", label: __("Date From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("Date To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "direction", label: __("Direction"), fieldtype: "Select", options: "All\nInflow\nOutflow", default: "All" },
		{ fieldname: "amount_from", label: __("Amount From"), fieldtype: "Currency" },
		{ fieldname: "amount_to", label: __("Amount To"), fieldtype: "Currency" },
		{ fieldname: "match_status", label: __("Review Status"), fieldtype: "Data" },
		{ fieldname: "account_resolution_status", label: __("Account Resolution Status"), fieldtype: "Select", options: "\nResolved\nUnresolved" },
		{ fieldname: "include_candidate_preview", label: __("Include Candidate Preview"), fieldtype: "Check", default: 0 },
		{ fieldname: "include_already_reviewed", label: __("Include Already Reviewed"), fieldtype: "Check", default: 0 },
		{ fieldname: "include_rejected", label: __("Include Rejected"), fieldtype: "Check", default: 0 },
		{ fieldname: "include_reconciled", label: __("Include Reconciled"), fieldtype: "Check", default: 0 }
	],
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
	},
	after_refresh(report) {
		forceOperationalPrimaryAction(report);
	}
};
