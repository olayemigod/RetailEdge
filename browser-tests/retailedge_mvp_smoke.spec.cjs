const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD || "RetailEdgeBrowser1!";

const USERS = {
	manager: "browser-manager@example.com",
	cashier: "browser-cashier@example.com",
	accounts: "browser-accounts@example.com",
	stock: "browser-stock@example.com",
};

async function login(context, user) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: user, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${user}`).toBeTruthy();
	const payload = await response.json();
	expect(String(payload.message || "")).toMatch(/Logged In/i);
}

async function routeDiagnostic(page, route) {
	const body = (await page.locator("body").innerText().catch(() => "")).slice(0, 4000);
	console.error(`ROUTE_DIAGNOSTIC route=/app/${route} url=${page.url()} body=${JSON.stringify(body)}`);
}

async function openProductPage(page, route, title, menuLabel) {
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
		await page.goto(`${BASE_URL}/app/${route}`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.waitForFunction(() => Boolean(window.frappe), null, { timeout: 20_000 }).catch(() => {});

		try {
			await page.getByText(title, { exact: true }).first().waitFor({
				state: "visible",
				timeout: 20_000,
			});
		} catch (error) {
			await routeDiagnostic(page, route);
			throw error;
		}

		if (menuLabel) {
			await expect(page.getByText(menuLabel, { exact: true }).first()).toBeVisible({ timeout: 15_000 });
		}
		await page.waitForTimeout(500);
		expect(runtimeErrors, `runtime/asset errors on /app/${route}`).toEqual([]);
	} finally {
		page.off("pageerror", pageErrorHandler);
		page.off("response", responseHandler);
	}
}

async function newPersona(browser, user, options = {}) {
	const context = await browser.newContext({ baseURL: BASE_URL, ...options });
	await login(context, user);
	const page = await context.newPage();
	return { context, page };
}

test("canonical RetailEdge manager reaches Business Hub and Action Centre", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.manager);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub", "Home");
		await openProductPage(page, "action-center", "Action Centre", "Review & Approvals");
	} finally {
		await context.close().catch(() => {});
	}
});

test("canonical RetailEdge cashier reaches Business Hub but not banking control pages", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.cashier);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub", "Home");

		await page.goto(`${BASE_URL}/app/banking-readiness`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.waitForTimeout(1_000);
		const body = await page.locator("body").innerText();
		const titleVisible = await page
			.getByText("Banking Setup & Readiness", { exact: true })
			.first()
			.isVisible()
			.catch(() => false);
		expect(titleVisible).toBeFalsy();
		expect(body).toMatch(/not permitted|permission|access denied|not allowed/i);
	} finally {
		await context.close().catch(() => {});
	}
});

test("Accounts User reaches Action Centre and both banking EdgeSuite pages with Money sidebar", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.accounts);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub", "Home");
		await openProductPage(page, "action-center", "Action Centre", "Review & Approvals");
		await openProductPage(page, "banking-readiness", "Banking Setup & Readiness", "Money");
		await openProductPage(page, "bank-matching-reconciliation", "Bank Matching & Reconciliation", "Money");
	} finally {
		await context.close().catch(() => {});
	}
});

test("Stock User reaches Business Hub and Stock Position", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.stock);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub", "Home");
		await openProductPage(page, "stock-position", "Stock Position", "Stock");
	} finally {
		await context.close().catch(() => {});
	}
});

test("Business Hub remains usable at narrow mobile width", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.manager, {
		viewport: { width: 390, height: 844 },
	});
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub", "Home");
		const overflow = await page.evaluate(
			() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)
		);
		expect(overflow).toBeLessThanOrEqual(4);
	} finally {
		await context.close().catch(() => {});
	}
});
