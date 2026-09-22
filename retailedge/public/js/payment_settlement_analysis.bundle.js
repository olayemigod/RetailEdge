import PaymentSettlementAnalysis from "./payment_settlement_analysis/PaymentSettlementAnalysis.vue";

const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "payment-settlement-analysis";
const PAGE_METHOD = "retailedge.payment_settlement_analysis.get_payment_settlement_analysis";
const EXPORT_METHOD = "retailedge.reporting_actions.get_report_export_data";

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

function registerPaymentSettlementAnalysisProvider(target = window) {
	const reports = target?.EdgeSuiteReports || target?.EdgeSuiteUI?.reports;
	if (!reports?.createPaginatedReportProvider || !reports?.registerProvider) return null;
	if (reports.hasProvider?.(REPORT_PRODUCT, REPORT_KEY)) {
		return reports.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || null;
	}

	const provider = reports.createPaginatedReportProvider({
		key: REPORT_KEY,
		defaultPageLength: 50,
		maxPageLength: 100,
		loadPage: async ({ filters = {}, start = 0, page_length = 50, sort = null } = {}) => {
			const safeLength = Math.max(1, Number(page_length || 50));
			const page = Math.floor(Math.max(0, Number(start || 0)) / safeLength) + 1;
			const result = await callMethod(PAGE_METHOD, {
				filters: { ...filters, page_size: safeLength },
				page,
				page_size: safeLength,
				sort,
			});
			const pagination = result.pagination || {};
			return {
				...result,
				start: Math.max(0, Number(start || 0)),
				page_length: safeLength,
				total: Number(pagination.total_rows ?? result.total ?? 0),
			};
		},
		exportReport: async ({ filters = {} } = {}) =>
			callMethod(EXPORT_METHOD, { report_key: REPORT_KEY, filters: { ...filters } }),
	});

	reports.registerProvider(REPORT_PRODUCT, REPORT_KEY, provider);
	return provider;
}

function mountPaymentSettlementAnalysis(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Payment & Settlement Analysis.");
	}
	if (!target) throw new Error("Payment & Settlement Analysis mount target is required.");
	registerPaymentSettlementAnalysisProvider(window);
	const app = edgeUI.createEdgeApp(PaymentSettlementAnalysis);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	registerPaymentSettlementAnalysisProvider(window);
	window.PaymentSettlementAnalysis = PaymentSettlementAnalysis;
	window.mountPaymentSettlementAnalysis = mountPaymentSettlementAnalysis;
	window.registerPaymentSettlementAnalysisProvider = registerPaymentSettlementAnalysisProvider;
}

export { mountPaymentSettlementAnalysis, registerPaymentSettlementAnalysisProvider };
export default PaymentSettlementAnalysis;
