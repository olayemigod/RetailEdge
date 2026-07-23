import * as Vue from "vue";

export const MINIMUM_EDGE_SUITE_UI_VERSION = "0.6.0";

const REQUIRED_COMPONENTS = Object.freeze([
	"EdgeAppShell",
	"EdgePageLayout",
	"EdgePageHeader",
	"EdgeFilterBar",
	"EdgeStatCard",
	"EdgeStatusBadge",
	"EdgeLoadingState",
	"EdgeErrorState",
	"EdgeEmptyState",
	"EdgeBranchContextSwitcher",
	"EdgeLinkField",
	"EdgeDataTable",
	"EdgeDocumentForm",
	"EdgeWorkflowBar",
	"EdgeSettingsLayout",
	"EdgeIcon",
]);

function versionParts(version) {
	return String(version || "0.0.0")
		.split(".")
		.slice(0, 3)
		.map((part) => Number.parseInt(part, 10) || 0);
}

export function versionAtLeast(version, minimum = MINIMUM_EDGE_SUITE_UI_VERSION) {
	const current = versionParts(version);
	const required = versionParts(minimum);
	for (let index = 0; index < 3; index += 1) {
		if (current[index] > required[index]) return true;
		if (current[index] < required[index]) return false;
	}
	return true;
}

export function getRetailEdgeRuntime() {
	return window.EdgeSuiteUI || window.EdgeUI || null;
}

export function assertRetailEdgeRuntime() {
	const runtime = getRetailEdgeRuntime();
	if (!runtime?.install || !runtime?.components) {
		throw new Error("EdgeSuite UI runtime is unavailable.");
	}
	if (!versionAtLeast(runtime.version)) {
		throw new Error(
			`RetailEdge requires EdgeSuite UI ${MINIMUM_EDGE_SUITE_UI_VERSION} or newer; found ${runtime.version || "unknown"}.`,
		);
	}
	const missing = REQUIRED_COMPONENTS.filter((name) => !runtime.components[name]);
	if (missing.length) {
		throw new Error(`EdgeSuite UI is missing required components: ${missing.join(", ")}.`);
	}
	return runtime;
}

export function createRetailEdgeApp(rootComponent, rootProps = null) {
	if (!rootComponent) throw new TypeError("RetailEdge root component is required.");
	const runtime = assertRetailEdgeRuntime();
	const app = Vue.createApp(rootComponent, rootProps || {});
	runtime.install(app);
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeUI = Object.assign(window.RetailEdgeUI || {}, {
		minimumVersion: MINIMUM_EDGE_SUITE_UI_VERSION,
		getRuntime: getRetailEdgeRuntime,
		assertRuntime: assertRetailEdgeRuntime,
		createApp: createRetailEdgeApp,
	});
}
