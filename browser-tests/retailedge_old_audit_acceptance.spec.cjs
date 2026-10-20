const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD;
const COMPANY = "RetailEdge Upgrade CI";
const CUSTOMER = "RetailEdge Upgrade Customer";

if (!PASSWORD) {
	throw new Error("RETAILEDGE_BROWSER_PASSWORD is required for old-audit acceptance.");
}

const USERS = {
	manager: "browser-manager@example.com",
	cashier: "browser-cashier@example.com",
	accounts: "browser-accounts@example.com",
	purchasing: "browser-purchasing@example.com",
	sales: "browser-sales@example.com",
};

async function login(context, user) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: user, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${user}`).toBeTruthy();
}

async function newPersona(browser, user) {
	const context = await browser.newContext({ baseURL: BASE_URL });
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
		await page.getByRole("heading", { name: title, exact: true }).first().waitFor({
			state: "visible",
			timeout: 25_000,
		});
		await page.waitForTimeout(300);
		await expect(page.locator(".modal:visible")).toHaveCount(0);
		expect(runtimeErrors, `runtime/asset errors on /app/${route}`).toEqual([]);
	} finally {
		page.off("pageerror", pageErrorHandler);
		page.off("response", responseHandler);
	}
}

async function assertMultiColumnGrid(locator) {
	await expect(locator).toBeVisible();
	const layout = await locator.evaluate((node) => {
		const style = getComputedStyle(node);
		return {
			display: style.display,
			columns: style.gridTemplateColumns.split(/\s+/).filter(Boolean),
		};
	});
	expect(layout.display).toBe("grid");
	expect(layout.columns.length).toBeGreaterThan(1);
}

test("old audit: Accounts User can apply Unmatched Bank Payment filters", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.accounts);
	try {
		await openProductPage(page, "unmatched-bank-payments", "Unmatched Bank Payments");
		const apply = page.getByRole("button", { name: "Apply Filters", exact: true });
		await expect(apply).toBeVisible();
		await expect(page.getByRole("button", { name: "Refresh", exact: true })).toHaveCount(0);
		await apply.click();
		await expect(page.getByRole("button", { name: "Apply Filters", exact: true })).toBeVisible();
	} finally {
		await context.close();
	}
});

test("old audit: Sales User Customer 360 completes real API aggregation without SQL failure", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.sales);
	try {
		await openProductPage(page, "customer-360", "Customer 360");
		await assertMultiColumnGrid(page.locator(".customer-360-filter-grid").first());

		const response = await context.request.get(
			`${BASE_URL}/api/method/retailedge.customer_360.get_customer_360`,
			{
				params: {
					filters: JSON.stringify({
						company: COMPANY,
						customer: CUSTOMER,
						from_date: "2026-01-01",
						to_date: "2026-12-31",
					}),
				},
			}
		);
		const text = await response.text();
		expect(response.ok(), text).toBeTruthy();
		const payload = JSON.parse(text);
		expect(payload.message?.title).toBe("Customer 360");
		expect(payload.message?.customer?.name).toBe(CUSTOMER);
		expect(payload.message?.scope?.company).toBe(COMPANY);
		expect(payload.message?.scope?.customer).toBe(CUSTOMER);
	} finally {
		await context.close();
	}
});

test("old audit: customer intelligence filters remain horizontal on desktop", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.sales);
	try {
		await openProductPage(page, "customer-sales-intelligence", "Customer & Sales Intelligence");
		await assertMultiColumnGrid(page.locator(".customer-intelligence-filter-grid").first());

		await openProductPage(page, "customer-opportunity-intelligence", "Customer Retention & Opportunity Intelligence");
		await assertMultiColumnGrid(page.locator(".customer-opportunity-filter-grid").first());
	} finally {
		await context.close();
	}
});

test("old audit: Purchase User can open Supplier Document Review", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.purchasing);
	try {
		await openProductPage(page, "supplier-document-review", "Supplier Document Review");
	} finally {
		await context.close();
	}
});

test("old audit: Cashier remains denied Supplier Document Review", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.cashier);
	try {
		await page.goto(`${BASE_URL}/app/supplier-document-review`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.waitForTimeout(1_000);
		const titleVisible = await page
			.getByRole("heading", { name: "Supplier Document Review", exact: true })
			.first()
			.isVisible()
			.catch(() => false);
		expect(titleVisible).toBeFalsy();
		const body = await page.locator("body").innerText();
		expect(body).toMatch(/not permitted|permission|access denied|not allowed/i);
	} finally {
		await context.close();
	}
});

test("old audit: Sales Forecast opens Forecasting & Planning in the same tab with governed guidance", async ({ browser }) => {
	const { context, page } = await newPersona(browser, USERS.manager);
	try {
		await openProductPage(page, "retailedge-sales-forecast", "Sales Forecast");
		const originalPageCount = context.pages().length;
		await page.getByRole("button", { name: "Planning Workspace", exact: true }).click();
		await page.getByRole("heading", { name: "Forecasting & Planning", exact: true }).first().waitFor({
			state: "visible",
			timeout: 25_000,
		});
		await expect(page).toHaveURL(/\/app\/forecasting-planning(?:$|[?#])/);
		expect(context.pages().length).toBe(originalPageCount);
		await expect(page.getByText(/Posted accounting and stock records remain the source of truth/i)).toBeVisible();
		await expect(page.getByText(/Forecast and Plan are analytical only and do not create transactions/i)).toBeVisible();
	} finally {
		await context.close();
	}
});
