import ForecastingPlanning from "./forecasting_planning/ForecastingPlanning.vue";

const PAGE_METHOD = "retailedge.planning_intelligence.get_planning_intelligence";
const EXPORT_METHOD = "retailedge.planning_intelligence.get_planning_intelligence_export";

function mountForecastingPlanning(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") throw new Error("EdgeSuite UI runtime is unavailable for Forecasting & Planning.");
	if (!target) throw new Error("Forecasting & Planning mount target is required.");
	const app = edgeUI.createEdgeApp(ForecastingPlanning, { pageMethod: PAGE_METHOD, exportMethod: EXPORT_METHOD });
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") window.mountForecastingPlanning = mountForecastingPlanning;

export { mountForecastingPlanning };
export default ForecastingPlanning;
