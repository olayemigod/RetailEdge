import * as Vue from "vue";
import SalespersonPerformanceDashboard from "./salesperson_performance_dashboard/SalespersonPerformanceDashboard.vue";

function getCompatibleEdgeUIRuntime() {
	const sharedRuntime = window.EdgeUI || {};
	const sharedComponents = sharedRuntime.components || sharedRuntime;
	const localComponents = SalespersonPerformanceDashboard.components || {};
	const components = {};

	for (const name of Object.keys(localComponents)) {
		components[name] = sharedComponents[name] || localComponents[name];
	}

	const createEdgeApp =
		typeof sharedRuntime.createEdgeApp === "function"
			? sharedRuntime.createEdgeApp.bind(sharedRuntime)
			: (component) => Vue.createApp(component);

	const runtime = {
		...sharedRuntime,
		version: sharedRuntime.version || "retailedge-local",
		components,
		createEdgeApp,
	};

	window.EdgeUI = runtime;
	return runtime;
}

function mountSalespersonPerformanceDashboard(target) {
	if (typeof window === "undefined") return null;

	const runtime = getCompatibleEdgeUIRuntime();
	const app = runtime.createEdgeApp(SalespersonPerformanceDashboard);
	if (!app || typeof app.mount !== "function") {
		throw new Error("EdgeSuite UI runtime compatibility error: mount is missing");
	}

	console.log("EdgeUI version:", runtime.version);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.SalespersonPerformanceDashboard = SalespersonPerformanceDashboard;
	window.mountSalespersonPerformanceDashboard = mountSalespersonPerformanceDashboard;
}

export { mountSalespersonPerformanceDashboard };
export default SalespersonPerformanceDashboard;
