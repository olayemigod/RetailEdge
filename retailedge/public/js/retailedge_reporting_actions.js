(() => {
	"use strict";

	const SHELL_REPORT_ROUTES = Object.freeze({
		"/app/cash-movement": "cash-movement",
		"/app/expense-register": "expense-register",
		"/app/expense-review": "expense-review",
		"/app/cash-shift-verification": "cash-shift-verification",
		"/app/daily-sales-audit": "daily-sales-audit",
		"/app/sales-by-item": "sales-by-item",
		"/app/sales-invoice-register": "sales-invoice-register",
		"/app/customer-receivables": "customer-receivables",
		"/app/purchase-register": "purchase-register",
		"/app/supplier-payables": "supplier-payables",
		"/app/stock-position": "stock-position",
	});
	let shellGovernanceInstalled = false;
	let baseReportShell = null;
	let baseExportMenu = null;

	function callMethod(method, args = {}) {
		return new Promise((resolve, reject) => {
			frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: (error) => reject(error) });
		});
	}
	function csrfToken() { return frappe?.csrf_token || frappe?.boot?.csrf_token || ""; }
	function filenameFromDisposition(disposition, fallback) {
		const value = String(disposition || "");
		const utfMatch = value.match(/filename\*=UTF-8''([^;]+)/i);
		if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1]);
		const plainMatch = value.match(/filename="?([^";]+)"?/i);
		return plainMatch?.[1] || fallback;
	}
	function activeReportKey() { const path = String(window.location?.pathname || "").replace(/\/$/, ""); return SHELL_REPORT_ROUTES[path] || ""; }
	function reportParentFilters(component) {
		const parent = component?.$parent;
		if (typeof parent?.providerFilters === "function") return parent.providerFilters() || {};
		const filters = { ...(parent?.filters || {}) }; delete filters.page_size; return filters;
	}
	function reportParentPageState(component) {
		const parent = component?.$parent; const pageLength = Math.max(1, Number(parent?.filters?.page_size || 50)); const page = Math.max(1, Number(parent?.currentPage || parent?.pagination?.page || 1));
		return { pageLength, start: Math.max(0, (page - 1) * pageLength) };
	}
	function reportActionError(error, fallback) {
		const message = error?.message || error?.exc || error?.exception || fallback;
		if (frappe?.msgprint) frappe.msgprint({ title: __("Reporting Action Failed"), message, indicator: "red" });
		return message;
	}
	async function getCapabilities(reportKey, company = "", branch = "") {
		return callMethod("retailedge.reporting_capabilities.get_shell_capabilities", { report_key: reportKey, scope_type: "report", company, branch });
	}
	async function exportReport({ reportKey, filters = {}, options = {}, start = 0, pageLength = 50 } = {}) {
		const format = String(options.format || "xlsx").toLowerCase();
		const body = new URLSearchParams({ report_key: reportKey, filters: JSON.stringify(filters || {}), options: JSON.stringify(options || {}), start: String(Math.max(0, Number(start || 0))), page_length: String(Math.max(1, Number(pageLength || 50))) });
		const response = await fetch("/api/method/retailedge.reporting_files.download_report", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Frappe-CSRF-Token": csrfToken() }, credentials: "same-origin", body: body.toString() });
		if (!response.ok) {
			let message = `Report export failed (${response.status}).`;
			try { const payload = await response.json(); message = payload?.exception || payload?.message || payload?._server_messages || message; } catch (_error) { /* Keep HTTP error. */ }
			throw new Error(message);
		}
		const bytes = new Uint8Array(await response.arrayBuffer()); const mime = response.headers.get("content-type") || ""; const filename = filenameFromDisposition(response.headers.get("content-disposition"), `RetailEdge-${reportKey}.${format}`);
		const exportRuntime = window.EdgeSuiteReportExport || window.EdgeSuiteUI?.reportExport;
		if (!exportRuntime?.downloadVerified) throw new Error("The EdgeSuite verified-download runtime is unavailable.");
		exportRuntime.downloadVerified({ bytes, format, mime, filename }, window); return true;
	}
	async function printReport({ reportKey, filters = {} } = {}) {
		const result = await callMethod("retailedge.reporting_files.get_report_print_html", { report_key: reportKey, filters });
		if (!result?.html) throw new Error("The report print view is empty.");
		const popup = window.open("", "_blank"); if (!popup) throw new Error("The browser blocked the report print window.");
		try { popup.opener = null; } catch (_error) { /* Best-effort isolation. */ }
		popup.document.open(); popup.document.write(result.html); popup.document.close(); popup.document.title = result.title || "RetailEdge Report";
		window.setTimeout(() => { popup.focus(); popup.print(); }, 120); return true;
	}
	function installShellGovernance(runtime = window.EdgeSuiteUI) {
		if (shellGovernanceInstalled || !runtime?.registerComponent || !runtime?.Vue?.defineComponent) return false;
		baseReportShell = runtime.getComponent?.("EdgeReportShell") || runtime.components?.EdgeReportShell;
		baseExportMenu = runtime.getComponent?.("EdgeExportMenu") || runtime.components?.EdgeExportMenu;
		if (!baseReportShell || !baseExportMenu) return false;
		const { defineComponent, h } = runtime.Vue;
		const GovernedReportShell = defineComponent({
			name: "RetailEdgeGovernedReportShell", inheritAttrs: false,
			data() { return { capabilities: { can_view: true, can_print: false, can_export: false }, exportBusy: false, printBusy: false }; },
			mounted() { this.refreshCapabilities(); },
			methods: {
				async refreshCapabilities() { const reportKey = activeReportKey(); if (!reportKey) return; try { this.capabilities = await getCapabilities(reportKey); } catch (error) { this.capabilities = { can_view: true, can_print: false, can_export: false }; console.warn("RetailEdge report capabilities unavailable", error); } },
				async handleExport(options) { const reportKey = activeReportKey(); if (!reportKey || !this.capabilities.can_export) return; const { start, pageLength } = reportParentPageState(this); this.exportBusy = true; try { await exportReport({ reportKey, filters: reportParentFilters(this), options, start, pageLength }); } catch (error) { reportActionError(error, "The report could not be exported."); } finally { this.exportBusy = false; } },
				async handlePrint() { const reportKey = activeReportKey(); if (!reportKey || !this.capabilities.can_print) return; this.printBusy = true; try { await printReport({ reportKey, filters: reportParentFilters(this) }); } catch (error) { reportActionError(error, "The report print view could not be prepared."); } finally { this.printBusy = false; } },
			},
			render() {
				const reportKey = activeReportKey(); if (!reportKey) return h(baseReportShell, this.$attrs, this.$slots); const rows = Array.isArray(this.$attrs.rows) ? this.$attrs.rows : [];
				return h(baseReportShell, { ...this.$attrs, exportEnabled: Boolean(rows.length && this.capabilities.can_export), printEnabled: Boolean(rows.length && this.capabilities.can_print), exportBusy: this.exportBusy, printBusy: this.printBusy, exportInitialOptions: { scope: "all_filtered", include_summary: true, include_filters: true, include_charts: false, include_letterhead: false, include_title: true, include_generated_metadata: true, include_totals: false }, onExport: this.handleExport, onPrint: this.handlePrint }, this.$slots);
			},
		});
		const GovernedLegacyExportMenu = defineComponent({ name: "RetailEdgeGovernedLegacyExportMenu", inheritAttrs: false, render() { if (activeReportKey()) return null; return h(baseExportMenu, this.$attrs, this.$slots); } });
		runtime.registerComponent("EdgeReportShell", GovernedReportShell, { replace: true }); runtime.registerComponent("EdgeExportMenu", GovernedLegacyExportMenu, { replace: true }); shellGovernanceInstalled = true; return true;
	}
	const api = Object.freeze({ getCapabilities, exportReport, printReport, installShellGovernance }); window.RetailEdgeReportingActions = api;
	installShellGovernance(window.EdgeSuiteUI); window.addEventListener("edgesuite:report-runtime-ready", () => installShellGovernance(window.EdgeSuiteUI));
})();
