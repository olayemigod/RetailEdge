const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD || "RetailEdgeBrowser1!";
const MANAGER = "browser-manager@example.com";
const ZERO_BRANCH = "browser-zero-branch@example.com";
const MULTI_BRANCH = "browser-multi-branch@example.com";

async function login(context, user = MANAGER) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: user, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${user}`).toBeTruthy();
}

async function openHub(page) {
	await page.goto(`${BASE_URL}/app/retailedge-business-hub`, {
		waitUntil: "domcontentloaded",
		timeout: 45_000,
	});
	await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
		state: "visible",
		timeout: 30_000,
	});
	await expect(page.locator(".retailedge-business-hub")).toBeVisible();
	await expect(page.locator(".edge-app-shell").first()).toBeAttached();
}

async function callFrappe(page, method, args = {}) {
	return page.evaluate(({ method, args }) => new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response?.message || {}),
			error: reject,
		});
	}), { method, args });
}

async function getHubContext(page) {
	return callFrappe(page, "retailedge.edgesuite_ui.get_retailedge_business_hub_context");
}

async function captureRoute(page, locator) {
	await page.evaluate(() => {
		window.__businessHubQaRoute = null;
		window.__businessHubQaOriginalSetRoute = frappe.set_route;
		frappe.set_route = (...args) => {
			window.__businessHubQaRoute = args;
		};
	});
	try {
		await locator.click({ timeout: 12_000 });
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

test("Business Hub QA: light appearance does not force a dark RetailEdge shell", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const result = await page.evaluate(() => {
			document.documentElement.setAttribute("data-edge-appearance", "light");
			const shell = document.querySelector('[data-edge-product="retailedge"]') || document.querySelector(".edge-app-shell");
			const sidebar = document.querySelector(".edge-app-shell__sidebar");
			const title = document.querySelector(".edge-topbar__title-copy strong");
			const shellStyle = shell ? getComputedStyle(shell) : null;
			return {
				retailSurface: shellStyle?.getPropertyValue("--retailedge-surface").trim() || "",
				edgeSurface: shellStyle?.getPropertyValue("--edge-color-surface").trim() || "",
				retailInk: shellStyle?.getPropertyValue("--retailedge-ink").trim() || "",
				edgeInk: shellStyle?.getPropertyValue("--edge-color-ink-950").trim() || "",
				sidebarBackground: sidebar ? getComputedStyle(sidebar).backgroundColor : "",
				titleColor: title ? getComputedStyle(title).color : "",
				titleText: title?.textContent?.trim() || "",
			};
		});
		expect(result.titleText).toBeTruthy();
		expect(result.titleColor).not.toBe("rgba(0, 0, 0, 0)");
		expect(result.sidebarBackground).not.toBe("rgb(11, 31, 51)");
		expect(result.retailSurface).toBeTruthy();
		expect(result.retailInk).toBeTruthy();
		if (result.edgeSurface) expect(result.retailSurface).toBe(result.edgeSurface);
		if (result.edgeInk) expect(result.retailInk).toBe(result.edgeInk);
	} finally {
		await context.close();
	}
});

test("Business Hub QA: EdgeSuite theme tokens drive RetailEdge brand and surfaces", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const tokens = await page.evaluate(() => {
			const shell = document.querySelector('[data-edge-product="retailedge"]') || document.querySelector(".edge-app-shell");
			const style = getComputedStyle(shell);
			return {
				edgeBrand: style.getPropertyValue("--edge-color-brand-600").trim(),
				retailBrand: style.getPropertyValue("--retailedge-brand").trim(),
				edgeSurface: style.getPropertyValue("--edge-color-surface").trim(),
				retailSurface: style.getPropertyValue("--retailedge-surface").trim(),
			};
		});
		expect(tokens.retailBrand).toBeTruthy();
		expect(tokens.retailSurface).toBeTruthy();
		if (tokens.edgeBrand) expect(tokens.retailBrand).toBe(tokens.edgeBrand);
		if (tokens.edgeSurface) expect(tokens.retailSurface).toBe(tokens.edgeSurface);
	} finally {
		await context.close();
	}
});

test("Business Hub QA: Smart Date replaces fixed Period dropdown and architecture labels stay hidden", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		await expect(page.locator('input[placeholder*="last 30 days"]')).toBeVisible();
		for (const label of ["UNDERSTAND", "ACT", "OPERATE", "RESPOND"]) {
			await expect(page.getByText(label, { exact: true })).toHaveCount(0);
		}
	} finally {
		await context.close();
	}
});

test("Business Hub QA: Smart Date custom range reaches authoritative Hub snapshot", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const hub = await getHubContext(page);
		const company = hub?.context?.company || "";
		const branch = hub?.context?.branch || "";
		expect(company).toBeTruthy();
		const snapshot = await callFrappe(page, "retailedge.business_hub_home.get_business_hub_home_snapshot", {
			company,
			branch,
			date_preset: "Custom Period",
			from_date: "2026-08-01",
			to_date: "2026-08-31",
			date_label: "August 2026",
		});
		expect(snapshot?.period?.preset).toBe("Custom Period");
		expect(snapshot?.period?.from_date).toBe("2026-08-01");
		expect(snapshot?.period?.to_date).toBe("2026-08-31");
		expect(snapshot?.period?.label).toBe("August 2026");
	} finally {
		await context.close();
	}
});

test("Business Hub QA: visible monetary KPI values stay inside their cards", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const cards = page.locator(".home-kpi-card");
		const count = await cards.count();
		expect(count).toBeGreaterThan(0);
		const measurements = await page.locator(".home-kpi-card strong").evaluateAll((nodes) =>
			nodes.map((node) => ({
				text: node.textContent?.trim() || "",
				clientWidth: node.clientWidth,
				scrollWidth: node.scrollWidth,
				whiteSpace: getComputedStyle(node).whiteSpace,
			}))
		);
		expect(measurements.length).toBeGreaterThan(0);
		for (const row of measurements) {
			expect(row.whiteSpace).toBe("nowrap");
			expect(row.scrollWidth, `KPI overflow: ${row.text}`).toBeLessThanOrEqual(row.clientWidth + 1);
		}
	} finally {
		await context.close();
	}
});

test("Business Hub QA: permission-derived actions do not leak unavailable transaction shortcuts", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const hub = await getHubContext(page);
		const keys = new Set((hub.quick_actions || []).map((row) => row.key));
		const labels = {
			"new-sales-invoice": "Make Sale",
			"receive-customer-payment": "Receive Customer Payment",
			"pay-supplier": "Pay Supplier",
			"record-expense": "Record Expense",
			"transfer-stock": "Transfer Stock",
			"record-purchase": "Record Purchase",
		};
		for (const [key, label] of Object.entries(labels)) {
			if (!keys.has(key)) {
				await expect(page.locator(".home-quick-action").filter({ hasText: label })).toHaveCount(0);
			}
		}
	} finally {
		await context.close();
	}
});

test("Business Hub QA: restricted-zero Branch remains visibly fail-closed", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, ZERO_BRANCH);
	const page = await context.newPage();
	try {
		await openHub(page);
		await expect(page.locator(".hub-scope-warning")).toContainText("No active Branch access");
		await expect(page.locator(".home-quick-action")).toHaveCount(0);
		const hub = await getHubContext(page);
		expect(hub?.context?.branch_scope_restricted).toBeTruthy();
		expect(hub?.context?.branch_scope_ready).toBeFalsy();
	} finally {
		await context.close();
	}
});

test("Business Hub QA: multiple permitted Branches expose Working Branch switcher", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, MULTI_BRANCH);
	const page = await context.newPage();
	try {
		await openHub(page);
		const hub = await getHubContext(page);
		expect((hub?.context?.branch_options || []).length).toBeGreaterThan(1);
		const switcher = page.locator('[aria-label="Working branch"]');
		await expect(switcher).toBeVisible();
		await expect(switcher.locator("button").first()).toBeEnabled();
	} finally {
		await context.close();
	}
});

test("Business Hub QA: Bank Matching page shortcut keeps Hub scope and selected period", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await openHub(page);
		const shortcut = page.locator(".home-quick-action").filter({ hasText: "Match Bank Transactions" });
		if (await shortcut.count() === 0) test.skip(true, "Bank Matching page is not permitted for this persona.");
		const result = await captureRoute(page, shortcut.first());
		expect(result.route).toEqual(["bank-matching-reconciliation"]);
		expect(result.handoff?.target).toBe("bank-matching-reconciliation");
		expect(result.handoff?.filters?.company).toBeTruthy();
		expect(result.handoff?.filters?.from_date).toBeTruthy();
		expect(result.handoff?.filters?.to_date).toBeTruthy();
	} finally {
		await context.close();
	}
});
