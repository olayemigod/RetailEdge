import RetailEdgeGlobalCreateHost from "./retailedge_business_hub/RetailEdgeGlobalCreateHost.vue";
import { installGuidedCreateSearch } from "./retailedge_business_hub/guided_create_search";

const HOST_ID = "retailedge-global-create-host";

function ensureHostTarget() {
	if (typeof document === "undefined" || !document.body) return null;
	let target = document.getElementById(HOST_ID);
	if (!target) {
		target = document.createElement("div");
		target.id = HOST_ID;
		document.body.appendChild(target);
	}
	return target;
}

function mountRetailEdgeGlobalCreateHost() {
	if (typeof window === "undefined") return null;
	if (window.__retailedgeGlobalCreateApp) return window.__retailedgeGlobalCreateApp;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI createEdgeApp API is unavailable for Global Create.");
	}
	const target = ensureHostTarget();
	if (!target) throw new Error("Global Create host target is unavailable.");
	const app = edgeUI.createEdgeApp(RetailEdgeGlobalCreateHost);
	app.mount(target);
	const destroySearch = installGuidedCreateSearch(window);
	const originalUnmount = app.unmount.bind(app);
	app.unmount = () => {
		destroySearch();
		originalUnmount();
		window.__retailedgeGlobalCreateApp = null;
		target.remove();
	};
	window.__retailedgeGlobalCreateApp = app;
	return app;
}

function openRetailEdgeGlobalCreate() {
	mountRetailEdgeGlobalCreateHost();
	document.dispatchEvent(new CustomEvent("retailedge-open-global-create"));
}

if (typeof window !== "undefined") {
	window.retailedgeEnsureGlobalCreateHost = mountRetailEdgeGlobalCreateHost;
	window.retailedgeOpenGlobalCreate = openRetailEdgeGlobalCreate;
}

export { mountRetailEdgeGlobalCreateHost, openRetailEdgeGlobalCreate };
export default RetailEdgeGlobalCreateHost;
