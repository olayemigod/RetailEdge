import ActionCenter from "./action_center/ActionCenter.vue";

function mountActionCenter(root) {
	if (!root) return;
	if (!window.EdgeSuiteUI?.createEdgeApp) {
		root.innerHTML = '<div class="p-6 text-center"><strong>Action Centre could not start.</strong><div>Refresh the page or contact your administrator.</div></div>';
		return;
	}
	window.EdgeSuiteUI.createEdgeApp(ActionCenter).mount(root);
}

window.retailedgeMountActionCenter = mountActionCenter;
