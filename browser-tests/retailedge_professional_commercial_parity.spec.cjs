const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD;
const USER = "browser-sales@example.com";
const COMPANY = "RetailEdge Upgrade CI";
const BRANCH = "RetailEdge RC3 Lagos";
const CUSTOMER = "RetailEdge Upgrade Customer";
const ITEM = "RE-UPGRADE-SERVICE";

if (!PASSWORD) {
	throw new Error("RETAILEDGE_BROWSER_PASSWORD is required for Professional Selling commercial parity acceptance.");
}

async function login(context) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: USER, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${USER}`).toBeTruthy();
}

async function apiGet(context, method, params = {}) {
	const query = new URLSearchParams(params).toString();
	const response = await context.request.get(
		`${BASE_URL}/api/method/${method}${query ? `?${query}` : ""}`
	);
	const text = await response.text();
	expect(response.ok(), `${method} failed: ${text}`).toBeTruthy();
	return JSON.parse(text).message;
}

async function apiPost(context, page, method, form = {}) {
	const csrf = await page.evaluate(() => window.frappe?.csrf_token || "");
	expect(csrf, `CSRF token unavailable before ${method}`).toBeTruthy();
	const response = await context.request.post(`${BASE_URL}/api/method/${method}`, {
		headers: { "X-Frappe-CSRF-Token": csrf },
		form,
	});
	const text = await response.text();
	expect(response.ok(), `${method} failed: ${text}`).toBeTruthy();
	return JSON.parse(text).message;
}

function previewValues(context, documentType) {
	const today = context.today;
	return {
		company: COMPANY,
		branch: BRANCH,
		warehouse: context.operating?.default_stock_location || "",
		customer: CUSTOMER,
		price_list: context.pricing?.price_list || "",
		transaction_date: today,
		delivery_date: documentType === "Sales Order" ? today : undefined,
		items: [{ item_code: ITEM, qty: 2, rate: 1000 }],
		additional_discount_percentage: 5,
		discount_amount: 0,
		apply_discount_on: "Grand Total",
	};
}

test("Quotation and standalone Sales Order share governed commercial preview and UI", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();

	try {
		await page.goto(`${BASE_URL}/app/professional-selling`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.getByRole("heading", { name: "Professional Selling", exact: true }).first().waitFor({
			state: "visible",
			timeout: 25_000,
		});
		await page.waitForFunction(() => Boolean(window.frappe?.csrf_token), null, { timeout: 20_000 });

		const selling = await apiGet(context, "retailedge.professional_selling.get_professional_selling_context");
		expect(selling.operating.company).toBe(COMPANY);
		expect(selling.operating.branch).toBe(BRANCH);
		expect(selling.today).toBeTruthy();

		for (const documentType of ["Quotation", "Sales Order"]) {
			const preview = await apiPost(
				context,
				page,
				"retailedge.sales_document_commercial_preview.get_sales_document_commercial_preview",
				{
					document_type: documentType,
					values: JSON.stringify(previewValues(selling, documentType)),
				}
			);
			expect(preview.doctype).toBe(documentType);
			expect(preview.document_label).toBe(documentType);
			expect(Number(preview.document_total)).toBeGreaterThan(0);
			expect(Number(preview.invoice_adjustment_amount || 0)).toBeGreaterThan(0);
			expect(preview.invoice_adjustment_kind).toBe("discount");
			expect(preview.commercial_term_capabilities?.can_edit_additional_discount).toBeTruthy();
		}

		await page.getByRole("button", { name: "Guided Quotation", exact: true }).click();
		await expect(page.getByText("Quotation discount & tax", { exact: true })).toBeVisible();
		await expect(page.getByText("Quotation summary", { exact: true })).toBeVisible();
		await page.getByRole("button", { name: "Cancel", exact: true }).click();
		await expect(page.getByText("Quotation discount & tax", { exact: true })).toHaveCount(0);

		await page.getByRole("button", { name: "Guided Sales Order", exact: true }).click();
		await expect(page.getByText("Sales Order discount & tax", { exact: true })).toBeVisible();
		await expect(page.getByText("Sales Order summary", { exact: true })).toBeVisible();

		await page.getByRole("button", { name: "From Submitted Quotation", exact: true }).click();
		await expect(page.getByText("Submitted Quotation", { exact: true }).first()).toBeVisible();
		await expect(page.getByText("Sales Order discount & tax", { exact: true })).toHaveCount(0);
	} finally {
		await context.close();
	}
});
