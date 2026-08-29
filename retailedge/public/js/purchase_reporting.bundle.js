import PurchaseReportingReport from "./purchase_reporting/PurchaseReportingReport.vue";

const REPORT_PRODUCT = "RetailEdge";
const GOVERNED_EXPORT_METHOD = "retailedge.reporting_actions.get_report_export_data";
const PURCHASE_REPORT_PROVIDERS = Object.freeze({
	purchase_register: {
		key: "purchase-register",
		pageMethod: "retailedge.purchase_reporting.get_purchase_register",
		maxDatasetRows: 2000,
	},
	supplier_payables: {
		key: "supplier-payables",
		pageMethod: "retailedge.supplier_payables.get_supplier_payables",
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

function registerPurchaseReportingProviders(target = window) {
	const reports = target?.EdgeSuiteReports || target?.EdgeSuiteUI?.reports;
	if (!reports?.createBoundedPaginatedReportProvider || !reports?.registerProvider) return [];

	return Object.values(PURCHASE_REPORT_PROVIDERS).map((config) => {
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
						company_currency: result.company_currency || "",
						balance_basis: result.balance_basis || "",
						ageing_date: result.ageing_date || "",
						historical_balance_supported: Boolean(result.historical_balance_supported),
					},
				};
			},
			exportReport: async ({ filters = {} } = {}) =>
				callMethod(GOVERNED_EXPORT_METHOD, { report_key: config.key, filters: { ...filters } }),
		});
		reports.registerProvider(REPORT_PRODUCT, config.key, provider);
		return provider;
	});
}

function mountPurchaseReportingPage(target, options = {}) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Purchase reporting.");
	}
	if (!target) throw new Error("Purchase reporting mount target is required.");
	registerPurchaseReportingProviders(window);
	const app = edgeUI.createEdgeApp(PurchaseReportingReport, {
		reportType: options.reportType || "purchase_register",
	});
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	registerPurchaseReportingProviders(window);
	window.PurchaseReportingPage = PurchaseReportingReport;
	window.mountPurchaseReportingPage = mountPurchaseReportingPage;
	window.registerPurchaseReportingProviders = registerPurchaseReportingProviders;
}

export { mountPurchaseReportingPage, registerPurchaseReportingProviders };
export default PurchaseReportingReport;
