import CustomerReceivablesReport from "./customer_receivables/CustomerReceivablesReport.vue";

const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "customer-receivables";
const PAGE_METHOD = "retailedge.customer_receivables.get_customer_receivables";
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

function registerCustomerReceivablesProvider(target = window) {
	const reports = target?.EdgeSuiteReports || target?.EdgeSuiteUI?.reports;
	if (!reports?.createBoundedPaginatedReportProvider || !reports?.registerProvider) return null;
	if (reports.hasProvider?.(REPORT_PRODUCT, REPORT_KEY)) {
		return reports.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || null;
	}
	const provider = reports.createBoundedPaginatedReportProvider({
		key: REPORT_KEY,
		defaultPageLength: 50,
		maxPageLength: 100,
		maxDatasetRows: 2000,
		loadPage: async ({ filters = {}, start = 0, page_length = 50 } = {}) => {
			const safeLength = Math.max(1, Number(page_length || 50));
			const page = Math.floor(Math.max(0, Number(start || 0)) / safeLength) + 1;
			const result = await callMethod(PAGE_METHOD, {
				filters: { ...filters, page_size: safeLength },
				page,
				page_size: safeLength,
			});
			const pagination = result.pagination || {};
			return {
				...result,
				start: Math.max(0, Number(start || 0)),
				page_length: safeLength,
				total: Number(pagination.total_rows ?? result.total ?? 0),
				metadata: {
					...(result.metadata || {}),
					scan: result.scan || {},
					company_currency: result.company_currency || "",
					current_balance_date: result.current_balance_date || "",
					balance_basis: result.balance_basis || "",
				},
			};
		},
		exportReport: async ({ filters = {} } = {}) =>
			callMethod(GOVERNED_EXPORT_METHOD, { report_key: REPORT_KEY, filters: { ...filters } }),
	});
	reports.registerProvider(REPORT_PRODUCT, REPORT_KEY, provider);
	return provider;
}

function mountCustomerReceivablesPage(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Customer Receivables.");
	}
	if (!target) throw new Error("Customer Receivables mount target is required.");
	registerCustomerReceivablesProvider(window);
	const app = edgeUI.createEdgeApp(CustomerReceivablesReport);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	registerCustomerReceivablesProvider(window);
	window.CustomerReceivablesPage = CustomerReceivablesReport;
	window.mountCustomerReceivablesPage = mountCustomerReceivablesPage;
	window.registerCustomerReceivablesProvider = registerCustomerReceivablesProvider;
}

export { mountCustomerReceivablesPage, registerCustomerReceivablesProvider };
export default CustomerReceivablesReport;
