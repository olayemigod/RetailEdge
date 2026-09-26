import MakeSale from "./make_sale/MakeSale.vue";

function mountRetailEdgeMakeSale(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Make Sale mount target is required");
	const app = edgeUI.createEdgeApp(MakeSale);
	app.mount(target);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeMakeSale = MakeSale;
	window.mountRetailEdgeMakeSale = mountRetailEdgeMakeSale;
}

export { mountRetailEdgeMakeSale };
export default MakeSale;
