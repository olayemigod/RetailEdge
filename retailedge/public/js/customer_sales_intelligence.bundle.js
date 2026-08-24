import CustomerSalesIntelligence from "./customer_sales_intelligence/CustomerSalesIntelligence.vue";

const PAGE_METHOD = "retailedge.customer_sales_intelligence.get_customer_sales_intelligence";
const EXPORT_METHOD = "retailedge.customer_sales_intelligence.get_customer_sales_intelligence_export";

function mountCustomerSalesIntelligence(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Customer & Sales Intelligence.");
	}
	if (!target) throw new Error("Customer & Sales Intelligence mount target is required.");
	const app = edgeUI.createEdgeApp(CustomerSalesIntelligence, {
		pageMethod: PAGE_METHOD,
		exportMethod: EXPORT_METHOD,
	});
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.CustomerSalesIntelligence = CustomerSalesIntelligence;
	window.mountCustomerSalesIntelligence = mountCustomerSalesIntelligence;
}

export { mountCustomerSalesIntelligence };
export default CustomerSalesIntelligence;
