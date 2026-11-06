import RetailEdgeBusinessHub from "./retailedge_business_hub/RetailEdgeBusinessHub.vue";
import UserReadinessNotice from "./retailedge_business_hub/UserReadinessNotice.vue";
import { installGuidedCreateSearch } from "./retailedge_business_hub/guided_create_search";

function bindEdgeSuiteRuntimeComponents(rootComponents, runtimeComponents) {
	const visited = new Set();
	const unresolved = new Set();

	function visit(component) {
		if (
			!component ||
			(typeof component !== "object" && typeof component !== "function") ||
			visited.has(component)
		) {
			return;
		}
		visited.add(component);

		const localComponents = component.components;
		if (!localComponents || typeof localComponents !== "object") return;

		Object.entries(localComponents).forEach(([name, registeredComponent]) => {
			if (registeredComponent == null) {
				const runtimeComponent = runtimeComponents?.[name];
				if (runtimeComponent) {
					localComponents[name] = runtimeComponent;
				} else {
					unresolved.add(name);
				}
				return;
			}
			visit(registeredComponent);
		});
	}

	rootComponents.forEach(visit);
	return Array.from(unresolved).sort();
}

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

	const missingComponents = bindEdgeSuiteRuntimeComponents(
		[UserReadinessNotice, RetailEdgeBusinessHub],
		window.EdgeSuiteUI.components || window.EdgeSuiteUI
	);
	if (missingComponents.length) {
		console.error(
			"[RetailEdge Business Hub] unresolved EdgeSuite components",
			missingComponents
		);
		throw new Error(
			"Business Hub could not start because required interface components are unavailable."
		);
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
