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

frappe.query_reports["RetailEdge Unmatched Bank Payment Events"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
		{ fieldname: "from_date", label: __("Date From"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
		{ fieldname: "to_date", label: __("Date To"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "payment_event_type", label: __("Payment Event Type"), fieldtype: "Select", options: "All\nPayment Entry\nInvoice Payment Row\nPOS Payment Row", default: "All" },
		{ fieldname: "mode_of_payment", label: __("Mode of Payment"), fieldtype: "Link", options: "Mode of Payment" },
		{ fieldname: "payment_account", label: __("Payment Account"), fieldtype: "Link", options: "Account" },
		{ fieldname: "include_candidate_preview", label: __("Include Candidate Preview"), fieldtype: "Check", default: 0 },
		{ fieldname: "include_already_matched", label: __("Include Already Matched"), fieldtype: "Check", default: 0 },
		{ fieldname: "include_cash", label: __("Include Cash"), fieldtype: "Check", default: 0, read_only: 1 }
	],
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
		attachRetailEdgeReportEdgeUI(report, "RetailEdge Unmatched Bank Payment Events", {
			eyebrow: __("Reconciliation Oversight"),
			title: __("Unmatched Bank Payment Events"),
			subtitle: __("Review payment entries and invoice or POS payment rows that do not yet have reliable Bank Transaction evidence."),
			emptyDescription: __("Choose another context or confirm that source payment documents contain correct references, dates, amounts and account information."),
		});
	},
	after_refresh(report) {
		forceOperationalPrimaryAction(report);
		window.retailedgeReportEdgeUI?.refresh(report, "RetailEdge Unmatched Bank Payment Events");
	}
};
