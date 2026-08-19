import ExpenseReviewReport from "./expense_review/ExpenseReviewReport.vue";

const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "expense-review";
const PAGE_METHOD = "retailedge.expense_review.get_expense_review";
const GOVERNED_EXPORT_METHOD = "retailedge.reporting_actions.get_report_export_data";

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject });
	});
}

function registerExpenseReviewProvider(target = window) {
	const reports = target?.EdgeSuiteReports || target?.EdgeSuiteUI?.reports;
	if (!reports?.createBoundedPaginatedReportProvider || !reports?.registerProvider) return null;
	if (reports.hasProvider?.(REPORT_PRODUCT, REPORT_KEY)) return reports.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || null;
	const provider = reports.createBoundedPaginatedReportProvider({
		key: REPORT_KEY,
		defaultPageLength: 50,
		maxPageLength: 100,
		maxDatasetRows: 5000,
		loadPage: async ({ filters = {}, start = 0, page_length = 50 } = {}) => {
			const safeLength = Math.max(1, Number(page_length || 50));
			const page = Math.floor(Math.max(0, Number(start || 0)) / safeLength) + 1;
			const result = await callMethod(PAGE_METHOD, { filters: { ...filters }, page, page_size: safeLength });
			return {
				...result,
				start: Math.max(0, Number(start || 0)),
				page_length: safeLength,
				total: Number(result.pagination?.total_rows ?? 0),
				metadata: { ...(result.metadata || {}), scan: result.scan || {}, can_review: Boolean(result.can_review) },
			};
		},
		exportReport: async ({ filters = {} } = {}) =>
			callMethod(GOVERNED_EXPORT_METHOD, { report_key: REPORT_KEY, filters: { ...filters } }),
	});
	reports.registerProvider(REPORT_PRODUCT, REPORT_KEY, provider);
	return provider;
}

function mountExpenseReviewPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") throw new Error("EdgeSuite UI runtime is unavailable for Expense Review.");
	if (!target) throw new Error("Expense Review mount target is required.");
	registerExpenseReviewProvider(window);
	const app = edgeUI.createEdgeApp(ExpenseReviewReport);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	registerExpenseReviewProvider(window);
	window.ExpenseReviewPage = ExpenseReviewReport;
	window.mountExpenseReviewPage = mountExpenseReviewPage;
	window.registerExpenseReviewProvider = registerExpenseReviewProvider;
}

export { mountExpenseReviewPage, registerExpenseReviewProvider };
export default ExpenseReviewReport;
