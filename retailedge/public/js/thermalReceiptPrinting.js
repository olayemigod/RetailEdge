const RECEIPT_METHOD = "retailedge.thermal_receipt.get_thermal_receipt_payload";
const RETAILEDGE_PRODUCT_KEY = "retailedge";

function sharedPrintAdapter() {
	const runtime = typeof window !== "undefined" ? window.EdgeSuiteUI : null;
	return runtime?.print || runtime?.getAdapter?.("print") || null;
}

function callReceiptPayload(document, name) {
	return new Promise((resolve, reject) => {
		if (typeof frappe === "undefined" || typeof frappe.call !== "function") {
			reject(new Error("RetailEdge receipt service is unavailable."));
			return;
		}
		frappe.call({
			method: RECEIPT_METHOD,
			args: { document, name },
			type: "GET",
			callback: (response) => resolve(response?.message || {}),
			error: reject,
		});
	});
}

function printerError(code, message, cause = null) {
	const error = new Error(message);
	error.code = code;
	if (cause) error.cause = cause;
	return error;
}

function normalizedContext(context = {}) {
	return {
		purpose: "Receipt",
		productKey: RETAILEDGE_PRODUCT_KEY,
		company: String(context.company || "").trim(),
		branch: String(context.branch || "").trim(),
	};
}

export function retailPrinterSetupUrl(context = {}) {
	const normalized = normalizedContext(context);
	const params = new URLSearchParams({
		purpose: normalized.purpose,
		product_key: normalized.productKey,
	});
	if (normalized.company) params.set("company", normalized.company);
	if (normalized.branch) params.set("branch", normalized.branch);
	return `/app/edge-printing?${params.toString()}`;
}

export function openRetailPrinterSetup(context = {}) {
	const url = retailPrinterSetupUrl(context);
	if (typeof window !== "undefined" && typeof window.location?.assign === "function") {
		window.location.assign(url);
		return true;
	}
	return false;
}

export function isRetailReceiptPrintable(documentOrDetails) {
	const doctype = String(
		typeof documentOrDetails === "string"
			? documentOrDetails
			: documentOrDetails?.doctype || "",
	).trim();
	return ["Sales Invoice", "POS Invoice"].includes(doctype);
}

async function resolveSerialProfile(adapter, context) {
	const profile = await adapter.profiles?.resolve?.(normalizedContext(context));
	if (!profile) {
		throw printerError(
			"RETAIL_PRINTER_PROFILE_REQUIRED",
			"No active receipt printer profile is configured for this company or branch.",
		);
	}
	if (profile.transport !== "serial") {
		throw printerError(
			"RETAIL_DIRECT_PRINTER_REQUIRED",
			"Direct receipt printing requires a Serial / Bluetooth receipt printer profile.",
		);
	}
	return profile;
}

async function ensureConnected(adapter, profile) {
	const current = adapter.getStatus?.("serial");
	if (current?.connected) return current;
	try {
		const restored = await adapter.devices?.connectBoundSerial?.(
			profile.name,
			adapter.profiles.connectionOptions(profile),
		);
		if (!restored?.status?.connected) throw new Error("Printer did not reconnect.");
		return restored.status;
	} catch (error) {
		throw printerError(
			"RETAIL_PRINTER_SETUP_REQUIRED",
			"Connect this device to the receipt printer in Devices & Printing.",
			error,
		);
	}
}

function receiptBlocks(payload, profileOptions, { openDrawer = false } = {}) {
	const blocks = Array.isArray(payload?.blocks) ? payload.blocks.map((block) => ({ ...block })) : [];
	const filtered = profileOptions.printQr ? blocks : blocks.filter((block) => block.type !== "qr");
	if (openDrawer && profileOptions.cashDrawer) {
		filtered.push({ type: "drawer", pin: profileOptions.drawerPin });
	}
	if (profileOptions.feedLines > 0) {
		filtered.push({ type: "feed", lines: profileOptions.feedLines });
	}
	if (profileOptions.autoCut) {
		filtered.push({ type: "cut", mode: profileOptions.cutMode });
	}
	return filtered;
}

export async function printRetailReceipt({
	document,
	name,
	company = "",
	branch = "",
	openDrawer = false,
} = {}) {
	const documentKey = String(document || "").trim();
	const documentName = String(name || "").trim();
	if (!documentKey || !documentName) {
		throw new TypeError("RetailEdge direct receipt printing requires a document and name.");
	}

	const adapter = sharedPrintAdapter();
	if (!adapter?.profiles || !adapter?.devices || typeof adapter.printReceipt !== "function") {
		throw printerError(
			"RETAIL_SHARED_PRINTING_UNAVAILABLE",
			"Shared EdgeSuite receipt printing is not available on this site yet.",
		);
	}

	const payload = await callReceiptPayload(documentKey, documentName);
	const context = {
		company: String(payload?.company || company || "").trim(),
		branch: String(payload?.branch || branch || "").trim(),
	};
	const profile = await resolveSerialProfile(adapter, context);
	await ensureConnected(adapter, profile);
	const options = adapter.profiles.receiptOptions(profile);
	const documentPayload = {
		paper: options.paper,
		charactersPerLine: options.charactersPerLine,
		blocks: receiptBlocks(payload, options, { openDrawer }),
		metadata: {
			...(payload.metadata || {}),
			product: RETAILEDGE_PRODUCT_KEY,
			profile: profile.name,
		},
	};

	const copies = Math.max(1, Number(options.copies || 1));
	const results = [];
	for (let copy = 0; copy < copies; copy += 1) {
		results.push(await adapter.printReceipt(documentPayload));
	}
	return Object.freeze({
		printed: true,
		copies,
		profile,
		payload,
		results,
	});
}

export {
	RECEIPT_METHOD,
	RETAILEDGE_PRODUCT_KEY,
};
