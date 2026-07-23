function attachRetailEdgeReportEdgeUI(report, reportName, config) {
	const attach = () => {
		window.retailedgeReportEdgeUI?.register(reportName, config);
		window.retailedgeReportEdgeUI?.attach(report, reportName);
		renderPOSClosingVarianceEdgeUI(report);
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

function numericValue(value) {
	const number = Number.parseFloat(value || 0);
	return Number.isFinite(number) ? number : 0;
}

function getPOSVarianceFilterSummary(report) {
	const fromDate = report.get_filter_value("from_date");
	const toDate = report.get_filter_value("to_date");
	const parts = [];
	if (fromDate && toDate) {
		parts.push(__("{0} to {1}", [fromDate, toDate]));
	} else if (fromDate) {
		parts.push(__("From {0}", [fromDate]));
	} else if (toDate) {
		parts.push(__("Up to {0}", [toDate]));
	}
	[
		["company", __("Company")],
		["branch", __("Branch")],
		["pos_profile", __("POS Profile")],
		["cashier", __("Cashier")],
		["cost_center", __("Expense Cost Center")],
	].forEach(([fieldname, label]) => {
		const value = report.get_filter_value(fieldname);
		if (value) {
			parts.push(__("{0}: {1}", [label, value]));
		}
	});
	if (report.get_filter_value("include_cogs")) {
		parts.push(__("Include COGS / Stock Expense"));
	}
	return parts.slice(0, 6).join(" · ") || __("All permitted POS closing shifts");
}

function renderPOSClosingVarianceEdgeUI(report) {
	if (!window.retailedgeReportEdgeUI?.renderSummary) {
		return false;
	}
	const summaryRows = (Array.isArray(report.data) ? report.data : []).filter((row) => !row?.parent_row);
	const totalShortage = summaryRows.reduce((total, row) => total + numericValue(row.shortage), 0);
	const totalExpenses = summaryRows.reduce((total, row) => total + numericValue(row.expenses), 0);
	const totalRetailEdgeExpenses = summaryRows.reduce(
		(total, row) => total + numericValue(row.retail_cashier_expense_total),
		0,
	);
	const totalUnmatchedShortage = summaryRows.reduce(
		(total, row) => total + numericValue(row.unmatched_shortage),
		0,
	);
	const totalExcessExpenses = summaryRows.reduce(
		(total, row) => total + numericValue(row.excess_expenses),
		0,
	);
	const absoluteAdjustedVariance = summaryRows.reduce(
		(total, row) => total + Math.abs(numericValue(row.variance_after_retailedge_expenses)),
		0,
	);
	const missingBranchCount = summaryRows.filter((row) => !row.branch).length;
	const pendingExpenseCount = summaryRows.filter((row) => {
		const status = String(row.retail_cashier_expense_status_summary || "").toLowerCase();
		return status.includes("pending") || status.includes("clarification") || status.includes("draft");
	}).length;
	const recommendations = [];
	if (totalUnmatchedShortage > 0) {
		recommendations.push({
			title: __("Investigate unmatched cash shortages"),
			description: __("The current shifts contain shortages that are not explained by the included expense evidence."),
			severity: "danger",
		});
	}
	if (absoluteAdjustedVariance > 0) {
		recommendations.push({
			title: __("Validate closing cash after RetailEdge expenses"),
			description: __("Review the shifts contributing adjusted cash variance after RetailEdge cashier expenses are applied."),
			severity: "warning",
		});
	}
	if (totalExcessExpenses > 0) {
		recommendations.push({
			title: __("Review expenses exceeding recorded shortages"),
			description: __("Confirm that expense timing, shift assignment and supporting vouchers are correct where included expenses exceed the recorded shortage."),
			severity: "warning",
		});
	}
	if (pendingExpenseCount) {
		recommendations.push({
			title: __("Complete pending expense review"),
			description: __("Complete clarification or approval for cashier expenses affecting {0} closing shift(s).", [pendingExpenseCount]),
			severity: "warning",
		});
	}
	if (missingBranchCount) {
		recommendations.push({
			title: __("Resolve missing branch attribution"),
			description: __("Confirm the POS Profile and branch context for {0} closing shift(s) before management sign-off.", [missingBranchCount]),
			severity: "danger",
		});
	}

	let statusLabel = __("No closing-shift exceptions in current view");
	let statusTone = "success";
	if (totalUnmatchedShortage > 0 || missingBranchCount) {
		statusLabel = __("Closing-shift exceptions require attention");
		statusTone = "danger";
	} else if (absoluteAdjustedVariance > 0 || totalExcessExpenses > 0 || pendingExpenseCount) {
		statusLabel = __("Closing-shift review required");
		statusTone = "warning";
	} else if (!summaryRows.length) {
		statusLabel = __("No closing shifts in current view");
		statusTone = "neutral";
	}

	const cards = [
		{
			value: totalShortage,
			label: __("Total Shortage"),
			datatype: "Currency",
			indicator: totalShortage ? "Red" : "Green",
		},
		{
			value: totalExpenses,
			label: __("Total Expenses"),
			datatype: "Currency",
			indicator: "Blue",
		},
		{
			value: totalRetailEdgeExpenses,
			label: __("Total RetailEdge Cashier Expenses"),
			datatype: "Currency",
			indicator: totalRetailEdgeExpenses ? "Orange" : "Green",
		},
		{
			value: totalUnmatchedShortage,
			label: __("Unmatched Shortage"),
			datatype: "Currency",
			indicator: totalUnmatchedShortage ? "Red" : "Green",
		},
	];
	const metadata = {
		title: __("POS Closing Variance vs Expenses"),
		icon: "wallet",
		row_count: summaryRows.length,
		filter_summary: getPOSVarianceFilterSummary(report),
		visible_card_labels: cards.map((card) => card.label),
		status: {
			label: statusLabel,
			tone: statusTone,
		},
		recommendations,
		empty_state: {
			message: __("No POS closing shifts matched the selected filters."),
			suggestions: [
				__("Choose another date range, company, branch, POS Profile, cashier or cost center."),
				__("Confirm that POS closing shifts and cashier expenses contain the correct shift and branch context."),
			],
		},
		capabilities: {
			supports_export: true,
			supports_print: true,
			supports_share: true,
		},
	};
	return window.retailedgeReportEdgeUI.renderSummary(
		report,
		"POS Closing Variance vs Expenses",
		metadata,
		cards,
	);
}

frappe.query_reports["POS Closing Variance vs Expenses"] = {
	onload(report) {
		configureOperationalReportRefresh(report);
		forceOperationalPrimaryAction(report);
		attachRetailEdgeReportEdgeUI(report, "POS Closing Variance vs Expenses", {
			eyebrow: __("Cash Control Intelligence"),
			title: __("POS Closing Variance vs Expenses"),
			subtitle: __("Compare closing cash, shortages and expense evidence across permitted POS shifts without changing any operational document."),
			emptyDescription: __("Choose another operational context or confirm that POS closing shifts and cashier expenses carry the correct shift and branch information."),
		});
	},
	after_refresh(report) {
		forceOperationalPrimaryAction(report);
		renderPOSClosingVarianceEdgeUI(report);
	},
	tree: true,
	name_field: "row_id",
	parent_field: "parent_row",
	initial_depth: 1,
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "pos_profile",
			label: __("POS Profile"),
			fieldtype: "Link",
			options: "POS Profile",
		},
		{
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
			description: __("Filters report rows using RetailEdge branch resolution from the shift/profile context."),
		},
		{
			fieldname: "cashier",
			label: __("Cashier"),
			fieldtype: "Link",
			options: "User",
			description: __("Filters POS closing rows by the shift user / cashier."),
		},
		{
			fieldname: "cost_center",
			label: __("Expense Cost Center"),
			fieldtype: "Link",
			options: "Cost Center",
			description: __("Optional. If blank, the report uses the POS Profile cost center when available."),
		},
		{
			fieldname: "include_cogs",
			label: __("Include COGS / Stock Expense"),
			fieldtype: "Check",
			default: 0,
			description: __("Enable only if you want stock valuation or cost-of-goods entries included as expenses."),
		},
	],
};
