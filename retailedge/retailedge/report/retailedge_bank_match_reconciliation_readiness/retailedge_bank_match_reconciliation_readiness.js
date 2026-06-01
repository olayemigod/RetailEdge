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

frappe.query_reports["RetailEdge Bank Match Reconciliation Readiness"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
		{ fieldname: "bank_account", label: __("Bank Account"), fieldtype: "Link", options: "Bank Account" },
		{ fieldname: "from_date", label: __("Date From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("Date To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "review_status", label: __("Review Status"), fieldtype: "Data" },
		{ fieldname: "match_confidence", label: __("Match Confidence"), fieldtype: "Select", options: "\nStrong Match\nPossible Match\nWeak Match\nNo Match" },
		{ fieldname: "reconciliation_readiness_status", label: __("Reconciliation Readiness Status"), fieldtype: "Select", options: "\nReady for Reconciliation\nNot Ready\nNeeds Review\nException\nAlready Reconciled" },
		{ fieldname: "include_reconciled", label: __("Include Reconciled"), fieldtype: "Check", default: 0 },
		{ fieldname: "include_rejected_cancelled", label: __("Include Rejected / Cancelled"), fieldtype: "Check", default: 0 }
	],
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
	},
	after_refresh(report) {
		forceOperationalPrimaryAction(report);
	}
};
