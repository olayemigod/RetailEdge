const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD || "RetailEdgeBrowser1!";
const COMPANY = "RetailEdge Upgrade CI";
const LAGOS = "RetailEdge RC3 Lagos";
const IKEJA = "RetailEdge RC3 Ikeja";
const MULTI_BRANCH = "browser-multi-branch@example.com";
const MANAGER = "browser-manager@example.com";

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
	await page.goto(`${BASE_URL}/app/${route}`, {
		waitUntil: "domcontentloaded",
		timeout: 30_000,
	});
	await page.getByRole("heading", { name: title, exact: true }).first().waitFor({
		state: "visible",
		timeout: 25_000,
	});
	await expect(page.locator(".modal:visible")).toHaveCount(0);
}

async function apiGet(context, method, params = {}) {
	const query = new URLSearchParams(params).toString();
	const response = await context.request.get(
		`${BASE_URL}/api/method/${method}${query ? `?${query}` : ""}`,
	);
	const text = await response.text();
	let payload = {};
	try {
		payload = JSON.parse(text);
	} catch (_error) {
		// Keep raw text for assertion diagnostics.
	}
	return { response, payload, text };
}

async function expectOperatingBranch(context, branch) {
	await expect.poll(async () => {
		const result = await apiGet(context, "retailedge.operating_context.get_operating_context", {
			company: COMPANY,
		});
		if (!result.response.ok()) return `HTTP ${result.response.status()}: ${result.text}`;
		return result.payload?.message?.branch || "";
	}).toBe(branch);
}

async function expectBusinessHubBranch(context, branch) {
	await expect.poll(async () => {
		const result = await apiGet(context, "retailedge.master_experience.get_retailedge_business_hub_context");
		if (!result.response.ok()) return `HTTP ${result.response.status()}: ${result.text}`;
		return result.payload?.message?.context?.branch || "";
	}).toBe(branch);
}

async function chooseWorkingBranch(page, branch) {
	const switcher = page.locator('[aria-label="Working branch"]');
	await expect(switcher).toBeVisible();
	const trigger = switcher.locator("button").first();
	await expect(trigger).toBeEnabled();
	await trigger.click();

	const dialog = page.getByRole("dialog", { name: "Choose working branch", exact: true });
	await expect(dialog).toBeVisible();
	const option = dialog.locator('.retailedge-branch-popover__option[role="option"]').filter({ hasText: branch });
	await expect(option).toHaveCount(1);
	await option.click();
}

test("multi-Branch Business Hub switches working Branch and preserves it through browser history", async ({ browser }) => {
	const { context, page } = await newPersona(browser, MULTI_BRANCH);
	try {
		await openProductPage(page, "retailedge-business-hub", "Business Hub");
		const switcher = page.locator('[aria-label="Working branch"]');
		await expect(switcher).toContainText(LAGOS);
		await expectOperatingBranch(context, LAGOS);

		await chooseWorkingBranch(page, IKEJA);
		await expectOperatingBranch(context, IKEJA);
		await expectBusinessHubBranch(context, IKEJA);
		await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
			state: "visible",
			timeout: 25_000,
		});
		await expect(switcher).toContainText(IKEJA);
		await expect(page.locator(".home-intelligence-card")).toHaveCount(8);

		await page.evaluate(() => frappe.set_route("action-center"));
		await page.getByRole("heading", { name: "Action Centre", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		await expect(page.locator('[aria-label="Working branch"]')).toContainText(IKEJA);

		await page.goBack({ waitUntil: "domcontentloaded" }).catch(() => null);
		await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		await expect(page.locator('[aria-label="Working branch"]')).toContainText(IKEJA);
		await expectOperatingBranch(context, IKEJA);

		await page.goForward({ waitUntil: "domcontentloaded" }).catch(() => null);
		await page.getByRole("heading", { name: "Action Centre", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		await expect(page.locator('[aria-label="Working branch"]')).toContainText(IKEJA);

		// Restore the deterministic fixture state for later persona tests and reruns.
		await page.goBack({ waitUntil: "domcontentloaded" }).catch(() => null);
		await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		await chooseWorkingBranch(page, LAGOS);
		await expectOperatingBranch(context, LAGOS);
		await expectBusinessHubBranch(context, LAGOS);
		await expect(page.locator('[aria-label="Working branch"]')).toContainText(LAGOS);
	} finally {
		await context.close().catch(() => {});
	}
});

test("RetailEdge Shift Reconciliation consumes Smart Date shortcuts and typed business periods", async ({ browser }) => {
	const { context, page } = await newPersona(browser, MANAGER);
	try {
		await openProductPage(page, "pos-closing-variance", "Shift Reconciliation");
		const smartDate = page.locator(".edge-smart-date").filter({ hasText: "Date Range" }).first();
		await expect(smartDate).toBeVisible();

		const trigger = smartDate.locator(".edge-smart-date__trigger");
		await trigger.click();
		await expect(page.getByText("Quick periods", { exact: true })).toBeVisible();
		await expect(page.locator(".edge-smart-date__preset")).toHaveCount(10);
		await page.getByRole("button", { name: "This Month", exact: true }).click();
		await expect(smartDate.locator(".edge-smart-date__period-label")).toHaveText("This Month");

		const refresh = page.getByRole("button", { name: "Refresh", exact: true });
		await expect(refresh).toBeVisible();
		await refresh.click();
		await expect(refresh).toBeEnabled();
		await expect(smartDate.locator(".edge-smart-date__period-label")).toHaveText("This Month");

		await trigger.click();
		const input = page.locator(".edge-smart-date__input");
		await input.fill("May to June 2026");
		await expect(page.locator(".edge-smart-date__interpretation")).toBeVisible();
		await page.locator(".edge-smart-date__apply").click();
		await expect(smartDate.locator(".edge-smart-date__range-value")).toContainText("01-05-2026");
		await expect(smartDate.locator(".edge-smart-date__range-value")).toContainText("30-06-2026");

		await refresh.click();
		await expect(refresh).toBeEnabled();
		await expect(smartDate.locator(".edge-smart-date__range-value")).toContainText("01-05-2026");
		await expect(smartDate.locator(".edge-smart-date__range-value")).toContainText("30-06-2026");
		await expect(page.locator(".managed-report-fallback")).toHaveCount(0);
	} finally {
		await context.close().catch(() => {});
	}
});
