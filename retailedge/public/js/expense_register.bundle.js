import ExpenseRegisterReport from "./expense_register/ExpenseRegisterReport.vue";

const REPORT_PRODUCT = "RetailEdge";
const REPORT_PROVIDERS = Object.freeze({
	expense_register: {
		key: "expense-register",
		pageMethod: "retailedge.expense_register.get_expense_register",
	},
	expense_analysis: {
		key: "expense-analysis",
		pageMethod: "retailedge.expense_analysis.get_expense_analysis",
	},
});
const EXPORT_METHOD = "retailedge.reporting_actions.get_report_export_data";

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

	for (const config of Object.values(REPORT_PROVIDERS)) {
		if (reports.hasProvider?.(REPORT_PRODUCT, config.key)) continue;
		const provider = reports.createPaginatedReportProvider({
			key: config.key,
			defaultPageLength: 50,
			maxPageLength: 100,
			loadPage: async ({ filters = {}, start = 0, page_length = 50, sort = null } = {}) => {
				const safeLength = Math.max(1, Number(page_length || 50));
				const page = Math.floor(Math.max(0, Number(start || 0)) / safeLength) + 1;
				const result = await callMethod(config.pageMethod, {
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
					metadata: {
						...(result.metadata || {}),
						scope: result.scope || {},
					},
				};
			},
			exportReport: async ({ filters = {} } = {}) =>
				callMethod(EXPORT_METHOD, { report_key: config.key, filters: { ...filters } }),
		});
		reports.registerProvider(REPORT_PRODUCT, config.key, provider);
	}

	return reports.getProvider?.(REPORT_PRODUCT, "expense-register") || null;
}

function mountExpenseRegister(target, options = {}) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Expense reporting.");
	}
	if (!target) throw new Error("Expense reporting mount target is required.");
	registerExpenseRegisterProvider(window);
	const app = edgeUI.createEdgeApp(ExpenseRegisterReport, {
		reportType: options.reportType || "expense_register",
	});
	const rootComponent = app.mount(target);
	app.__retailedgeRootComponent = rootComponent;
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
