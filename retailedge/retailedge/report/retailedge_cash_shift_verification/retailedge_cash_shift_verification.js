function applyRetailEdgeSummaryCardDesign() {
	// EdgeSuite UI renders the business summary while the native report table remains unchanged.
}

function scheduleRetailEdgeSummaryCardDesign() {
	// Retained for compatibility with existing operational report refresh helpers.
}

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

frappe.query_reports["RetailEdge Cash Shift Verification"] = {
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
		attachRetailEdgeReportEdgeUI(report, "RetailEdge Cash Shift Verification", {
			eyebrow: __("Cash Control"),
			title: __("Cash Shift Verification"),
			subtitle: __("Compare expected and counted cash, identify missing shift evidence, and review invoice-verification sync without changing POS or ledger records."),
			emptyDescription: __("Choose another operational context or confirm that daily audits carry valid opening and closing shift references."),
		});
	},

	after_refresh(report) {
		forceOperationalPrimaryAction(report);
		scheduleRetailEdgeSummaryCardDesign(report);
		window.retailedgeReportEdgeUI?.refresh(report, "RetailEdge Cash Shift Verification");
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
			fieldname: "cash_status",
			label: __("Cash Status"),
			fieldtype: "Select",
			options: "\nBalanced\nShortage\nOverage\nNeeds Review\nMissing Closing Shift\nMissing Opening Shift",
		},
		{
			fieldname: "review_status",
			label: __("Review Status"),
			fieldtype: "Select",
			options: "\nDraft\nReady for Review\nIn Review\nBalanced\nVariance Found\nClarification Required\nApproved\nRejected\nCancelled\nReopened",
		},
		{
			fieldname: "only_unsynced",
			label: __("Only Unsynced"),
			fieldtype: "Check",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
};
