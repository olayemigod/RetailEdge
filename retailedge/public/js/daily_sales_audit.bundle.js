import DailySalesAuditReport from "./daily_sales_audit/DailySalesAuditReport.vue";

const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "daily-sales-audit";
const PAGE_METHOD = "retailedge.daily_sales_audit_page.get_daily_sales_audit_page";
const EXPORT_METHOD = "retailedge.reporting_actions.get_report_export_data";

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject });
	});
}

function registerDailySalesAuditProvider(target = window) {
	const reports = target?.EdgeSuiteReports || target?.EdgeSuiteUI?.reports;
	if (!reports?.createBoundedPaginatedReportProvider || !reports?.registerProvider) return null;
	if (reports.hasProvider?.(REPORT_PRODUCT, REPORT_KEY)) return reports.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || null;
	const provider = reports.createBoundedPaginatedReportProvider({
		key: REPORT_KEY,
		defaultPageLength: 50,
		maxPageLength: 100,
		maxDatasetRows: 1000,
		loadPage: async ({ filters = {}, start = 0, page_length = 50 } = {}) => {
			const safeLength = Math.max(1, Number(page_length || 50));
			const page = Math.floor(Math.max(0, Number(start || 0)) / safeLength) + 1;
			const result = await callMethod(PAGE_METHOD, { filters: { ...filters }, page, page_size: safeLength });
			return {
				...result,
				start: Math.max(0, Number(start || 0)),
				page_length: safeLength,
				total: Number(result.pagination?.total_rows ?? 0),
				metadata: { ...(result.metadata || {}), scan: result.scan || {} },
			};
		},
		exportReport: async ({ filters = {} } = {}) => callMethod(EXPORT_METHOD, { report_key: REPORT_KEY, filters: { ...filters } }),
	});
	reports.registerProvider(REPORT_PRODUCT, REPORT_KEY, provider);
	return provider;
}

function mountDailySalesAuditPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") throw new Error("EdgeSuite UI runtime is unavailable for Daily Sales Audit.");
	if (!target) throw new Error("Daily Sales Audit mount target is required.");
	registerDailySalesAuditProvider(window);
	const app = edgeUI.createEdgeApp(DailySalesAuditReport);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	registerDailySalesAuditProvider(window);
	window.DailySalesAuditPage = DailySalesAuditReport;
	window.mountDailySalesAuditPage = mountDailySalesAuditPage;
}

export { mountDailySalesAuditPage, registerDailySalesAuditProvider };
export default DailySalesAuditReport;
