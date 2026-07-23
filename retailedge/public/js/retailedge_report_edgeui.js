(function () {
	"use strict";

	const reportConfigs = new Map();
	const reportInstances = new WeakMap();
	const METADATA_FLAG = "is_edgesuite_metadata";

	function runtime() {
		return window.EdgeSuiteUI || window.EdgeUI || null;
	}

	function supportsRuntime(edgeUI) {
		return Boolean(
			edgeUI
			&& typeof edgeUI.createEdgeApp === "function"
			&& edgeUI.Vue
			&& edgeUI.components?.EdgePageHeader
			&& edgeUI.components?.EdgeDashboardLayout
			&& edgeUI.components?.EdgeStatCard
			&& edgeUI.components?.EdgeStatusBadge
			&& edgeUI.components?.EdgeEmptyState
			&& edgeUI.components?.EdgeIcon,
		);
	}

	function configFor(reportName) {
		return reportConfigs.get(reportName) || null;
	}

	function reportMain(report) {
		return report?.page?.main_section?.length ? report.page.main_section : null;
	}

	function ensureHost(report) {
		const main = reportMain(report);
		if (!main) return null;
		main.closest(".page-container").addClass("retailedge-edgeui-report-page");
		let host = main.children(".retailedge-report-edgeui-host").get(0);
		if (!host) {
			host = document.createElement("div");
			host.className = "retailedge-report-edgeui-host";
			main.prepend(host);
		}
		return host;
	}

	function nativeSummary(report) {
		return reportMain(report)?.children(".report-summary");
	}

	function hideNativeSummary(report) {
		nativeSummary(report)?.attr("aria-hidden", "true").hide();
	}

	function showNativeSummary(report) {
		nativeSummary(report)?.removeAttr("aria-hidden").show();
	}

	function tone(indicator) {
		const value = String(indicator || "neutral").trim().toLowerCase();
		if (["green", "success"].includes(value)) return "success";
		if (["orange", "yellow", "warning"].includes(value)) return "warning";
		if (["red", "danger"].includes(value)) return "danger";
		if (["blue", "purple", "info"].includes(value)) return "info";
		return "neutral";
	}

	function formatValue(card) {
		const value = card?.value;
		if (value === null || value === undefined || value === "") return "—";
		const datatype = String(card.datatype || card.value_type || "").toLowerCase();
		if (datatype === "currency") {
			return frappe.format_value
				? frappe.format_value(value, { fieldtype: "Currency" })
				: String(value);
		}
		if (datatype === "percent") {
			return `${Number(value || 0).toFixed(1).replace(/\.0$/, "")}%`;
		}
		if (["float", "int"].includes(datatype) || typeof value === "number") {
			const number = Number(value || 0);
			return Number.isFinite(number)
				? number.toLocaleString(undefined, { maximumFractionDigits: datatype === "int" ? 0 : 2 })
				: String(value);
		}
		return String(value);
	}

	function selectedCards(metadata, cards) {
		if (!Array.isArray(cards)) return [];
		const labels = Array.isArray(metadata?.visible_card_labels)
			? metadata.visible_card_labels.filter(Boolean)
			: [];
		if (!labels.length) return cards;
		const index = new Map(labels.map((label, position) => [String(label), position]));
		return cards
			.filter((card) => index.has(String(card?.label || card?.title || "")))
			.sort((left, right) => {
				const leftLabel = String(left?.label || left?.title || "");
				const rightLabel = String(right?.label || right?.title || "");
				return index.get(leftLabel) - index.get(rightLabel);
			});
	}

	function copyReportLink() {
		const value = window.location.href;
		if (navigator.clipboard?.writeText) {
			navigator.clipboard.writeText(value).then(() => {
				frappe.show_alert({ message: __("Report link copied."), indicator: "green" });
			});
			return;
		}
		const input = document.createElement("input");
		input.value = value;
		document.body.appendChild(input);
		input.select();
		document.execCommand("copy");
		input.remove();
		frappe.show_alert({ message: __("Report link copied."), indicator: "green" });
	}

	function reportAction(label, className, handler, disabled = false) {
		return {
			label,
			className,
			handler,
			disabled,
		};
	}

	function createReportApp(report, reportName, config, edgeUI, host) {
		const { h, reactive } = edgeUI.Vue;
		const {
			EdgePageHeader,
			EdgeDashboardLayout,
			EdgeStatCard,
			EdgeStatusBadge,
			EdgeEmptyState,
			EdgeIcon,
		} = edgeUI.components;
		const state = reactive({
			metadata: {},
			cards: [],
			rowCount: 0,
			empty: false,
		});

		const root = {
			name: "RetailEdgeReportEdgeUISurface",
			setup() {
				return () => {
					const metadata = state.metadata || {};
					const capabilities = metadata.capabilities || {};
					const status = metadata.status || {};
					const suggestions = metadata.empty_state?.suggestions || [];
					const recommendations = Array.isArray(metadata.recommendations)
						? metadata.recommendations
						: [];
					const cards = selectedCards(metadata, state.cards);
					const actions = [
						reportAction(__("Refresh"), "edge-button edge-button--primary", () => report.refresh()),
						capabilities.supports_export !== false && typeof report.export_report === "function"
							? reportAction(__("Export"), "edge-button", () => report.export_report())
							: null,
						capabilities.supports_print !== false && typeof report.print_report === "function"
							? reportAction(__("Print"), "edge-button", () => report.print_report())
							: null,
						capabilities.supports_share !== false
							? reportAction(__("Share"), "edge-button", copyReportLink)
							: null,
					].filter(Boolean);

					const children = [
						h(EdgePageHeader, {
							eyebrow: config.eyebrow || __("Retail Intelligence"),
							title: config.title || metadata.title || reportName,
							subtitle: config.subtitle || "",
						}, {
							actions: () => actions.map((action) => h(
								"button",
								{
									type: "button",
									class: action.className,
									disabled: action.disabled,
									onClick: action.handler,
								},
								action.label,
							)),
						}),
						h("div", { class: "retailedge-report-edgeui-context" }, [
							h(EdgeStatusBadge, {
								label: __("{0} row(s)", [state.rowCount]),
								status: state.rowCount ? "available" : "empty",
								tone: state.rowCount ? "success" : "neutral",
							}),
							h(EdgeStatusBadge, {
								label: metadata.filter_summary || __("Current report filters"),
								status: "filters",
								tone: "neutral",
							}),
							status.label
								? h(EdgeStatusBadge, {
									label: status.label,
									status: status.label,
									tone: status.tone || "neutral",
								})
								: null,
						].filter(Boolean)),
					];

					if (!state.empty && cards.length) {
						children.push(h(EdgeDashboardLayout, { minColumnWidth: "12.5rem" }, {
							default: () => cards.map((card) => h(
								"div",
								{ class: "retailedge-report-edgeui-card" },
								[h(EdgeStatCard, {
									label: card.label || card.title || "",
									value: formatValue(card),
									helper: card.subtitle || card.helper || "",
									tone: tone(card.indicator || card.tone),
									tooltip: card.tooltip || "",
								})],
							)),
						}));
					}

					if (recommendations.length) {
						children.push(h("section", { class: "retailedge-report-edgeui-recommendations" }, [
							h("header", { class: "retailedge-report-edgeui-section-heading" }, [
								h("p", { class: "edge-eyebrow" }, __("Actionable insight")),
								h("h2", {}, __("Items requiring attention")),
							]),
							h("div", { class: "retailedge-report-edgeui-recommendation-list" }, recommendations.map((item) => h(
								"article",
								{ class: "retailedge-report-edgeui-recommendation" },
								[
									h(EdgeStatusBadge, {
										label: item.severity === "danger" ? __("Urgent") : __("Review"),
										status: item.severity || "warning",
										tone: item.severity || "warning",
									}),
									h("div", {}, [
										h("strong", {}, item.title || __("Recommendation")),
										h("p", {}, item.description || ""),
									]),
								],
							))),
						]));
					}

					if (state.empty) {
						children.push(h("section", { class: "retailedge-report-edgeui-empty" }, [
							h(EdgeEmptyState, {
								title: metadata.empty_state?.message || __("No matching records"),
								description: config.emptyDescription || __("Adjust the filters or date range and refresh the report."),
								icon: metadata.icon || "report",
							}),
							suggestions.length
								? h("ul", { class: "retailedge-report-edgeui-suggestions" }, suggestions.map((item) => h("li", {}, item)))
								: null,
						]));
					}

					return h("section", { class: "retailedge-report-edgeui-surface" }, [
						h("span", { class: "retailedge-report-edgeui-product-mark", "aria-hidden": "true" }, [
							h(EdgeIcon, { name: metadata.icon || "report", size: "sm" }),
						]),
						...children,
					]);
				};
			},
		};

		const app = edgeUI.createEdgeApp(root);
		app.mount(host);
		return { app, state, host, reportName };
	}

	function ensureInstance(report, reportName) {
		const existing = reportInstances.get(report);
		if (existing?.reportName === reportName && existing.host?.isConnected) return existing;
		const config = configFor(reportName);
		const edgeUI = runtime();
		const host = config ? ensureHost(report) : null;
		if (!config || !host || !supportsRuntime(edgeUI)) return null;
		if (existing?.app?.unmount) existing.app.unmount();
		const instance = createReportApp(report, reportName, config, edgeUI, host);
		reportInstances.set(report, instance);
		return instance;
	}

	function renderSummary(report, reportName, metadata, cards) {
		const instance = ensureInstance(report, reportName);
		if (!instance) return false;
		instance.state.metadata = metadata || {};
		instance.state.cards = Array.isArray(cards) ? cards : [];
		instance.state.rowCount = Number.isFinite(Number(metadata?.row_count))
			? Number(metadata.row_count)
			: (Array.isArray(report.data) ? report.data.length : 0);
		instance.state.empty = instance.state.rowCount === 0;
		hideNativeSummary(report);
		return true;
	}

	function extractSummary(summary) {
		if (!Array.isArray(summary)) return null;
		const cards = [...summary];
		const index = cards.findIndex((item) => item?.[METADATA_FLAG]);
		if (index === -1) return null;
		return { metadata: cards.splice(index, 1)[0], cards };
	}

	function patchSummaryRenderer(report, reportName) {
		if (report.__retailedgeEdgeUIReportName === reportName) return;
		const fallback = typeof report.show_and_render_summary === "function"
			? report.show_and_render_summary.bind(report)
			: null;

		report.show_and_render_summary = function (summary) {
			const extracted = extractSummary(summary);
			if (!extracted) return fallback ? fallback(summary) : undefined;
			report.__retailedgeEdgeUISummary = extracted;
			if (!renderSummary(report, reportName, extracted.metadata, extracted.cards)) {
				showNativeSummary(report);
				return fallback ? fallback(extracted.cards) : undefined;
			}
			return undefined;
		};
		report.__retailedgeEdgeUIReportName = reportName;
	}

	function refresh(report, reportName) {
		const pending = report?.__retailedgeEdgeUISummary;
		if (!pending) return Boolean(ensureInstance(report, reportName));
		return renderSummary(report, reportName, pending.metadata, pending.cards);
	}

	function attach(report, reportName) {
		if (!report || !configFor(reportName)) return false;
		patchSummaryRenderer(report, reportName);
		const mount = () => {
			ensureInstance(report, reportName);
			refresh(report, reportName);
		};
		if (supportsRuntime(runtime())) {
			mount();
			return true;
		}
		frappe.require("edgeui.bundle.js", mount);
		return true;
	}

	window.retailedgeReportEdgeUI = {
		register(reportName, config) {
			if (!reportName) return;
			reportConfigs.set(reportName, Object.assign({}, config || {}));
		},
		handles(reportName) {
			return reportConfigs.has(reportName);
		},
		attach,
		refresh,
		renderSummary,
	};
})();
