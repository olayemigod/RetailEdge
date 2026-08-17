import StockPosition from "./stock_position/StockPosition.vue";

const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "stock-position";
const PAGE_METHOD = "retailedge.stock_position.get_stock_position";
const EXPORT_METHOD = "retailedge.stock_position.get_stock_position_export";

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

function registerStockPositionProvider(target = window) {
	const reports = target?.EdgeSuiteReports || target?.EdgeSuiteUI?.reports;
	if (!reports?.createBoundedPaginatedReportProvider || !reports?.registerProvider) return null;
	if (reports.hasProvider?.(REPORT_PRODUCT, REPORT_KEY)) {
		return reports.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || null;
	}

	const provider = reports.createBoundedPaginatedReportProvider({
		key: REPORT_KEY,
		defaultPageLength: 50,
		maxPageLength: 100,
		maxDatasetRows: 10000,
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
					scope: result.scope || {},
					show_costs: result.show_costs || 0,
					company_currency: result.company_currency || "",
				},
			};
		},
		exportReport: async ({ filters = {} } = {}) =>
			callMethod(EXPORT_METHOD, { filters: { ...filters } }),
	});

	reports.registerProvider(REPORT_PRODUCT, REPORT_KEY, provider);
	return provider;
}

function mountStockPosition(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Stock Position.");
	}
	if (!target) throw new Error("Stock Position mount target is required.");
	registerStockPositionProvider(window);
	const app = edgeUI.createEdgeApp(StockPosition);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	registerStockPositionProvider(window);
	window.StockPosition = StockPosition;
	window.mountStockPosition = mountStockPosition;
	window.registerStockPositionProvider = registerStockPositionProvider;
}

export { mountStockPosition, registerStockPositionProvider };
export default StockPosition;
