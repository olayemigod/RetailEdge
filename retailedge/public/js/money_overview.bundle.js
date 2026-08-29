import MoneyOverview from "./money_overview/MoneyOverview.vue";

function mountMoneyOverview(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Money Overview mount target is required");
	const app = edgeUI.createEdgeApp(MoneyOverview);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.MoneyOverview = MoneyOverview;
	window.mountMoneyOverview = mountMoneyOverview;
}

export { mountMoneyOverview };
export default MoneyOverview;
