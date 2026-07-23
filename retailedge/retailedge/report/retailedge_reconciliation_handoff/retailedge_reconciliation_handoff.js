function attachRetailEdgeReportEdgeUI(report, reportName, config) {
	const attach = () => {
		window.retailedgeReportEdgeUI?.register(reportName, config);
		window.retailedgeReportEdgeUI?.attach(report, reportName);
	};
	if (window.retailedgeReportEdgeUI) {
		attach();
		return;
	}
	frappe.require("/assets/retailedge/js/retailedge_report_edgeui.js", attach);
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

frappe.query_reports["RetailEdge Reconciliation Handoff"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
		{ fieldname: "bank_account", label: __("Bank Account"), fieldtype: "Link", options: "Bank Account" },
		{ fieldname: "from_date", label: __("Date From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("Date To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "handoff_status", label: __("Handoff Status"), fieldtype: "Select", options: "\nReady for ERPNext Reconciliation\nNeeds Review Before Reconciliation\nNot Eligible for Reconciliation\nAlready Reconciled\nException / Manual Investigation Required" },
		{ fieldname: "match_type", label: __("Match Type"), fieldtype: "Data" },
		{ fieldname: "match_status", label: __("Match Status"), fieldtype: "Data" },
		{ fieldname: "candidate_doctype", label: __("Candidate Type"), fieldtype: "Select", options: "\nPayment Entry\nSales Invoice" },
		{ fieldname: "include_already_reconciled", label: __("Include Already Reconciled"), fieldtype: "Check", default: 0 },
		{ fieldname: "include_exceptions", label: __("Include Exceptions"), fieldtype: "Check", default: 1 },
		{ fieldname: "include_rejected_cancelled", label: __("Include Rejected / Cancelled"), fieldtype: "Check", default: 0 }
	],
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
		attachRetailEdgeReportEdgeUI(report, "RetailEdge Reconciliation Handoff", {
			eyebrow: __("Reconciliation Oversight"),
			title: __("Reconciliation Handoff"),
			subtitle: __("Review ready items, blockers, candidate evidence and exceptions before processing anything in ERPNext reconciliation."),
			emptyDescription: __("Choose another context or confirm that approved bank match reviews have complete candidate, account, amount and reconciliation evidence."),
		});
	},
	after_refresh(report) {
		forceOperationalPrimaryAction(report);
		window.retailedgeReportEdgeUI?.refresh(report, "RetailEdge Reconciliation Handoff");
	}
};
