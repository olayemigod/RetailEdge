const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD;
const COMPANY = "RetailEdge Upgrade CI";
const LAGOS = "RetailEdge RC3 Lagos";
const IKEJA = "RetailEdge RC3 Ikeja";

if (!PASSWORD) {
	throw new Error("RETAILEDGE_BROWSER_PASSWORD is required for RC3 acceptance.");
}

const USERS = {
	manager: "browser-manager@example.com",
	branchManager: "browser-branch-manager@example.com",
	cashier: "browser-cashier@example.com",
	accounts: "browser-accounts@example.com",
	stock: "browser-stock@example.com",
	purchasing: "browser-purchasing@example.com",
	sales: "browser-sales@example.com",
	oneBranch: "browser-one-branch@example.com",
	multiBranch: "browser-multi-branch@example.com",
	zeroBranch: "browser-zero-branch@example.com",
	nativeAdvanced: "browser-native@example.com",
};

async function login(context, user) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: user, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${user}`).toBeTruthy();
}

async function newPersona(browser, user, options = {}) {
	const context = await browser.newContext({ baseURL: BASE_URL, ...options });
	await login(context, user);
	const page = await context.newPage();
	return { context, page };
}

async function openProductPage(page, route, title) {
	const runtimeErrors = [];
	const pageErrorHandler = (error) => runtimeErrors.push(`pageerror: ${error.message}`);
	const responseHandler = (response) => {
		const type = response.request().resourceType();
		if (["script", "stylesheet"].includes(type) && response.status() >= 400) {
			runtimeErrors.push(`${response.status()} ${type}: ${response.url()}`);
		}
	};
	page.on("pageerror", pageErrorHandler);
	page.on("response", responseHandler);
	try {
		await page.goto(`${BASE_URL}/app/${route}`, { waitUntil: "domcontentloaded", timeout: 30_000 });
		await page.getByText(title, { exact: true }).first().waitFor({ state: "visible", timeout: 25_000 });
		await page.waitForTimeout(300);
		expect(runtimeErrors, `runtime/asset errors on /app/${route}`).toEqual([]);
	} finally {
		page.off("pageerror", pageErrorHandler);
		page.off("response", responseHandler);
	}
}

async function apiGet(context, method, params = {}) {
	const query = new URLSearchParams(params).toString();
	const response = await context.request.get(
		`${BASE_URL}/api/method/${method}${query ? `?${query}` : ""}`
	);
	const text = await response.text();
	let payload = {};
	try {
		payload = JSON.parse(text);
	} catch (_error) {
		// Keep the raw payload for diagnostics below.
	}
	return { response, payload, text };
}

test("RC3 owner/manager reaches the product Home and Action Centre", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.manager);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub");
		await openProductPage(page, "action-center", "Action Centre");
	} finally {
		await context.close();
	}
});

test("RC3 restricted Branch Manager reaches Home, Action Centre and Banking workspace", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.branchManager);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub");
		await openProductPage(page, "action-center", "Action Centre");
		await openProductPage(page, "banking-readiness", "Banking Setup & Readiness");
		await openProductPage(page, "bank-matching-reconciliation", "Bank Matching & Reconciliation");
	} finally {
		await context.close();
	}
});

test("RC3 cashier remains in Home and cannot open Banking Readiness", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.cashier);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub");
		await page.goto(`${BASE_URL}/app/banking-readiness`, { waitUntil: "domcontentloaded", timeout: 30_000 });
		await page.waitForTimeout(1_000);
		const bankingTitleVisible = await page
			.getByText("Banking Setup & Readiness", { exact: true })
			.first()
			.isVisible()
			.catch(() => false);
		expect(bankingTitleVisible).toBeFalsy();
	} finally {
		await context.close();
	}
});

test("RC3 Accounts persona reaches Home, Action Centre and both banking Pages", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.accounts);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub");
		await openProductPage(page, "action-center", "Action Centre");
		await openProductPage(page, "banking-readiness", "Banking Setup & Readiness");
		await openProductPage(page, "bank-matching-reconciliation", "Bank Matching & Reconciliation");
	} finally {
		await context.close();
	}
});

test("RC3 Stock persona reaches Home and Stock Position", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.stock);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub");
		await openProductPage(page, "stock-position", "Stock Position");
	} finally {
		await context.close();
	}
});

test("RC3 Purchasing persona has an EdgeSuite product shell and purchasing workspace", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.purchasing);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub");
		await openProductPage(page, "professional-purchasing", "Professional Purchasing");
		await openProductPage(page, "supplier-payables", "Supplier Payables");
	} finally {
		await context.close();
	}
});

test("RC3 Sales persona has an EdgeSuite product shell and selling workspace", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.sales);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub");
		await openProductPage(page, "professional-selling", "Professional Selling");
		await openProductPage(page, "customer-receivables", "Customer Receivables");
		await openProductPage(page, "payment-management", "Payment Management");
	} finally {
		await context.close();
	}
});

test("RC3 one-Branch authority resolves exactly one permitted Branch", async ({ browser }) => {
	const { context } = await newPersona(browser, USERS.oneBranch);
	try {
		const allowed = await apiGet(context, "retailedge.operating_context.get_allowed_operating_contexts", {
			company: COMPANY,
		});
		expect(allowed.response.ok(), allowed.text).toBeTruthy();
		expect(allowed.payload.message.branches).toEqual([LAGOS]);
		const current = await apiGet(context, "retailedge.operating_context.get_operating_context", {
			company: COMPANY,
		});
		expect(current.response.ok(), current.text).toBeTruthy();
		expect(current.payload.message.branch).toBe(LAGOS);

		const transfer = await apiGet(context, "retailedge.guided_stock_transfer.get_simple_stock_transfer_context", {
			company: COMPANY,
		});
		expect(transfer.response.ok(), transfer.text).toBeTruthy();
		expect(transfer.payload.message.defaults.source_branch).toBe(LAGOS);
		expect(transfer.payload.message.defaults.target_branch).toBe(LAGOS);
	} finally {
		await context.close();
	}
});

test("RC3 multi-Branch authority requires explicit Branch choice for Stock Transfer", async ({ browser }) => {
	const { context } = await newPersona(browser, USERS.multiBranch);
	try {
		const allowed = await apiGet(context, "retailedge.operating_context.get_allowed_operating_contexts", {
			company: COMPANY,
		});
		expect(allowed.response.ok(), allowed.text).toBeTruthy();
		expect(new Set(allowed.payload.message.branches)).toEqual(new Set([IKEJA, LAGOS]));

		const transfer = await apiGet(context, "retailedge.guided_stock_transfer.get_simple_stock_transfer_context", {
			company: COMPANY,
		});
		expect(transfer.response.ok(), transfer.text).toBeTruthy();
		expect(transfer.payload.message.defaults.source_branch).toBe("");
		expect(transfer.payload.message.defaults.target_branch).toBe("");
	} finally {
		await context.close();
	}
});

test("RC3 restricted-zero history fails closed on a guided Stock Transfer", async ({ browser }) => {
	const { context } = await newPersona(browser, USERS.zeroBranch);
	try {
		const current = await apiGet(context, "retailedge.operating_context.get_operating_context", {
			company: COMPANY,
		});
		expect(current.response.ok(), current.text).toBeTruthy();
		expect(current.payload.message.branch).toBe("");
		expect(String(current.payload.message.source || "")).toMatch(/branch assignment/i);

		const transfer = await apiGet(context, "retailedge.guided_stock_transfer.get_simple_stock_transfer_context", {
			company: COMPANY,
		});
		expect(transfer.response.ok()).toBeFalsy();
		expect(transfer.text).toMatch(/not active|PermissionError|not permitted/i);
	} finally {
		await context.close();
	}
});

test("RC3 advanced native persona retains authorised Setup fallback", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.nativeAdvanced);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub");
		await openProductPage(page, "retailedge-setup", "Setup");
	} finally {
		await context.close();
	}
});

test("RC3 representative Home remains usable at narrow width", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.manager, {
		viewport: { width: 390, height: 844 },
	});
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub");
		const overflow = await page.evaluate(
			() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)
		);
		expect(overflow).toBeLessThanOrEqual(4);
	} finally {
		await context.close();
	}
});
