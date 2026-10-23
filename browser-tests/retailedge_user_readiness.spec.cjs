const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD;
const COMPANY = "RetailEdge Upgrade CI";
const READY_USER = "browser-manager@example.com";
const INCOMPLETE_USER = "browser-zero-branch@example.com";
const SETUP_ADMIN = "browser-native@example.com";

if (!PASSWORD) {
	throw new Error("RETAILEDGE_BROWSER_PASSWORD is required for user-readiness acceptance.");
}

async function login(context, user) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: user, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${user}`).toBeTruthy();
}

async function apiGet(context, method, params = {}) {
	const query = new URLSearchParams(params).toString();
	const response = await context.request.get(
		`${BASE_URL}/api/method/${method}${query ? `?${query}` : ""}`
	);
	const text = await response.text();
	let payload = {};
	try {
		payload = JSON.parse(text);
	} catch (_error) {
		// Keep raw payload for assertion diagnostics.
	}
	return { response, payload, text };
}

async function openBusinessHub(page) {
	await page.goto(`${BASE_URL}/app/retailedge-business-hub`, {
		waitUntil: "domcontentloaded",
		timeout: 30_000,
	});
	await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
		state: "visible",
		timeout: 25_000,
	});
}

test("ready RetailEdge user remains operational and has no setup warning", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, READY_USER);
	const page = await context.newPage();
	try {
		const readiness = await apiGet(context, "retailedge.user_readiness.get_my_retailedge_user_readiness", {
			company: COMPANY,
		});
		expect(readiness.response.ok(), readiness.text).toBeTruthy();
		expect(readiness.payload.message.applicable).toBe(true);
		expect(readiness.payload.message.ready).toBe(true);
		expect(readiness.payload.message.status).toBe("Ready");

		const contexts = await apiGet(context, "retailedge.operating_context.get_allowed_operating_contexts", {
			company: COMPANY,
		});
		expect(contexts.response.ok(), contexts.text).toBeTruthy();
		expect(contexts.payload.message.readiness.ready).toBe(true);
		expect(contexts.payload.message.branches).toContain("RetailEdge RC3 Lagos");

		await openBusinessHub(page);
		await expect(page.locator('[data-retailedge-readiness-guidance="1"]')).toHaveCount(0);
		await expect(page.getByRole("button", { name: "+ Create", exact: true })).toBeVisible();
	} finally {
		await context.close();
	}
});

test("intentionally incomplete RetailEdge user fails closed with actionable guidance", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, INCOMPLETE_USER);
	const page = await context.newPage();
	try {
		const readiness = await apiGet(context, "retailedge.user_readiness.get_my_retailedge_user_readiness", {
			company: COMPANY,
		});
		expect(readiness.response.ok(), readiness.text).toBeTruthy();
		expect(readiness.payload.message.applicable).toBe(true);
		expect(readiness.payload.message.ready).toBe(false);
		expect(readiness.payload.message.status).toBe("Setup incomplete");
		expect(readiness.payload.message.reasons.map((reason) => reason.code)).toContain("missing_company_assignment");
		expect(readiness.payload.message.message).toMatch(/assign.*active Branch|Company and Branch/i);

		const deniedContexts = await apiGet(context, "retailedge.operating_context.get_allowed_operating_contexts", {
			company: COMPANY,
		});
		expect(deniedContexts.response.status(), deniedContexts.text).toBe(403);
		expect(deniedContexts.payload.exc_type).toBe("PermissionError");

		const contexts = await apiGet(context, "retailedge.operating_context.get_allowed_operating_contexts");
		expect(contexts.response.ok(), contexts.text).toBeTruthy();
		expect(contexts.payload.message.companies).toEqual([]);
		expect(contexts.payload.message.branches).toEqual([]);
		expect(contexts.payload.message.readiness.ready).toBe(false);

		const transfer = await apiGet(context, "retailedge.guided_stock_transfer.get_simple_stock_transfer_context", {
			company: COMPANY,
		});
		expect(transfer.response.ok()).toBeFalsy();
		expect(transfer.text).toMatch(/setup is not complete|Assign this User|PermissionError/i);

		await openBusinessHub(page);
		const notice = page.locator('[data-retailedge-readiness-guidance="1"]');
		await expect(notice).toBeVisible();
		await expect(notice).toContainText("Access setup incomplete");
		await expect(notice).toContainText(/Company and Branch|active Branch/i);
		await expect(page.getByRole("button", { name: "+ Create", exact: true })).toHaveCount(0);
		await expect(page.locator(".home-quick-action")).toHaveCount(0);
	} finally {
		await context.close();
	}
});

test("setup administrator can discover the incomplete historical user without backfill", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, SETUP_ADMIN);
	const page = await context.newPage();
	try {
		const review = await apiGet(
			context,
			"retailedge.user_readiness.get_retailedge_user_readiness_reconciliation",
			{ include_ready: 0, page_length: 100 }
		);
		expect(review.response.ok(), review.text).toBeTruthy();
		const row = review.payload.message.rows.find((candidate) => candidate.user === INCOMPLETE_USER);
		expect(row).toBeTruthy();
		expect(row.ready).toBe(false);
		expect(row.repair_action.key).toBe("assign_branch");

		await page.goto(`${BASE_URL}/app/branch-assignments`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.getByRole("heading", { name: "Branch Assignments", exact: true }).first().waitFor({
			state: "visible",
			timeout: 25_000,
		});
		await expect(page.getByText("User access readiness", { exact: true })).toBeVisible();
		const incompleteRow = page.locator(".readiness-table tbody tr").filter({ hasText: INCOMPLETE_USER });
		await expect(incompleteRow).toBeVisible();
		await expect(incompleteRow.getByRole("button", { name: "Assign Company and Branch", exact: true })).toBeVisible();
		await incompleteRow.getByRole("button", { name: "Assign Company and Branch", exact: true }).click();
		const assignDialog = page.getByRole("dialog", { name: "Assign User to Branch", exact: true });
		await expect(assignDialog.getByPlaceholder("Choose system user", { exact: true })).toHaveValue(INCOMPLETE_USER);
		await assignDialog.getByRole("button", { name: "Cancel", exact: true }).click();
		await page.getByRole("button", { name: "Assign User", exact: true }).click();
		await expect(assignDialog.getByPlaceholder("Choose system user", { exact: true })).toHaveValue("");
		await assignDialog.getByRole("button", { name: "Cancel", exact: true }).click();

		const stillIncomplete = await apiGet(context, "retailedge.user_readiness.get_retailedge_user_readiness_reconciliation", {
			include_ready: 0,
			page_length: 100,
		});
		expect(stillIncomplete.response.ok(), stillIncomplete.text).toBeTruthy();
		expect(stillIncomplete.payload.message.rows.some((candidate) => candidate.user === INCOMPLETE_USER)).toBe(true);
	} finally {
		await context.close();
	}
});

test("setup administrator can enter the governed user onboarding wizard without mutating the user", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, SETUP_ADMIN);
	const page = await context.newPage();
	try {
		const before = await apiGet(
			context,
			"retailedge.user_readiness.get_retailedge_user_readiness_reconciliation",
			{ include_ready: 0, page_length: 100 }
		);
		expect(before.response.ok(), before.text).toBeTruthy();
		expect(before.payload.message.rows.some((candidate) => candidate.user === INCOMPLETE_USER)).toBe(true);

		await page.goto(`${BASE_URL}/app/retailedge-setup`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.getByRole("heading", { name: "Setup", exact: true }).first().waitFor({
			state: "visible",
			timeout: 25_000,
		});
		await page.getByRole("button", { name: "Start Onboarding", exact: true }).click();
		await expect(page.getByRole("heading", { name: "User Onboarding", exact: true })).toBeVisible();
		for (const step of ["Person", "Access", "Location", "Point of Sale", "Review"]) {
			await expect(page.getByRole("button", { name: new RegExp(step) }).first()).toBeVisible();
		}

		const userField = page.getByPlaceholder("Search enabled System Users", { exact: true });
		await userField.fill(INCOMPLETE_USER);
		const option = page.getByRole("option").filter({ hasText: INCOMPLETE_USER }).first();
		await expect(option).toBeVisible();
		await option.click();
		await expect(page.getByText(INCOMPLETE_USER, { exact: true }).first()).toBeVisible();
		await page.getByRole("button", { name: "Continue", exact: true }).click();
		await expect(page.getByText("Business document permissions stay in ERPNext.", { exact: true })).toBeVisible();

		const after = await apiGet(
			context,
			"retailedge.user_readiness.get_retailedge_user_readiness_reconciliation",
			{ include_ready: 0, page_length: 100 }
		);
		expect(after.response.ok(), after.text).toBeTruthy();
		expect(after.payload.message.rows.some((candidate) => candidate.user === INCOMPLETE_USER)).toBe(true);
	} finally {
		await context.close();
	}
});