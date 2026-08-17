import SalesReportingReport from "./sales_reporting/SalesReportingReport.vue";

const REPORT_PRODUCT = "RetailEdge";
const SALES_REPORT_PROVIDERS = Object.freeze({
	sales_by_item: {
		key: "sales-by-item",
		pageMethod: "retailedge.sales_reporting.get_sales_by_item",
		exportMethod: "retailedge.sales_reporting.get_sales_by_item_export",
		maxDatasetRows: 10000,
	},
	sales_invoice_register: {
		key: "sales-invoice-register",
		pageMethod: "retailedge.sales_reporting.get_sales_invoice_register",
		exportMethod: "retailedge.sales_reporting.get_sales_invoice_register_export",
		maxDatasetRows: 2000,
	},
});

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function registerSalesReportingProviders(target = window) {
	const reports = target?.EdgeSuiteReports || target?.EdgeSuiteUI?.reports;
	if (!reports?.createBoundedPaginatedReportProvider || !reports?.registerProvider) return [];

	return Object.values(SALES_REPORT_PROVIDERS).map((config) => {
		if (reports.hasProvider?.(REPORT_PRODUCT, config.key)) {
			return reports.getProvider?.(REPORT_PRODUCT, config.key) || null;
		}
		const provider = reports.createBoundedPaginatedReportProvider({
			key: config.key,
			defaultPageLength: 50,
			maxPageLength: 100,
			maxDatasetRows: config.maxDatasetRows,
			loadPage: async ({ filters = {}, start = 0, page_length = 50 } = {}) => {
				const safeLength = Math.max(1, Number(page_length || 50));
				const page = Math.floor(Math.max(0, Number(start || 0)) / safeLength) + 1;
				const result = await callMethod(config.pageMethod, {
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
						scope: result.scope || {},
						company_currency: result.company_currency || "",
					},
				};
			},
			exportReport: async ({ filters = {} } = {}) =>
				callMethod(config.exportMethod, { filters: { ...filters } }),
		});
		reports.registerProvider(REPORT_PRODUCT, config.key, provider);
		return provider;
	});
}

function mountSalesReportingPage(target, options = {}) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Sales reporting.");
	}
	if (!target) throw new Error("Sales reporting mount target is required.");
	registerSalesReportingProviders(window);
	const app = edgeUI.createEdgeApp(SalesReportingReport, {
		reportType: options.reportType || "sales_by_item",
	});
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	registerSalesReportingProviders(window);
	window.SalesReportingPage = SalesReportingReport;
	window.mountSalesReportingPage = mountSalesReportingPage;
	window.registerSalesReportingProviders = registerSalesReportingProviders;
}

export { mountSalesReportingPage, registerSalesReportingProviders };
export default SalesReportingReport;
