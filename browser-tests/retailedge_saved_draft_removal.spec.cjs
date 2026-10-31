const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD;
const USER = "browser-sales@example.com";
const COMPANY = "RetailEdge Upgrade CI";
const BRANCH = "RetailEdge RC3 Lagos";
const CUSTOMER = "RetailEdge Upgrade Customer";
const ITEM = "RE-UPGRADE-SERVICE";
const SECOND_ITEM = "RE-UPGRADE-SERVICE-SECOND";

if (!PASSWORD) {
	throw new Error("RETAILEDGE_BROWSER_PASSWORD is required for saved-draft removal acceptance.");
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

function moneyValue(text) {
	return Number(String(text || "").replace(/[^0-9.-]/g, ""));
}

test("Make Sale persists removed saved-draft row and recalculated total after reopening", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();

	try {
		await page.goto(`${BASE_URL}/app/retailedge-business-hub`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.waitForFunction(() => Boolean(window.frappe?.csrf_token), null, { timeout: 20_000 });

		const formContext = await apiGet(
			context,
			"retailedge.guided_sales_invoice.get_simple_sales_invoice_context"
		);
		expect(formContext.defaults.company).toBe(COMPANY);
		expect(formContext.defaults.branch).toBe(BRANCH);
		expect(formContext.defaults.warehouse).toBeTruthy();

		const draft = await apiPost(
			context,
			page,
			"retailedge.guided_sales_invoice.create_simple_sales_invoice_draft",
			{
				values: JSON.stringify({
					...formContext.defaults,
					customer: CUSTOMER,
					remarks: "Browser acceptance: saved draft row removal",
					items: [
						{ item_code: ITEM, qty: 1, rate: 1000 },
						{ item_code: SECOND_ITEM, qty: 2, rate: 1000 },
					],
				}),
			}
		);
		expect(draft?.name).toBeTruthy();

		const initialPreview = await apiGet(
			context,
			"retailedge.standard_sales_invoice_completion.get_standard_sales_invoice_completion_preview",
			{ name: draft.name }
		);
		expect(initialPreview.item_count).toBe(2);
		expect(initialPreview.editable_items).toHaveLength(2);
		expect(Number(initialPreview.grand_total)).toBeGreaterThan(0);

		await page.evaluate(
			({ key, payload }) => window.sessionStorage.setItem(key, JSON.stringify(payload)),
			{
				key: `retailedge:make-sale:handoff:${encodeURIComponent(USER)}`,
				payload: {
					createdAt: Date.now(),
					document_name: draft.name,
					values: {},
				},
			}
		);

		await page.goto(`${BASE_URL}/app/make-sale`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await expect(page.getByRole("heading", { name: "Make Sale", exact: true })).toBeVisible({ timeout: 25_000 });
		await expect(page.locator(".saved-panel").getByText(draft.name, { exact: true })).toBeVisible({ timeout: 25_000 });

		await page.getByRole("button", { name: "Edit Sale", exact: true }).click();
		const rows = page.locator(".make-sale-form .edge-child-table tbody tr");
		await expect(rows).toHaveCount(2, { timeout: 25_000 });

		const invoiceTotal = page.locator(".make-sale-form .sales-commercial-summary__total strong");
		await expect(invoiceTotal).toBeVisible({ timeout: 25_000 });
		const initialTotalText = (await invoiceTotal.innerText()).trim();
		expect(moneyValue(initialTotalText)).toBeCloseTo(Number(initialPreview.grand_total), 2);

		await rows.first().getByRole("button", { name: "Remove", exact: true }).click();
		await expect(rows).toHaveCount(1);
		await expect(page.locator(".make-sale-form .item-count")).toContainText("1 item");
		await expect
			.poll(async () => (await invoiceTotal.innerText()).trim(), { timeout: 25_000 })
			.not.toBe(initialTotalText);
		const reducedTotalText = (await invoiceTotal.innerText()).trim();
		expect(moneyValue(reducedTotalText)).toBeLessThan(moneyValue(initialTotalText));

		const updateDraft = page.getByRole("button", { name: "Update Draft", exact: true });
		await expect(updateDraft).toBeEnabled({ timeout: 25_000 });
		await updateDraft.click();

		const savedPanel = page.locator(".saved-panel");
		await expect(savedPanel.getByText(draft.name, { exact: true })).toBeVisible({ timeout: 25_000 });
		await expect(savedPanel.getByRole("button", { name: "Edit Sale", exact: true })).toBeVisible();

		const persistedPreview = await apiGet(
			context,
			"retailedge.standard_sales_invoice_completion.get_standard_sales_invoice_completion_preview",
			{ name: draft.name }
		);
		expect(persistedPreview.item_count).toBe(1);
		expect(persistedPreview.editable_items).toHaveLength(1);
		expect(Number(persistedPreview.grand_total)).toBeLessThan(Number(initialPreview.grand_total));
		expect(moneyValue(reducedTotalText)).toBeCloseTo(Number(persistedPreview.grand_total), 2);

		await savedPanel.getByRole("button", { name: "Edit Sale", exact: true }).click();
		await expect(rows).toHaveCount(1, { timeout: 25_000 });
		await expect(page.locator(".make-sale-form .item-count")).toContainText("1 item");
		await expect(invoiceTotal).toBeVisible({ timeout: 25_000 });
		await expect
			.poll(async () => moneyValue(await invoiceTotal.innerText()), { timeout: 25_000 })
			.toBeCloseTo(Number(persistedPreview.grand_total), 2);

		const reopenedPreview = await apiGet(
			context,
			"retailedge.standard_sales_invoice_completion.get_standard_sales_invoice_completion_preview",
			{ name: draft.name }
		);
		expect(reopenedPreview.item_count).toBe(1);
		expect(reopenedPreview.editable_items).toHaveLength(1);
		expect(Number(reopenedPreview.grand_total)).toBeCloseTo(Number(persistedPreview.grand_total), 2);
	} finally {
		await context.close().catch(() => {});
	}
});
