import SalespersonPerformanceDashboard from "./salesperson_performance_dashboard/SalespersonPerformanceDashboard.vue";
import { createRetailEdgeApp } from "./retailedge_ui/app_factory";

let activeApp = null;

export function mountSalespersonPerformanceDashboard(target) {
	if (!target) throw new TypeError("Salesperson Performance Dashboard mount target is required.");
	if (activeApp?.unmount) activeApp.unmount();
	activeApp = createRetailEdgeApp(SalespersonPerformanceDashboard);
	activeApp.mount(target);
	return activeApp;
}

export function unmountSalespersonPerformanceDashboard() {
	if (activeApp?.unmount) activeApp.unmount();
	activeApp = null;
}

if (typeof window !== "undefined") {
	window.mountSalespersonPerformanceDashboard = mountSalespersonPerformanceDashboard;
	window.unmountSalespersonPerformanceDashboard = unmountSalespersonPerformanceDashboard;
}

export default SalespersonPerformanceDashboard;
