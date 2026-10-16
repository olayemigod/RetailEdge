const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD;
const COMPANY = "RetailEdge Upgrade CI";
const LAGOS = "RetailEdge RC3 Lagos";
const IKEJA = "RetailEdge RC3 Ikeja";
const RESTRICTED_USER = "browser-multi-branch@example.com";
const GLOBAL_USER = "browser-global-branch@example.com";
const SALES_INVOICE_FIXTURE_PREFIX = "RetailEdge browser Working Branch fixture:";

if (!PASSWORD) {
	throw new Error("RETAILEDGE_BROWSER_PASSWORD is required for Working Branch acceptance.");
}

async function login(context, user) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: user, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${user}`).toBeTruthy();
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

async function allowedContexts(page) {
	return page.evaluate(
		(company) =>
			new Promise((resolve, reject) => {
				frappe.call({
					method: "retailedge.operating_context.get_allowed_operating_contexts",
					args: { company },
					callback: (response) => resolve(response.message || {}),
					error: (error) => reject(new Error(error?.message || "Could not load permitted Branches")),
				});
			}),
		COMPANY
	);
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
	expect(result.company_wide).toBeFalsy();
}

async function switchAllBranches(page) {
	const result = await page.evaluate(
		(company) =>
			new Promise((resolve, reject) => {
				frappe.call({
					method: "retailedge.operating_context.switch_company_wide_context",
					args: { company },
					callback: (response) => resolve(response.message || {}),
					error: (error) => reject(new Error(error?.message || "All Branches switch failed")),
				});
			}),
		COMPANY
	);
	expect(result.company).toBe(COMPANY);
	expect(result.branch).toBe("");
	expect(result.company_wide).toBe(true);
}

async function sellingRows(page) {
	const result = await page.evaluate(
		() =>
			new Promise((resolve, reject) => {
				frappe.call({
					method: "retailedge.professional_selling.get_professional_selling_list",
					args: { document: "quotation", status: "All", start: 0, page_length: 50 },
					callback: (response) => resolve(response.message || {}),
					error: (error) => reject(new Error(error?.message || "Could not load selling records")),
				});
			})
	);
	return Array.isArray(result.rows) ? result.rows : [];
}

async function fixtureSalesInvoices(page) {
	const rows = await page.evaluate(
		(prefix) =>
			new Promise((resolve, reject) => {
				frappe.call({
					method: "frappe.client.get_list",
					args: {
						doctype: "Sales Invoice",
						filters: [["remarks", "like", `${prefix}%`]],
						fields: ["name", "retailedge_branch"],
						limit_page_length: 20,
					},
					callback: (response) => resolve(response.message || []),
					error: (error) => reject(new Error(error?.message || "Could not load Sales Invoice fixtures")),
				});
			}),
		SALES_INVOICE_FIXTURE_PREFIX
	);
	return Object.fromEntries((rows || []).map((row) => [row.retailedge_branch, row.name]));
}

async function directDocumentRead(page, doctype, name) {
	return page.evaluate(
		({ targetDoctype, targetName }) =>
			new Promise((resolve) => {
				frappe.call({
					method: "frappe.client.get",
					args: { doctype: targetDoctype, name: targetName },
					callback: (response) => resolve({ ok: true, name: response.message?.name || "" }),
					error: () => resolve({ ok: false, name: "" }),
				});
			}),
		{ targetDoctype: doctype, targetName: name }
	);
}

async function expectListScope(page, doctype, branch, { companyWide = false } = {}) {
	await expect
		.poll(() => page.evaluate(() => window.cur_list?.doctype || ""), { timeout: 20_000 })
		.toBe(doctype);
	await expect
		.poll(
			() =>
				page.evaluate(() => {
					const filters = window.cur_list?.filter_area?.get?.() || [];
					const branchFilter = filters.find(
						(filter) => Array.isArray(filter) && filter[1] === "retailedge_branch"
					);
					const companyFilter = filters.find(
						(filter) => Array.isArray(filter) && filter[1] === "company"
					);
					return {
						branch: branchFilter?.[3] || "",
						company: companyFilter?.[3] || "",
					};
				}),
			{ timeout: 20_000 }
		)
		.toEqual({ branch: companyWide ? "" : branch, company: COMPANY });
}

async function expectSalesInvoiceRows(page, { included = [], excluded = [] }) {
	await expect
		.poll(
			() => page.evaluate(() => (window.cur_list?.data || []).map((row) => row.name)),
			{ timeout: 20_000 }
		)
		.toEqual(expect.arrayContaining(included));
	const names = await page.evaluate(() => (window.cur_list?.data || []).map((row) => row.name));
	for (const name of excluded) expect(names).not.toContain(name);
}

async function openSalesInvoiceList(page, branch, expected, excluded = [], { companyWide = false } = {}) {
	await page.goto(`${BASE_URL}/app/sales-invoice`, {
		waitUntil: "domcontentloaded",
		timeout: 30_000,
	});
	await expectListScope(page, "Sales Invoice", branch, { companyWide });
	await expectSalesInvoiceRows(page, { included: expected, excluded });
}

async function openStockEntryList(page, branch, { companyWide = false } = {}) {
	await page.goto(`${BASE_URL}/app/stock-entry`, {
		waitUntil: "domcontentloaded",
		timeout: 30_000,
	});
	await expectListScope(page, "Stock Entry", branch, { companyWide });
}

test("Working Branch is a server-enforced document visibility boundary", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, RESTRICTED_USER);
	const page = await context.newPage();
	try {
		await openBusinessHub(page);

		const allowed = await allowedContexts(page);
		expect(new Set(allowed.branches || [])).toEqual(new Set([LAGOS, IKEJA]));
		expect(allowed.can_view_all_branches).toBe(false);
		const invoiceFixtures = await fixtureSalesInvoices(page);
		expect(invoiceFixtures[LAGOS]).toBeTruthy();
		expect(invoiceFixtures[IKEJA]).toBeTruthy();

		await switchBranch(page, LAGOS);
		const lagosRows = await sellingRows(page);
		expect(lagosRows.length).toBeGreaterThan(0);
		expect(lagosRows.every((row) => row.branch === LAGOS)).toBe(true);
		await openSalesInvoiceList(page, LAGOS, [invoiceFixtures[LAGOS]], [invoiceFixtures[IKEJA]]);

		await switchBranch(page, IKEJA);
		await page.reload({ waitUntil: "domcontentloaded", timeout: 30_000 });
		const ikejaRows = await sellingRows(page);
		expect(ikejaRows.length).toBeGreaterThan(0);
		expect(ikejaRows.every((row) => row.branch === IKEJA)).toBe(true);
		const ikejaDocument = ikejaRows[0].name;
		await openSalesInvoiceList(page, IKEJA, [invoiceFixtures[IKEJA]], [invoiceFixtures[LAGOS]]);

		await switchBranch(page, LAGOS);
		await page.reload({ waitUntil: "domcontentloaded", timeout: 30_000 });
		const crossBranchRead = await directDocumentRead(page, "Quotation", ikejaDocument);
		expect(crossBranchRead.ok).toBe(false);
		const crossBranchInvoiceRead = await directDocumentRead(page, "Sales Invoice", invoiceFixtures[IKEJA]);
		expect(crossBranchInvoiceRead.ok).toBe(false);

		// This restricted persona is intentionally kept inside RetailEdge's
		// product experience for stock operations rather than being granted the
		// advanced native Stock Entry Desk solely for this acceptance test.
		await page.goto(`${BASE_URL}/app/stock-entry`, {
			waitUntil: "domcontentloaded",
			timeout: 30_000,
		});
		await page.getByRole("heading", { name: "Business Hub", exact: true }).first().waitFor({
			state: "visible",
			timeout: 20_000,
		});
	} finally {
		await context.close();
	}
});

test("company-wide users can deliberately broaden from one Branch to All Branches", async ({ browser }) => {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context, GLOBAL_USER);
	const page = await context.newPage();
	try {
		await openBusinessHub(page);
		const allowed = await allowedContexts(page);
		expect(allowed.can_view_all_branches).toBe(true);
		expect(new Set(allowed.branches || [])).toEqual(
			new Set(["RetailEdge RC3 Lagos", "RetailEdge RC3 Ikeja", "RetailEdge RC3 Abuja"])
		);
		const invoiceFixtures = await fixtureSalesInvoices(page);
		expect(invoiceFixtures[LAGOS]).toBeTruthy();
		expect(invoiceFixtures[IKEJA]).toBeTruthy();

		await switchBranch(page, LAGOS);
		const lagosRows = await sellingRows(page);
		expect(lagosRows.length).toBeGreaterThan(0);
		expect(lagosRows.every((row) => row.branch === LAGOS)).toBe(true);
		await openSalesInvoiceList(page, LAGOS, [invoiceFixtures[LAGOS]], [invoiceFixtures[IKEJA]]);
		await openStockEntryList(page, LAGOS);

		await switchAllBranches(page);
		await openBusinessHub(page);
		const allRows = await sellingRows(page);
		const branches = new Set(allRows.map((row) => row.branch).filter(Boolean));
		expect(branches.has(LAGOS)).toBe(true);
		expect(branches.has(IKEJA)).toBe(true);
		await expect(page.locator(".retailedge-topbar-branch-trigger strong")).toHaveText("All Branches", {
			timeout: 20_000,
		});

		await openSalesInvoiceList(
			page,
			"",
			[invoiceFixtures[LAGOS], invoiceFixtures[IKEJA]],
			[],
			{ companyWide: true }
		);
		await openStockEntryList(page, "", { companyWide: true });
	} finally {
		await context.close();
	}
});