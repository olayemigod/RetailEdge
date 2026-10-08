import CustomerOpportunityIntelligence from "./customer_opportunity_intelligence/CustomerOpportunityIntelligence.vue";

function mountCustomerOpportunityIntelligence(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
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
