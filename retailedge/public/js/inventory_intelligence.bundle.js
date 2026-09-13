import InventoryIntelligenceCentre from "./inventory_intelligence/InventoryIntelligenceCentre.vue";

const PAGE_METHOD = "retailedge.inventory_health.get_inventory_health";
const EXPORT_METHOD = "retailedge.inventory_health.get_inventory_health_export";

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function mountInventoryIntelligence(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("EdgeSuite UI runtime is unavailable for Inventory Intelligence.");
	}
	if (!target) throw new Error("Inventory Intelligence mount target is required.");
	const app = edgeUI.createEdgeApp(InventoryIntelligenceCentre, {
		pageMethod: PAGE_METHOD,
		exportMethod: EXPORT_METHOD,
	});
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.InventoryIntelligenceCentre = InventoryIntelligenceCentre;
	window.mountInventoryIntelligence = mountInventoryIntelligence;
}

export { mountInventoryIntelligence };
export default InventoryIntelligenceCentre;
