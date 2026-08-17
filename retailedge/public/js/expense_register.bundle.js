import ExpenseRegisterReport from "./expense_register/ExpenseRegisterReport.vue";

const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "expense-register";
const PAGE_METHOD = "retailedge.expense_register.get_expense_register";
const EXPORT_METHOD = "retailedge.expense_register.get_expense_register_export";

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

function registerExpenseRegisterProvider(target = window) {
	const reports = target?.EdgeSuiteReports || target?.EdgeSuiteUI?.reports;
	if (!reports?.createPaginatedReportProvider || !reports?.registerProvider) return null;
	if (reports.hasProvider?.(REPORT_PRODUCT, REPORT_KEY)) {
		return reports.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || null;
	}

	const provider = reports.createPaginatedReportProvider({
		key: REPORT_KEY,
		defaultPageLength: 50,
		maxPageLength: 100,
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
					scope: result.scope || {},
				},
			};
		},
		exportReport: async ({ filters = {} } = {}) =>
			callMethod(EXPORT_METHOD, { filters: { ...filters } }),
	});

	reports.registerProvider(REPORT_PRODUCT, REPORT_KEY, provider);
	return provider;
}

function mountExpenseRegister(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Expense Register.");
	}
	if (!target) throw new Error("Expense Register mount target is required.");
	registerExpenseRegisterProvider(window);
	const app = edgeUI.createEdgeApp(ExpenseRegisterReport);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	registerExpenseRegisterProvider(window);
	window.ExpenseRegister = ExpenseRegisterReport;
	window.mountExpenseRegister = mountExpenseRegister;
	window.registerExpenseRegisterProvider = registerExpenseRegisterProvider;
}

export { mountExpenseRegister, registerExpenseRegisterProvider };
export default ExpenseRegisterReport;
