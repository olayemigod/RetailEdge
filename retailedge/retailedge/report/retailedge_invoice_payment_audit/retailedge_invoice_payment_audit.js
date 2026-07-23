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

frappe.query_reports["RetailEdge Invoice Payment Audit"] = {
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
		attachRetailEdgeReportEdgeUI(report, "RetailEdge Invoice Payment Audit", {
			eyebrow: __("Payment Control"),
			title: __("Invoice Payment Audit"),
			subtitle: __("Review invoice payment evidence, account alignment, audit status, and risk without changing invoice or ledger records."),
			emptyDescription: __("Choose another operational context or confirm that submitted invoices and payment evidence exist for the selected period."),
		});
	},

	after_refresh(report) {
		forceOperationalPrimaryAction(report);
		scheduleRetailEdgeSummaryCardDesign(report);
		window.retailedgeReportEdgeUI?.refresh(report, "RetailEdge Invoice Payment Audit");
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
