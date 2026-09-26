import RetailSettings from "./retail_settings/RetailSettings.vue";

window.mountRetailSettings = function mountRetailSettings(target) {
	if (!target) return null;
	if (!window.EdgeSuiteUI?.createEdgeApp) throw new Error("Required interface runtime is unavailable.");
	return window.EdgeSuiteUI.createEdgeApp(RetailSettings).mount(target);
};
