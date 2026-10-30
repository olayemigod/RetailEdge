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

async function unpaidSalesInvoices(context) {
	const params = new URLSearchParams({
		document: "sales-invoice",
		status: "Unpaid",
		start: "0",
		page_length: "20",
	});
	const response = await context.request.get(
		`${BASE_URL}/api/method/retailedge.professional_selling.get_professional_selling_list?${params.toString()}`
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

test("cashier can start a constrained receipt from an unpaid Sales Invoice", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		const list = await unpaidSalesInvoices(context);
		const invoice = (list.rows || []).find(
			(row) => Number(row.docstatus || 0) === 1 && Number(row.outstanding_amount || 0) > 0.005 && !Number(row.is_return || 0)
		);
		expect(invoice, "browser fixture should expose a submitted unpaid cashier invoice").toBeTruthy();

		await openRoute(page, "professional-selling");
		const invoiceRow = page.locator(".selling-record-table tbody tr").filter({ hasText: invoice.name }).first();
		await expect(invoiceRow).toBeVisible({ timeout: 20_000 });
		await invoiceRow.locator(".edge-dropdown__trigger").click();
		const receivePayment = page.getByText("Receive Payment", { exact: true }).last();
		await expect(receivePayment).toBeVisible();
		await receivePayment.click();

		await page.getByRole("heading", { name: "Receive Payment", exact: true }).first().waitFor({ state: "visible", timeout: 20_000 });
		await expect(page.getByText(invoice.name, { exact: true }).first()).toBeVisible();
		await expect(page.getByText("Invoice outstanding", { exact: true }).first()).toBeVisible();
		await expect(page.getByRole("button", { name: "Review Payment", exact: true })).toBeVisible();
	} finally {
		await context.close();
	}
});
