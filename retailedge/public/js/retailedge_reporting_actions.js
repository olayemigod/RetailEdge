(() => {
	"use strict";

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

	async function getCapabilities(reportKey, company = "", branch = "") {
		return callMethod("retailedge.reporting_capabilities.get_shell_capabilities", {
			report_key: reportKey,
			scope_type: "report",
			company,
			branch,
		});
	}

	async function exportReport({ reportKey, filters = {}, options = {}, start = 0, pageLength = 50 } = {}) {
		const format = String(options.format || "xlsx").toLowerCase();
		const body = new URLSearchParams({
			report_key: reportKey,
			filters: JSON.stringify(filters || {}),
			options: JSON.stringify(options || {}),
			start: String(Math.max(0, Number(start || 0))),
			page_length: String(Math.max(1, Number(pageLength || 50))),
		});
		const response = await fetch("/api/method/retailedge.reporting_files.download_report", {
			method: "POST",
			headers: {
				"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
				"X-Frappe-CSRF-Token": csrfToken(),
			},
			credentials: "same-origin",
			body: body.toString(),
		});
		if (!response.ok) {
			let message = `Report export failed (${response.status}).`;
			try {
				const payload = await response.json();
				message = payload?.exception || payload?.message || payload?._server_messages || message;
			} catch (_error) {
				// Keep the HTTP error when the response is not JSON.
			}
			throw new Error(message);
		}
		const bytes = new Uint8Array(await response.arrayBuffer());
		const mime = response.headers.get("content-type") || "";
		const filename = filenameFromDisposition(
			response.headers.get("content-disposition"),
			`RetailEdge-${reportKey}.${format}`,
		);
		const exportRuntime = window.EdgeSuiteReportExport || window.EdgeSuiteUI?.reportExport;
		if (!exportRuntime?.downloadVerified) {
			throw new Error("The EdgeSuite verified-download runtime is unavailable.");
		}
		exportRuntime.downloadVerified({ bytes, format, mime, filename }, window);
		return true;
	}

	async function printReport({ reportKey, filters = {} } = {}) {
		const result = await callMethod("retailedge.reporting_files.get_report_print_html", {
			report_key: reportKey,
			filters,
		});
		if (!result?.html) throw new Error("The report print view is empty.");
		const popup = window.open("", "_blank", "noopener,noreferrer");
		if (!popup) throw new Error("The browser blocked the report print window.");
		popup.document.open();
		popup.document.write(result.html);
		popup.document.close();
		popup.document.title = result.title || "RetailEdge Report";
		popup.addEventListener("load", () => {
			popup.focus();
			popup.print();
		}, { once: true });
		return true;
	}

	window.RetailEdgeReportingActions = Object.freeze({
		getCapabilities,
		exportReport,
		printReport,
	});
})();
