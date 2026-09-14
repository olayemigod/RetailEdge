const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD || "RetailEdgeBrowser1!";
const MANAGER = "browser-manager@example.com";
const CASHIER = "browser-cashier@example.com";
const ZERO_BRANCH = "browser-zero-branch@example.com";
const MULTI_BRANCH = "browser-multi-branch@example.com";

async function login(context, user = MANAGER) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: user, pwd: PASSWORD },
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
		expect(result.handoff?.filters?.retailedge_attention).toBe("ready_to_receive");
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


test("Business Hub QA regression: Receive Stock lands on Ready to Receive purchasing view", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		await page.getByRole("button", { name: /Receive Stock/i }).click();
		await page.getByRole("heading", { name: "Professional Purchasing", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		const ready = page.getByRole("button", { name: /Ready to Receive/i }).first();
		await expect(ready).toHaveClass(/attention-chip--active/);
	} finally {
		await context.close();
	}
});


test("Business Hub QA regression: period change refreshes selected-period views without relabelling current position", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const result = await page.evaluate(async () => {
			const wrapper = frappe.pages?.["retailedge-business-hub"];
			const proxy = wrapper?._retailedgeBusinessHub?._instance?.proxy;
			if (!proxy?.handleHomePeriodChange) throw new Error("Business Hub proxy is unavailable.");
			await proxy.handleHomePeriodChange("Last 30 Days");
			return {
				preset: proxy.homePeriodPreset,
				period: { ...(proxy.homePeriod || {}) },
				displayRange: proxy.homePeriod?.from_date && proxy.homePeriod?.to_date
					? `${frappe.datetime.str_to_user(proxy.homePeriod.from_date)} – ${frappe.datetime.str_to_user(proxy.homePeriod.to_date)}`
					: "",
			};
		});
		expect(result.preset).toBe("Last 30 Days");
		expect(result.period?.from_date).toBeTruthy();
		expect(result.period?.to_date).toBeTruthy();
		await expect(page.locator(".home-as-of")).toHaveText(result.displayRange);
		await expect(page.locator(".home-kpi-card").filter({ hasText: "Current position" }).first()).toBeVisible();
		await expect(page.locator(".home-kpi-card").filter({ hasText: "Last 30 Days" }).first()).toBeVisible();
	} finally {
		await context.close();
	}
});


test("Business Hub QA regression: performance KPI card opens its scoped destination", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const salesCard = page.locator(".home-kpi-card").filter({ hasText: "Sales" }).first();
		await expect(salesCard).toBeVisible();
		const result = await captureRoute(page, () => salesCard.click());
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


test("Business Hub QA regression: Record Expense carries Company and Branch into Business Expenses", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const result = await captureRoute(page, () =>
			page.getByRole("button", { name: /Record Expense/i }).click()
		);
		expect(result.route).toEqual(["business-expenses"]);
		expect(result.handoff?.target).toBe("business-expenses");
		expect(result.handoff?.filters?.company).toBeTruthy();
		expect(result.handoff?.filters?.branch).toBeTruthy();
		expect(result.handoff?.filters?.from_date).toBeUndefined();
		expect(result.handoff?.filters?.to_date).toBeUndefined();
	} finally {
		await context.close();
	}
});

test("Business Hub QA regression: Record Expense reopens New Expense after Business Expenses page reuse", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		await page.getByRole("button", { name: /Record Expense/i }).click();
		await expect(page.getByRole("heading", { name: "New Business Expense", exact: true })).toBeVisible();
		await page.getByRole("button", { name: "Back to Queue", exact: true }).click();
		await expect(page.getByRole("heading", { name: "Expense queue", exact: true })).toBeVisible();

		await page.evaluate(() => frappe.set_route("retailedge-business-hub"));
		await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({ state: "visible", timeout: 20_000 });
		await page.getByRole("button", { name: /Record Expense/i }).click();
		await expect(page.getByRole("heading", { name: "New Business Expense", exact: true })).toBeVisible();
	} finally {
		await context.close();
	}
});


test("Business Hub QA regression: cashier Record Expense stays in guided Cashier Expense", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, CASHIER);
	const page = await context.newPage();
	try {
		await openHub(page);
		await page.getByRole("button", { name: /Record Expense/i }).click();
		await expect(page.locator(".guided-expense-form")).toBeVisible();
		await expect(page.locator(".edge-app-shell").first()).toBeAttached();
		await expect(page).toHaveURL(/retailedge-business-hub/);
	} finally {
		await context.close();
	}
});


test("Business Hub QA regression: restricted-zero Branch user is gated before operational actions", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, ZERO_BRANCH);
	const page = await context.newPage();
	try {
		await page.goto(`${BASE_URL}/app/retailedge-business-hub`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		await expect(page.locator(".hub-scope-warning")).toContainText("No active Branch access");
		await expect(page.locator(".home-quick-action")).toHaveCount(0);
		for (const label of ["Make Sale", "Record Expense", "Receive Stock", "Transfer Stock", "Record Purchase"]) {
			await expect(page.getByRole("button", { name: new RegExp(label, "i") })).toHaveCount(0);
		}
	} finally {
		await context.close();
	}
});


test("Business Hub QA regression: Bank Matching page reuse reapplies the latest Hub period", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();

	async function setHubPeriod(preset) {
		return page.evaluate(async (value) => {
			const wrapper = frappe.pages?.["retailedge-business-hub"];
			const proxy = wrapper?._retailedgeBusinessHub?._instance?.proxy;
			if (!proxy?.handleHomePeriodChange) throw new Error("Business Hub proxy is unavailable.");
			await proxy.handleHomePeriodChange(value);
			return {
				from_date: proxy.homePeriod?.from_date || "",
				to_date: proxy.homePeriod?.to_date || "",
			};
		}, preset);
	}

	async function bankDateFilters() {
		return page.evaluate(() => {
			const fields = Array.from(document.querySelectorAll(".retailedge-bank-layout .edge-input"));
			const read = (label) => {
				const field = fields.find((node) => {
					const text = node.querySelector(".edge-input__label")?.textContent || node.querySelector("label")?.textContent || "";
					return String(text).trim() === label;
				});
				return field?.querySelector("input")?.value || "";
			};
			return { from_date: read("From Date"), to_date: read("To Date") };
		});
	}

	try {
		await openHub(page);
		const firstPeriod = await setHubPeriod("Last 30 Days");
		await page.getByRole("button", { name: /Match Bank Transactions/i }).click();
		await page.getByRole("heading", { name: "Bank Matching & Reconciliation", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		await expect.poll(bankDateFilters).toEqual(firstPeriod);

		await page.evaluate(() => frappe.set_route("retailedge-business-hub"));
		await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		const secondPeriod = await setHubPeriod("Yesterday");
		expect(secondPeriod).not.toEqual(firstPeriod);

		await page.getByRole("button", { name: /Match Bank Transactions/i }).click();
		await page.getByRole("heading", { name: "Bank Matching & Reconciliation", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		await expect.poll(bankDateFilters).toEqual(secondPeriod);
	} finally {
		await context.close();
	}
});


test("Business Hub QA regression: multi-Branch blank context still exposes Working Branch choice", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, MULTI_BRANCH);
	const page = await context.newPage();
	try {
		await openHub(page);
		await page.evaluate(() => {
			const shared = frappe.boot?.edgesuite_ui_identity?.retailedge;
			const legacy = frappe.boot?.retailedge_ui_identity;
			if (shared) shared.active_branch = "";
			if (legacy) legacy.active_branch = "";
			document.dispatchEvent(new CustomEvent("edgesuite-context-changed", {
				detail: { product: "retailedge", company: shared?.active_company || legacy?.active_company || "", branch: "" },
			}));
		});
		const switcher = page.locator('[aria-label="Working branch"]');
		await expect(switcher).toBeVisible();
		const trigger = switcher.locator("button").first();
		await expect(trigger).toBeEnabled();
		await expect(switcher).toContainText(/Choose working branch|Select branch/i);
	} finally {
		await context.close();
	}
});
