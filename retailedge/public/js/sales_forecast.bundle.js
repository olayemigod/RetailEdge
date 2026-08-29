import SalesForecast from "./sales_forecast/SalesForecast.vue";

const PAGE_METHOD = "retailedge.sales_forecasting.get_sales_forecast";
const EXPORT_METHOD = "retailedge.sales_forecasting.get_sales_forecast_export";

function mountSalesForecast(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") throw new Error("EdgeSuite UI runtime is unavailable for Sales Forecast.");
	if (!target) throw new Error("Sales Forecast mount target is required.");
	const app = edgeUI.createEdgeApp(SalesForecast, { pageMethod: PAGE_METHOD, exportMethod: EXPORT_METHOD });
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.SalesForecast = SalesForecast;
	window.mountSalesForecast = mountSalesForecast;
}

export { mountSalesForecast };
export default SalesForecast;
