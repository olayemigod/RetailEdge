const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const COMPANY = "RetailEdge Upgrade CI";
const BRANCH = "RetailEdge RC3 Lagos";

async function loginAdministrator(context) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: "Administrator", pwd: "admin" },
	});
	expect(response.ok(), "Administrator login failed").toBeTruthy();
}

async function assertNoAssetOrRuntimeErrors(page, action) {
	const errors = [];
	const pageErrorHandler = (error) => errors.push(`pageerror: ${error.message}`);
	const responseHandler = (response) => {
		const type = response.request().resourceType();
		if (["script", "stylesheet"].includes(type) && response.status() >= 400) {
			errors.push(`${response.status()} ${type}: ${response.url()}`);
		}
	};
	page.on("pageerror", pageErrorHandler);
	page.on("response", responseHandler);
	try {
		await action();
		await page.waitForTimeout(300);
		expect(errors).toEqual([]);
	} finally {
		page.off("pageerror", pageErrorHandler);
		page.off("response", responseHandler);
	}
}

function printingUrl(route) {
	return `${BASE_URL}/app/${route}`;
}

async function assertRetailEdgeShellPresence(page) {
	const shell = page.locator('.edge-app-shell[data-edge-product="retailedge"]:visible');
	await expect(shell).toHaveCount(1);
	await expect(shell.locator(".edge-sidebar")).toBeVisible();
	await expect(shell.locator(".edge-sidebar")).toContainText("ProcessEdge Retail");
	await expect(shell.locator(".edge-sidebar")).toContainText("Business Hub");
	return shell;
}

async function assertRetailEdgeShell(page) {
	await assertRetailEdgeShellPresence(page);
	await expect(page.locator(".page-head:visible")).toHaveCount(0);
	await expect(page.locator(".body-sidebar-container:visible")).toHaveCount(0);
}

test("Document Output menu keeps Devices & Printing in the same virtual-printer session", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await loginAdministrator(context);
	const page = await context.newPage();

	try {
		await assertNoAssetOrRuntimeErrors(page, async () => {
			await page.goto(`${BASE_URL}/app/document-output-sharing`, {
				waitUntil: "domcontentloaded",
				timeout: 30_000,
			});
			await page.getByRole("heading", { name: "Document Output & Sharing", exact: true }).waitFor({
				state: "visible",
				timeout: 25_000,
			});
			await assertRetailEdgeShellPresence(page);
		});

		await page.evaluate(async () => {
			const adapter = window.EdgeSuiteUI?.print;
			if (!adapter?.simulation || typeof adapter.printReceipt !== "function") {
				throw new Error("Shared virtual print runtime is unavailable.");
			}
			await adapter.simulation.enable();
			await adapter.printReceipt({
				paper: 80,
				charactersPerLine: 48,
				blocks: [
					{ type: "text", text: "Document Output Session Probe", align: "center", bold: true },
					{ type: "feed", lines: 1 },
				],
				metadata: { purpose: "browser-navigation-regression" },
			});
		});

		expect(await page.evaluate(() => window.EdgeSuiteUI?.print?.simulation?.isEnabled?.())).toBeTruthy();
		expect(await page.evaluate(() => window.EdgeSuiteUI?.print?.simulation?.getHistory?.()?.length || 0)).toBeGreaterThan(0);
		expect(await page.evaluate(() => window.sessionStorage.getItem("edgesuite.printing.virtual_printer.v1"))).toBeTruthy();

		const pagesBefore = context.pages().length;
		const shell = page.locator('.edge-app-shell[data-edge-product="retailedge"]:visible');
		const sidebar = shell.locator(".edge-sidebar");
		const printingSection = sidebar.locator(".edge-sidebar__section").filter({ hasText: "Devices & Printing" }).first();
		await expect(printingSection).toHaveCount(1);
		const printingSectionToggle = printingSection.locator(".edge-sidebar__section-toggle").first();
		await expect(printingSectionToggle).toBeVisible();
		if ((await printingSectionToggle.getAttribute("aria-expanded")) !== "true") {
			await printingSectionToggle.click();
		}
		await expect(printingSectionToggle).toHaveAttribute("aria-expanded", "true");
		const printingMenuItem = printingSection.locator(".edge-sidebar-item").filter({ hasText: "Devices & Printing" }).first();
		await expect(printingMenuItem).toBeVisible();
		await printingMenuItem.click();
		await page.waitForURL(/\/(?:app|desk)\/edge-printing$/, { timeout: 25_000 });
		await page.getByRole("heading", { name: "Devices & Printing", exact: true }).waitFor({
			state: "visible",
			timeout: 25_000,
		});
		expect(context.pages().length).toBe(pagesBefore);
		await assertRetailEdgeShell(page);
		await expect(page.locator(".edge-printing-page-actions")).toContainText(COMPANY);
		await expect(page.locator(".edge-printing-page-actions")).toContainText(BRANCH);
		await expect(page.locator(".edge-printing-simulator .edge-status-badge")).toHaveText("Active");
		await expect(page.getByText("Last Virtual Print", { exact: true })).toBeVisible();
		await expect(page.getByText("Document Output Session Probe", { exact: false })).toBeVisible();
		expect(await page.evaluate(() => window.EdgeSuiteUI?.print?.simulation?.isEnabled?.())).toBeTruthy();
		expect(await page.evaluate(() => window.EdgeSuiteUI?.print?.simulation?.getHistory?.()?.length || 0)).toBeGreaterThan(0);

		await page.getByRole("button", { name: "Return to Physical Printer", exact: true }).click();
		await expect(page.locator(".edge-printing-simulator .edge-status-badge")).toHaveText("Off");
	} finally {
		await context.close();
	}
});

test("printing administration pages mount the real RetailEdge EdgeSuite shell", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await loginAdministrator(context);
	const page = await context.newPage();

	try {
		await assertNoAssetOrRuntimeErrors(page, async () => {
			await page.goto(printingUrl("edge-printing"), {
				waitUntil: "domcontentloaded",
				timeout: 30_000,
			});
			await page.getByRole("heading", { name: "Devices & Printing", exact: true }).waitFor({
				state: "visible",
				timeout: 25_000,
			});
			await assertRetailEdgeShell(page);
			await expect(page.locator(".edge-printing-page-actions")).toContainText(COMPANY);
			await expect(page.locator(".edge-printing-page-actions")).toContainText(BRANCH);
			await expect(page.getByText("Virtual Printer (QA)", { exact: true })).toBeVisible();
			await page.getByRole("button", { name: "Enable Virtual Printer", exact: true }).click();
			await expect(page.locator(".edge-printing-simulator .edge-status-badge")).toHaveText("Active");
			await expect(page.getByRole("button", { name: "Return to Physical Printer", exact: true })).toBeVisible();
		});

		await assertNoAssetOrRuntimeErrors(page, async () => {
			await page.getByRole("button", { name: "Manage Print Profiles", exact: true }).click();
			await page.waitForURL(/\/(?:app|desk)\/edge-print-profiles$/, { timeout: 25_000 });
			await page.getByRole("heading", { name: "Print Profiles", exact: true }).waitFor({
				state: "visible",
				timeout: 25_000,
			});
			await assertRetailEdgeShell(page);
			await expect(page.locator(".edge-print-profiles-page-root:visible")).toHaveCount(1);
			await expect(page.getByRole("button", { name: "New Print Profile", exact: true })).toBeVisible();
		});

		const url = new URL(page.url());
		expect(url.search).toBe("");

		await page.getByRole("button", { name: "New Print Profile", exact: true }).click();
		const productField = page.locator("label.edge-print-profile-field").filter({ hasText: "Product" }).first();
		await expect(productField).toBeVisible();
		await expect(productField.locator("select")).toContainText("PEdge Retail");
		await expect(page.getByText("Product Key", { exact: true })).toHaveCount(0);

		const profileName = "Browser Branch Receipt Profile";
		await page.locator("label.edge-print-profile-field").filter({ hasText: "Profile Name" }).locator("input").fill(profileName);
		await productField.locator("select").selectOption("retailedge");
		await page.locator("label.edge-print-profile-field").filter({ hasText: "Scope Type" }).locator("select").selectOption("Branch");
		const branchField = page.locator("label.edge-print-profile-field").filter({
			has: page.locator(".edge-input__label", { hasText: "Branch" }),
		});
		await expect(branchField).toHaveCount(1);
		await branchField.locator("input").fill(BRANCH);
		await page.getByRole("button", { name: "Create Print Profile", exact: true }).click();
		await expect(page.locator(".edge-print-profile-row").filter({ hasText: profileName })).toBeVisible({ timeout: 15_000 });
		await expect(page.getByText("Unable to save print profile", { exact: true })).toHaveCount(0);
		await expect(page.getByText("[object Object]", { exact: true })).toHaveCount(0);

		await assertNoAssetOrRuntimeErrors(page, async () => {
			await page.goto(printingUrl("edge-printing"), {
				waitUntil: "domcontentloaded",
				timeout: 30_000,
			});
			await page.getByRole("heading", { name: "Devices & Printing", exact: true }).waitFor({
				state: "visible",
				timeout: 25_000,
			});
			await assertRetailEdgeShell(page);
			await expect(page.locator(".edge-printing-simulator .edge-status-badge")).toHaveText("Active");
			await expect(page.getByText("Virtual session", { exact: true })).toBeVisible();
			await expect(page.getByRole("button", { name: "Test Print", exact: true })).toBeVisible();
			await page.getByRole("button", { name: "Test Print", exact: true }).click();
			await page.getByRole("button", { name: "View Last Virtual Print", exact: true }).click();
			await expect(page.getByText("Last Virtual Print", { exact: true })).toBeVisible();
			await expect(page.getByText("EdgeSuite Printer Test", { exact: false })).toBeVisible();
		});

		const storedVirtualSession = await page.evaluate(() =>
			window.sessionStorage.getItem("edgesuite.printing.virtual_printer.v1"),
		);
		expect(storedVirtualSession).toBeTruthy();

		await page.getByRole("button", { name: "Return to Physical Printer", exact: true }).click();
		await expect(page.locator(".edge-printing-simulator .edge-status-badge")).toHaveText("Off");
		expect(await page.evaluate(() => window.sessionStorage.getItem("edgesuite.printing.virtual_printer.v1"))).toBeNull();

		await page.goto(`${BASE_URL}/desk/sales-invoice`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.waitForURL(/\/(?:app|desk)\/sales-invoice(?:\?|$)/, { timeout: 25_000 });
		await expect(page.getByText("Not found", { exact: false })).toHaveCount(0);
		await expect(page.locator(".body-sidebar-container:visible")).toHaveCount(1);
	} finally {
		await context.close();
	}
});
