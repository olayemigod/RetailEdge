const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD || "RetailEdgeBrowser1!";
const MANAGER = "browser-manager@example.com";

async function login(context) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: MANAGER, pwd: PASSWORD },
	});
	expect(response.ok(), "manager login failed").toBeTruthy();
}

async function openHub(page) {
	await page.goto(`${BASE_URL}/app/retailedge-business-hub`, {
		waitUntil: "domcontentloaded",
		timeout: 30_000,
	});
	await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
		state: "visible",
		timeout: 20_000,
	});
	await expect(page.locator(".home-intelligence-card")).toHaveCount(8);
}

async function captureRoute(page, clicker) {
	await page.evaluate(() => {
		window.__businessHubQaRoute = null;
		window.__businessHubQaOriginalSetRoute = frappe.set_route;
		frappe.set_route = (...args) => {
			window.__businessHubQaRoute = args;
		};
	});
	try {
		await clicker();
		return await page.evaluate(() => ({
			route: window.__businessHubQaRoute,
			handoff: window.__retailedgeBusinessHubRouteHandoff || null,
		}));
	} finally {
		await page.evaluate(() => {
			if (window.__businessHubQaOriginalSetRoute) {
				frappe.set_route = window.__businessHubQaOriginalSetRoute;
			}
			delete window.__businessHubQaOriginalSetRoute;
		});
	}
}

test("Business Hub QA regression: Receive Stock keeps Company and Branch context", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const result = await captureRoute(page, () =>
			page.getByRole("button", { name: /Receive Stock/i }).click()
		);
		expect(result.route).toEqual(["professional-purchasing"]);
		expect(result.handoff?.target).toBe("professional-purchasing");
		expect(result.handoff?.filters?.company).toBeTruthy();
		expect(result.handoff?.filters?.branch).toBeTruthy();
		expect(result.handoff?.filters?.from_date).toBeUndefined();
		expect(result.handoff?.filters?.to_date).toBeUndefined();
	} finally {
		await context.close();
	}
});

test("Business Hub QA regression: Bank Matching shortcut keeps Hub period and scope", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const result = await captureRoute(page, () =>
			page.getByRole("button", { name: /Match Bank Transactions/i }).click()
		);
		expect(result.route).toEqual(["bank-matching-reconciliation"]);
		expect(result.handoff?.target).toBe("bank-matching-reconciliation");
		expect(result.handoff?.filters?.company).toBeTruthy();
		expect(result.handoff?.filters?.branch).toBeTruthy();
		expect(result.handoff?.filters?.from_date).toBeTruthy();
		expect(result.handoff?.filters?.to_date).toBeTruthy();
	} finally {
		await context.close();
	}
});

test("Business Hub QA regression: Sales index action carries selected period and scope", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const salesCard = page.locator(".home-intelligence-card").filter({
			has: page.getByRole("heading", { name: "Sales", exact: true }),
		});
		const result = await captureRoute(page, () =>
			salesCard.getByRole("button", { name: "Review Sales", exact: true }).click()
		);
		expect(result.route).toEqual(["sales-invoice-register"]);
		expect(result.handoff?.target).toBe("sales-invoice-register");
		expect(result.handoff?.filters?.company).toBeTruthy();
		expect(result.handoff?.filters?.branch).toBeTruthy();
		expect(result.handoff?.filters?.from_date).toBeTruthy();
		expect(result.handoff?.filters?.to_date).toBeTruthy();
	} finally {
		await context.close();
	}
});


test("Business Hub QA regression: Make Sale stays guided and keeps Update Stock controlled", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		await page.getByRole("button", { name: /Make Sale/i }).click();
		await expect(page.locator(".guided-invoice-form")).toBeVisible();
		const updateStock = page.locator('.guided-check-field input[type="checkbox"]').first();
		await expect(updateStock).toBeChecked();
		await expect(updateStock).toBeDisabled();
	} finally {
		await context.close();
	}
});

test("Business Hub QA regression: Record Purchase and Transfer Stock open guided forms", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		await page.getByRole("button", { name: /Record Purchase/i }).click();
		await expect(page.locator(".guided-purchase-form")).toBeVisible();
		await page.getByRole("button", { name: "Cancel", exact: true }).last().click();
		await page.getByRole("button", { name: /Transfer Stock/i }).click();
		await expect(page.locator(".guided-stock-form")).toBeVisible();
	} finally {
		await context.close();
	}
});

test("Business Hub QA regression: manager Record Expense stays in EdgeSuite Business Expenses", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		await page.getByRole("button", { name: /Record Expense/i }).click();
		await page.getByRole("heading", { name: "Business Expenses", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		await expect(page.getByRole("heading", { name: "New Business Expense", exact: true })).toBeVisible();
		await expect(page.locator(".edge-app-shell").first()).toBeAttached();
	} finally {
		await context.close();
	}
});
