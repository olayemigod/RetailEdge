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

function portInfoMatchesBinding(portInfo = {}, bindingPortInfo = {}) {
	const entries = Object.entries(bindingPortInfo || {}).filter(
		([, value]) => value !== undefined && value !== null && value !== "",
	);
	return entries.length > 0 && entries.every(([key, value]) => portInfo?.[key] === value);
}

function resolvedReceiptTemplate(payload = {}, profileOptions = {}) {
	const paperWidth = String(Number(profileOptions.paper || 80));
	return (
		payload?.template_variants?.[paperWidth]
		|| payload?.template_family
		|| "PEdge Sales Receipt"
	);
}

function directProfileTransport(profile) {
	const transport = String(profile?.transport || "").trim().toLowerCase();
	if (!["serial", "usb"].includes(transport)) {
		throw printerError(
			"RETAIL_DIRECT_PRINTER_REQUIRED",
			"Direct receipt printing requires a Serial / Bluetooth or USB receipt printer profile.",
		);
	}
	return transport;
}

function activeTransport(adapter, profile) {
	if (adapter.simulation?.isEnabled?.()) return "serial";
	return directProfileTransport(profile);
}

export function retailPrinterSetupUrl() {
	return "/app/edge-printing";
}

export function openRetailPrinterSetup() {
	if (typeof frappe !== "undefined" && typeof frappe.set_route === "function") {
		frappe.set_route("edge-printing");
		return true;
	}
	if (typeof window !== "undefined" && typeof window.location?.assign === "function") {
		window.location.assign(retailPrinterSetupUrl());
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

async function resolveDirectProfile(adapter, context) {
	const profile = await adapter.profiles?.resolve?.(normalizedContext(context));
	if (!profile) {
		throw printerError(
			"RETAIL_PRINTER_PROFILE_REQUIRED",
			"No active receipt printer profile is configured for this company or branch.",
		);
	}
	directProfileTransport(profile);
	return profile;
}

async function ensureConnected(adapter, profile) {
	const transport = activeTransport(adapter, profile);
	const current = adapter.getStatus?.(transport);
	if (adapter.simulation?.isEnabled?.() && transport === "serial" && current?.connected) {
		return { transport, status: current };
	}

	try {
		const binding = adapter.bindingStore?.get?.(profile.name);
		const sharedMatch = adapter.devices?.bindingMatchesStatus?.(profile.name, current || {});
		const legacySerialMatch = Boolean(
			transport === "serial"
			&& current?.connected
			&& binding?.transport === "serial"
			&& portInfoMatchesBinding(current.portInfo || {}, binding.portInfo || {}),
		);
		const currentMatchesBinding = Boolean(current?.connected && (sharedMatch || legacySerialMatch));

		if (currentMatchesBinding) return { transport, status: current };

		if (current?.connected) {
			if (typeof adapter.disconnect !== "function") {
				throw new Error("Shared print runtime cannot switch the connected printer safely.");
			}
			await adapter.disconnect(transport);
		}

		const connectBound = transport === "usb"
			? adapter.devices?.connectBoundUsb
			: adapter.devices?.connectBoundSerial;
		if (typeof connectBound !== "function") {
			throw new Error(`Shared print runtime does not support ${transport.toUpperCase()} printer bindings.`);
		}
		const restored = await connectBound.call(
			adapter.devices,
			profile.name,
			adapter.profiles.connectionOptions(profile),
		);
		if (!restored?.status?.connected) throw new Error("Printer did not reconnect.");
		return { transport, status: restored.status };
	} catch (error) {
		const suffix = transport === "usb"
			? " If direct USB access is unavailable, use Print Document for normal system printing."
			: "";
		throw printerError(
			"RETAIL_PRINTER_SETUP_REQUIRED",
			`Connect this device to the receipt printer in Devices & Printing.${suffix}`,
			error,
		);
	}
}

function receiptBlocks(payload, profileOptions, { openDrawer = false } = {}) {
	const paperWidth = String(Number(profileOptions.paper || 80));
	const paperBlocks = payload?.blocks_by_paper?.[paperWidth];
	const source = Array.isArray(paperBlocks)
		? paperBlocks
		: Array.isArray(payload?.blocks)
			? payload.blocks
			: [];
	const blocks = source.map((block) => ({ ...block }));
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
	const profile = await resolveDirectProfile(adapter, context);
	const connection = await ensureConnected(adapter, profile);
	const options = adapter.profiles.receiptOptions(profile);
	const template = resolvedReceiptTemplate(payload, options);
	const documentPayload = {
		paper: options.paper,
		charactersPerLine: options.charactersPerLine,
		blocks: receiptBlocks(payload, options, { openDrawer }),
		metadata: {
			...(payload.metadata || {}),
			product: RETAILEDGE_PRODUCT_KEY,
			profile: profile.name,
			template,
			paper_width: options.paper,
		},
	};

	const copies = Math.max(1, Number(options.copies || 1));
	const results = [];
	const encodeText = adapter.profiles.textEncoder(profile);
	for (let copy = 0; copy < copies; copy += 1) {
		results.push(await adapter.printReceipt(documentPayload, {
			transport: connection.transport,
			encodeText,
		}));
	}
	return Object.freeze({
		printed: true,
		copies,
		profile,
		transport: connection.transport,
		template,
		payload,
		results,
	});
}

export {
	RECEIPT_METHOD,
	RETAILEDGE_PRODUCT_KEY,
};
