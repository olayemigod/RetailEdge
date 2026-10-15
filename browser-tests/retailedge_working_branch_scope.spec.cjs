const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD;
const COMPANY = "RetailEdge Upgrade CI";
const LAGOS = "RetailEdge RC3 Lagos";
const IKEJA = "RetailEdge RC3 Ikeja";
const USER = "browser-multi-branch@example.com";

if (!PASSWORD) {
	throw new Error("RETAILEDGE_BROWSER_PASSWORD is required for Working Branch acceptance.");
}

async function login(context) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: USER, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${USER}`).toBeTruthy();
}

async function switchBranch(page, branch) {
	const result = await page.evaluate(
		({ company, nextBranch }) =>
			new Promise((resolve, reject) => {
				frappe.call({
					method: "retailedge.operating_context.switch_operating_context",
					args: { company, branch: nextBranch },
					callback: (response) => resolve(response.message || {}),
					error: (error) => reject(new Error(error?.message || "Working Branch switch failed")),
				});
			}),
		{ company: COMPANY, nextBranch: branch }
	);
	expect(result.branch).toBe(branch);
}

async function expectStockEntryBranchFilter(page, branch) {
	await expect
		.poll(() => page.evaluate(() => window.cur_list?.doctype || ""), { timeout: 20_000 })
		.toBe("Stock Entry");
	await expect
		.poll(
			() =>
				page.evaluate(() => {
					const filters = window.cur_list?.filter_area?.get?.() || [];
					const match = filters.find(
						(filter) => Array.isArray(filter) && filter[1] === "retailedge_branch"
					);
					return match?.[3] || "";
				}),
			{ timeout: 20_000 }
		)
		.toBe(branch);
}

test("Working Branch exposes every permitted Branch and scopes document lists after switching", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	try {
		await page.goto(`${BASE_URL}/app/retailedge-business-hub`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
			state: "visible",
			timeout: 25_000,
		});

		const branches = await page.evaluate(
			(company) =>
				new Promise((resolve, reject) => {
					frappe.call({
						method: "retailedge.operating_context.get_allowed_operating_contexts",
						args: { company },
						callback: (response) => resolve(response.message?.branches || []),
						error: (error) => reject(new Error(error?.message || "Could not load permitted Branches")),
					});
				}),
			COMPANY
		);
		expect(new Set(branches)).toEqual(new Set([LAGOS, IKEJA]));

		await switchBranch(page, LAGOS);
		await page.goto(`${BASE_URL}/app/stock-entry`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await expectStockEntryBranchFilter(page, LAGOS);

		await switchBranch(page, IKEJA);
		await page.reload({ waitUntil: "domcontentloaded", timeout: 30_000 });
		await expectStockEntryBranchFilter(page, IKEJA);
	} finally {
		await context.close();
	}
});
