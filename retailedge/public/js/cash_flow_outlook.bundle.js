import CashFlowOutlookReport from "./cash_flow_outlook/CashFlowOutlookReport.vue";

const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "cash-flow-outlook";
const PAGE_METHOD = "retailedge.cash_flow_outlook.get_cash_flow_outlook";
const GOVERNED_EXPORT_METHOD = "retailedge.reporting_actions.get_report_export_data";

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: reject,
		});
	});
}

function registerCashFlowOutlookProvider(target = window) {
	const reports = target?.EdgeSuiteReports || target?.EdgeSuiteUI?.reports;
	if (!reports?.createBoundedPaginatedReportProvider || !reports?.registerProvider) return null;
	if (reports.hasProvider?.(REPORT_PRODUCT, REPORT_KEY)) {
		return reports.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || null;
	}
	const provider = reports.createBoundedPaginatedReportProvider({
		key: REPORT_KEY,
		defaultPageLength: 25,
		maxPageLength: 25,
		maxDatasetRows: 14,
		loadPage: async ({ filters = {}, start = 0, page_length = 25 } = {}) => {
			const result = await callMethod(PAGE_METHOD, { filters: { ...filters } });
			const rows = Array.isArray(result.rows) ? result.rows : [];
			const safeStart = Math.max(0, Number(start || 0));
			const safeLength = Math.max(1, Math.min(25, Number(page_length || 25)));
			return {
				...result,
				rows: rows.slice(safeStart, safeStart + safeLength),
				start: safeStart,
				page_length: safeLength,
				total: rows.length,
				metadata: {
					...(result.metadata || {}),
					scan: result.scan || {},
					company_currency: result.company_currency || "",
					as_of_date: result.as_of_date || "",
					horizon_weeks: result.horizon_weeks || 13,
					beyond_horizon: result.beyond_horizon || {},
				},
			};
		},
		exportReport: async ({ filters = {} } = {}) =>
			callMethod(GOVERNED_EXPORT_METHOD, { report_key: REPORT_KEY, filters: { ...filters } }),
	});
	reports.registerProvider(REPORT_PRODUCT, REPORT_KEY, provider);
	return provider;
}

function mountCashFlowOutlookPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Cash Flow Outlook.");
	}
	if (!target) throw new Error("Cash Flow Outlook mount target is required.");
	registerCashFlowOutlookProvider(window);
	const app = edgeUI.createEdgeApp(CashFlowOutlookReport);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	registerCashFlowOutlookProvider(window);
	window.CashFlowOutlookPage = CashFlowOutlookReport;
	window.mountCashFlowOutlookPage = mountCashFlowOutlookPage;
	window.registerCashFlowOutlookProvider = registerCashFlowOutlookProvider;
}

export { mountCashFlowOutlookPage, registerCashFlowOutlookProvider };
export default CashFlowOutlookReport;
