import BasketAffinity from "./basket_affinity/BasketAffinity.vue";

function mountBasketAffinity(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI || typeof edgeUI.createEdgeApp !== "function") {
		throw new Error("This page could not start. Refresh the page or contact your administrator.");
	}
	if (!target) throw new Error("Basket & Product Affinity mount target is required.");
	const app = edgeUI.createEdgeApp(BasketAffinity, {
		pageMethod: "retailedge.basket_affinity.get_basket_affinity",
		exportMethod: "retailedge.basket_affinity.get_basket_affinity_export",
	});
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.BasketAffinity = BasketAffinity;
	window.mountBasketAffinity = mountBasketAffinity;
}

export { mountBasketAffinity };
export default BasketAffinity;
