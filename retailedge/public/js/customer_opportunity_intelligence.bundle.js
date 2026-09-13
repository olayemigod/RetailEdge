import CustomerOpportunityIntelligence from "./customer_opportunity_intelligence/CustomerOpportunityIntelligence.vue";

function mountCustomerOpportunityIntelligence(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Customer Retention & Opportunity Intelligence.");
	}
	if (!target) throw new Error("Customer Retention & Opportunity Intelligence mount target is required.");
	const app = edgeUI.createEdgeApp(CustomerOpportunityIntelligence, {
		pageMethod: "retailedge.customer_opportunity_intelligence.get_customer_opportunity_intelligence",
		exportMethod: "retailedge.customer_opportunity_intelligence.get_customer_opportunity_intelligence_export",
	});
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.CustomerOpportunityIntelligence = CustomerOpportunityIntelligence;
	window.mountCustomerOpportunityIntelligence = mountCustomerOpportunityIntelligence;
}

export { mountCustomerOpportunityIntelligence };
export default CustomerOpportunityIntelligence;
