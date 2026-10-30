const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD;
const CASHIER = "browser-cashier@example.com";

if (!PASSWORD) {
	throw new Error("RETAILEDGE_BROWSER_PASSWORD is required for cashier sidebar acceptance.");
}

async function login(context) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: CASHIER, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${CASHIER}`).toBeTruthy();
}

async function openRoute(page, route) {
	await page.goto(`${BASE_URL}/app/${route}`, { waitUntil: "domcontentloaded", timeout: 30_000 });
	await page.locator(".edge-app-shell").first().waitFor({ state: "visible", timeout: 25_000 });
	await expect(page.locator(".modal:visible")).toHaveCount(0);
}

async function finalNavigation(context) {
	const response = await context.request.get(
		`${BASE_URL}/api/method/retailedge.navigation_consolidation.get_retailedge_business_hub_context`
	);
	const text = await response.text();
	expect(response.ok(), text).toBeTruthy();
	return JSON.parse(text).message || {};
}

function targets(data) {
	return (data.navigation_groups || []).flatMap((group) => group.items || []).map((item) => item.target);
}

test("cashier sidebar keeps Professional Selling across My Work and selling routes", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		const navigation = await finalNavigation(context);
		expect(targets(navigation)).toContain("professional-selling");

		await openRoute(page, "cashier-my-work");
		await expect(page.locator(".edge-app-shell").getByText("Professional Selling", { exact: true })).toHaveCount(1);

		await openRoute(page, "professional-selling");
		for (const label of ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"]) {
			await expect(page.getByRole("heading", { name: label, exact: true }).first()).toBeVisible();
		}

		await openRoute(page, "cashier-my-work");
		await expect(page.locator(".edge-app-shell").getByText("Professional Selling", { exact: true })).toHaveCount(1);
	} finally {
		await context.close();
	}
});
