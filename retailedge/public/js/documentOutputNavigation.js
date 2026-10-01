export function openDocumentOutputSharing(documentKey, documentName) {
	const key = String(documentKey || "").trim();
	const name = String(documentName || "").trim();
	if (!key || !name || typeof window === "undefined" || typeof frappe === "undefined" || typeof frappe.set_route !== "function") return false;

	const shared = window.retailedge?.openDocumentOutputSharing;
	if (typeof shared === "function") {
		const result = shared(key, name);
		if (result !== false) return true;
	}

	window.retailedgeDocumentOutputTarget = {
		document: key,
		name,
		mode: "share",
	};
	frappe.set_route("document-output-sharing");
	return true;
}
