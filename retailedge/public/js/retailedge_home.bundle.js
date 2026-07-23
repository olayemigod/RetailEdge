import RetailEdgeHome from "./retailedge_home/RetailEdgeHome.vue";
import { createRetailEdgeApp } from "./retailedge_ui/app_factory";

let activeApp = null;

export function mountRetailEdgeHome(target) {
	if (!target) throw new TypeError("RetailEdge Home mount target is required.");
	if (activeApp?.unmount) activeApp.unmount();
	activeApp = createRetailEdgeApp(RetailEdgeHome);
	activeApp.mount(target);
	return activeApp;
}

export function unmountRetailEdgeHome() {
	if (activeApp?.unmount) activeApp.unmount();
	activeApp = null;
}

if (typeof window !== "undefined") {
	window.mountRetailEdgeHome = mountRetailEdgeHome;
	window.unmountRetailEdgeHome = unmountRetailEdgeHome;
}

export default RetailEdgeHome;
