const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD || "RetailEdgeBrowser1!";
const MANAGER = "browser-manager@example.com";

async function login(context) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: MANAGER, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${MANAGER}`).toBeTruthy();
	const payload = await response.json();
	expect(String(payload.message || "")).toMatch(/Logged In/i);
}

test("RetailEdge keeps shared desktop collapse control after shell rerender", async ({ browser }) => {
	const context = await browser.newContext({
		baseURL: BASE_URL,
		viewport: { width: 1280, height: 800 },
	});
	await login(context);
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

		const shell = page.locator('.edge-app-shell[data-edge-product="retailedge"]').first();
		await expect(shell).toBeVisible();
		await expect(shell).toHaveClass(/edge-nav-shell-v2/);

		let toggle = shell.locator(".edge-nav-shell-toggle");
		await expect(toggle).toBeVisible();
		await expect(toggle).toHaveAttribute("aria-label", "Collapse navigation");

		// Model the product-shell identity/brand reconciliation that originally
		// removed the DOM-injected control while leaving the shell mounted.
		await toggle.evaluate((node) => node.remove());
		await expect(shell.locator(".edge-nav-shell-toggle")).toBeVisible({ timeout: 5_000 });

		toggle = shell.locator(".edge-nav-shell-toggle");
		await expect(toggle).toHaveAttribute("aria-label", "Collapse navigation");
		await toggle.click();
		await expect(shell).toHaveClass(/edge-nav-shell--collapsed/);
		await expect(toggle).toHaveAttribute("aria-label", "Expand navigation");

		const sidebar = shell.locator(".edge-sidebar").first();
		await expect
			.poll(() => sidebar.evaluate((node) => Math.round(node.getBoundingClientRect().width)))
			.toBe(72);

		const stored = await page.evaluate(
			() => localStorage.getItem("edgeui:browser-manager@example.com:retailedge:navigation-collapsed"),
		);
		expect(stored).toBe("1");

		await page.reload({ waitUntil: "domcontentloaded" });
		await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
		const reloadedShell = page.locator('.edge-app-shell[data-edge-product="retailedge"]').first();
		await expect(reloadedShell).toHaveClass(/edge-nav-shell--collapsed/);
		await expect(reloadedShell.locator(".edge-nav-shell-toggle")).toHaveAttribute(
			"aria-label",
			"Expand navigation",
		);
	} finally {
		await context.close().catch(() => {});
	}
});
