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

frappe.query_reports["RetailEdge Daily Sales Audit Register"] = {
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
		attachRetailEdgeReportEdgeUI(report, "RetailEdge Daily Sales Audit Register", {
			eyebrow: __("Daily Cash Control"),
			title: __("Daily Sales Audit Register"),
			subtitle: __("Review cash sales, expected cash, closing counts, variance, clarification, and approval state across permitted branches and shifts."),
			emptyDescription: __("Choose another date range or operational context, or confirm that daily audits were created from the correct opening and closing shifts."),
		});
	},

	after_refresh(report) {
		forceOperationalPrimaryAction(report);
		window.retailedgeReportEdgeUI?.refresh(report, "RetailEdge Daily Sales Audit Register");
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
			fieldname: "audit_status",
			label: __("Audit Status"),
			fieldtype: "Select",
			options: "\nDraft\nReady for Review\nIn Review\nVariance Found\nApproved\nRejected\nCancelled",
		},
		{
			fieldname: "audit_result",
			label: __("Audit Result"),
			fieldtype: "Select",
			options: "\nNot Checked\nBalanced\nShortage\nOverage\nMixed Variance\nRequires Clarification",
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
