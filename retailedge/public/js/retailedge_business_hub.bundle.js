import RetailEdgeBusinessHub from "./retailedge_business_hub/RetailEdgeBusinessHub.vue";
import UserReadinessNotice from "./retailedge_business_hub/UserReadinessNotice.vue";
import { installGuidedCreateSearch } from "./retailedge_business_hub/guided_create_search";

function mountRetailEdgeBusinessHub(target) {
	if (typeof window === "undefined" || !window.EdgeSuiteUI) {
		throw new Error("Standalone EdgeSuite UI runtime not loaded.");
	}
	if (typeof window.EdgeSuiteUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI createEdgeApp API is unavailable.");
	}
	if (!target) {
		throw new Error("RetailEdge Business Hub mount target is unavailable.");
	}

	target.replaceChildren();
	const readinessTarget = document.createElement("div");
	readinessTarget.className = "retailedge-user-readiness-notice-root";
	const hubTarget = document.createElement("div");
	hubTarget.className = "retailedge-business-hub-app-root";
	target.append(readinessTarget, hubTarget);

	const readinessApp = window.EdgeSuiteUI.createEdgeApp(UserReadinessNotice);
	readinessApp.mount(readinessTarget);
	const app = window.EdgeSuiteUI.createEdgeApp(RetailEdgeBusinessHub);
	app.mount(hubTarget);

	const destroyGuidedCreateSearch = installGuidedCreateSearch(window);
	const originalUnmount = app.unmount.bind(app);
	app.unmount = () => {
		destroyGuidedCreateSearch();
		readinessApp.unmount();
		originalUnmount();
	};
	return app;
}

if (typeof window !== "undefined") {
	window.mountRetailEdgeBusinessHub = mountRetailEdgeBusinessHub;
}

export { mountRetailEdgeBusinessHub };
export default RetailEdgeBusinessHub;
