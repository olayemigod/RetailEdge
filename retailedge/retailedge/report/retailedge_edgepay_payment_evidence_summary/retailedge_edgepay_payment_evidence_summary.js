// Copyright (c) 2026, ProcessEdge Solutions and contributors
// For license information, please see license.txt

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

frappe.query_reports["RetailEdge EdgePay Payment Evidence Summary"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "from_date", label: __("Date From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("Date To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "review_status", label: __("Review Status"), fieldtype: "Select", options: "\nPending Review\nReviewed\nRejected\nException" },
		{ fieldname: "reconciliation_status", label: __("Reconciliation Status"), fieldtype: "Select", options: "\nNot Ready\nReady\nMatched\nReconciled\nBlocked\nException" },
		{ fieldname: "posting_status", label: __("Posting Status"), fieldtype: "Select", options: "\nNot Prepared\nReady\nDraft Created\nSubmitted\nBlocked\nFailed\nCancelled" },
		{ fieldname: "submission_status", label: __("Submission Status"), fieldtype: "Select", options: "\nNot Submitted\nSubmitted\nFailed\nBlocked" }
	],
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
	},
	after_refresh(report) {
		forceOperationalPrimaryAction(report);
	}
};
