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

function csrfToken() {
	return frappe?.csrf_token || frappe?.boot?.csrf_token || "";
}

function filenameFromDisposition(disposition, fallback) {
	const value = String(disposition || "");
	const utfMatch = value.match(/filename\*=UTF-8''([^;]+)/i);
	if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1]);
	const plainMatch = value.match(/filename="?([^";]+)"?/i);
	return plainMatch?.[1] || fallback;
}

export async function getDashboardCapabilities(scopeKey, filters = {}) {
	return callMethod("retailedge.dashboard_capabilities.get_dashboard_shell_capabilities", {
		scope_key: scopeKey,
		company: filters.company || "",
		branch: filters.branch || "",
	});
}

export async function exportDashboard(scopeKey, filters = {}, options = {}) {
	const format = String(options.format || "xlsx").toLowerCase();
	const body = new URLSearchParams({
		scope_key: scopeKey,
		filters: JSON.stringify(filters || {}),
		options: JSON.stringify(options || {}),
	});
	const response = await fetch("/api/method/retailedge.dashboard_files.download_dashboard", {
		method: "POST",
		headers: {
			"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
			"X-Frappe-CSRF-Token": csrfToken(),
		},
		credentials: "same-origin",
		body: body.toString(),
	});
	if (!response.ok) throw new Error(`Dashboard export failed (${response.status}).`);
	const bytes = new Uint8Array(await response.arrayBuffer());
	const mime = response.headers.get("content-type") || "";
	const filename = filenameFromDisposition(
		response.headers.get("content-disposition"),
		`RetailEdge-${scopeKey}.${format}`,
	);
	const exportRuntime = window.EdgeSuiteReportExport || window.EdgeSuiteUI?.reportExport;
	if (!exportRuntime?.downloadVerified) throw new Error("The EdgeSuite verified-download runtime is unavailable.");
	exportRuntime.downloadVerified({ bytes, format, mime, filename }, window);
	return true;
}

export async function printDashboard(scopeKey, filters = {}) {
	const result = await callMethod("retailedge.dashboard_files.get_dashboard_print_html", {
		scope_key: scopeKey,
		filters,
	});
	if (!result?.html) throw new Error("The dashboard print view is empty.");
	const popup = window.open("", "_blank");
	if (!popup) throw new Error("The browser blocked the dashboard print window.");
	try { popup.opener = null; } catch (_error) { /* Best-effort isolation. */ }
	popup.document.open();
	popup.document.write(result.html);
	popup.document.close();
	popup.document.title = result.title || "RetailEdge Dashboard";
	window.setTimeout(() => { popup.focus(); popup.print(); }, 120);
	return true;
}

export function defaultDashboardExportOptions() {
	return {
		format: "xlsx",
		scope: "all_filtered",
		columns: [],
		include_summary: true,
		include_filters: true,
		include_charts: false,
		include_letterhead: false,
		include_title: true,
		include_generated_metadata: true,
		include_totals: false,
		orientation: "landscape",
		repeat_table_headings: true,
	};
}
