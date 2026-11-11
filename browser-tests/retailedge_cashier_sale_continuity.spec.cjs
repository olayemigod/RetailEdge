const { test, expect } = require("@playwright/test");

const BASE_URL = process.env.RETAILEDGE_BASE_URL || "http://retail-browser.localhost:8000";
const PASSWORD = process.env.RETAILEDGE_BROWSER_PASSWORD;
const CASHIER = "browser-cashier@example.com";
const BRANCH = "RetailEdge RC3 Lagos";

if (!PASSWORD) {
	throw new Error("RETAILEDGE_BROWSER_PASSWORD is required for cashier sale continuity acceptance.");
}

async function login(context) {
	const response = await context.request.post(`${BASE_URL}/api/method/login`, {
		form: { usr: CASHIER, pwd: PASSWORD },
	});
	expect(response.ok(), `login failed for ${CASHIER}`).toBeTruthy();
}

async function newCashier(browser) {
	const context = await browser.newContext({ baseURL: BASE_URL });
	await login(context);
	const page = await context.newPage();
	return { context, page };
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
		// Raw payload is preserved in assertion diagnostics below.
	}
	return { response, payload, text };
}

async function apiPost(context, page, method, form = {}) {
	const csrf = await page.evaluate(() => window.frappe?.csrf_token || "");
	expect(csrf, `Missing Frappe CSRF token for ${method}`).toBeTruthy();
	const response = await context.request.post(`${BASE_URL}/api/method/${method}`, {
		headers: { "X-Frappe-CSRF-Token": csrf },
		form,
	});
	const text = await response.text();
	let payload = {};
	try { payload = JSON.parse(text); } catch (_error) {}
	return { response, payload, text };
}

async function openProductPage(page, route, title) {
	await page.goto(`${BASE_URL}/app/${route}`, { waitUntil: "domcontentloaded", timeout: 30_000 });
	await page.getByRole("heading", { name: title, exact: true }).first().waitFor({ state: "visible", timeout: 25_000 });
	await expect(page.locator(".modal:visible")).toHaveCount(0);
}

test("cashier can review and resume an unfinished saved sale after a fresh page load", async ({ browser }) => {
	const { context, page } = await newCashier(browser);
	try {
		const drafts = await apiGet(context, "retailedge.sales_invoice_workbench.get_resumable_sales_invoice_drafts", { limit: "12" });
		expect(drafts.response.ok(), drafts.text).toBeTruthy();
		expect(Array.isArray(drafts.payload.message)).toBeTruthy();
		expect(drafts.payload.message.length).toBeGreaterThan(0);

		const seededDraft = drafts.payload.message.find((row) => row.branch === BRANCH) || drafts.payload.message[0];
		expect(seededDraft.name).toBeTruthy();
		expect(seededDraft.can_edit).toBeTruthy();

		await openProductPage(page, "make-sale", "Make Sale");
		await expect(page.getByRole("heading", { name: "Continue a saved sale", exact: true })).toBeVisible();

		const draftRow = page.locator(".unfinished-sales__row").filter({ hasText: seededDraft.name }).first();
		await expect(draftRow).toBeVisible();
		await expect(draftRow).toContainText(seededDraft.customer_name || seededDraft.customer);
		await draftRow.getByRole("button", { name: "Review", exact: true }).click();

		await expect(page.getByRole("heading", { name: `Review ${seededDraft.name}`, exact: true })).toBeVisible();
		await expect(page.getByRole("heading", { name: "Confirm the sale details", exact: true })).toBeVisible();
		await expect(page.locator(".sale-review__table thead th").filter({ hasText: /^Item$/ }).first()).toBeVisible();
		await expect(page.getByText("Amount due", { exact: true })).toBeVisible();
		await expect(page.getByRole("button", { name: "Submit Reviewed Sale", exact: true })).toBeVisible();
		await expect(page.getByRole("button", { name: "Edit Sale", exact: true })).toBeVisible();

		await page.reload({ waitUntil: "domcontentloaded" });
		await page.getByRole("heading", { name: "Make Sale", exact: true }).first().waitFor({ state: "visible", timeout: 25_000 });
		const reloadedRow = page.locator(".unfinished-sales__row").filter({ hasText: seededDraft.name }).first();
		await expect(reloadedRow).toBeVisible();
		await reloadedRow.getByRole("button", { name: "Resume Sale", exact: true }).click();
		const updateDraft = page.getByRole("button", { name: "Update Draft", exact: true });
		await expect(updateDraft).toBeVisible();
		await expect(page.getByRole("button", { name: "Cancel Edit", exact: true })).toBeVisible();

		// Acceptance must prove persistence, not merely show an Edit button.
		// Use the seeded CI-only Sales Invoice and leave it in Draft: no sale is submitted.
		const savedNote = `Cashier saved-sale persistence QA ${seededDraft.name}`;
		await page.locator(".make-sale-form textarea").fill(savedNote);
		// Keep enough on-screen diagnostic evidence to distinguish missing stock
		// context from a rejected commercial preview (without bypassing either).
		await expect.poll(async () => ({
			enabled: await updateDraft.isEnabled(),
			commercialError: (await page.locator(".sales-commercial-summary__error").allTextContents()).join(" | "),
			context: (await page.locator(".guided-invoice-context").allTextContents()).join(" | "),
		}), { timeout: 25_000 }).toMatchObject({ enabled: true, commercialError: "" });
		await updateDraft.click();
		await expect(page.locator(".make-sale-form")).toHaveCount(0, { timeout: 25_000 });
		await expect.poll(async () => {
			const persisted = await apiGet(
				context,
				"retailedge.standard_sales_invoice_completion.get_standard_sales_invoice_completion_preview",
				{ name: seededDraft.name },
			);
			if (!persisted.response.ok()) throw new Error(persisted.text);
			return {
				remarks: persisted.payload.message?.remarks,
				docstatus: Number(persisted.payload.message?.docstatus),
			};
		}, { timeout: 25_000 }).toEqual({ remarks: savedNote, docstatus: 0 });

		await page.reload({ waitUntil: "domcontentloaded" });
		await expect(page.locator(".unfinished-sales__row").filter({ hasText: seededDraft.name }).first()).toBeVisible({ timeout: 25_000 });
	} finally {
		await context.close();
	}
});

test("cashier can use the governed Professional Selling chain while accounting authority stays separate", async ({ browser }) => {
	const { context, page } = await newCashier(browser);
	try {
		const selling = await apiGet(context, "retailedge.professional_selling.get_professional_selling_context");
		expect(selling.response.ok(), selling.text).toBeTruthy();
		const invoice = await apiGet(context, "retailedge.professional_sales_invoice.get_professional_sales_invoice_capability");
		expect(invoice.response.ok(), invoice.text).toBeTruthy();
		expect(invoice.payload.message?.can_read).toBeTruthy();
		expect(invoice.payload.message?.can_create).toBeTruthy();

		const sellingDocuments = selling.payload.message?.documents || [];
		for (const doctype of ["Quotation", "Sales Order", "Delivery Note"]) {
			const document = sellingDocuments.find((row) => row.doctype === doctype);
			expect(document, `${doctype} capability missing`).toBeTruthy();
			expect(document.can_read, `${doctype} read permission missing`).toBeTruthy();
			expect(document.can_create, `${doctype} create permission missing`).toBeTruthy();
		}

		await openProductPage(page, "professional-selling", "Professional Selling");
		for (const label of ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"]) {
			await expect(page.getByRole("heading", { name: label, exact: true }).first()).toBeVisible();
		}

		const records = page.locator(".selling-records-panel");
		await expect(records).toBeVisible();
		for (const label of ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"]) {
			await expect(records.getByRole("tab", { name: label, exact: true })).toBeVisible();
		}

		const paymentContext = await apiGet(context, "retailedge.guided_payment.get_simple_payment_context", {
			intent: "receive-customer-payment",
		});
		expect(paymentContext.response.ok()).toBeFalsy();
		expect(paymentContext.text).toMatch(/Payment Entr|permission/i);
		await expect(page.getByText("Make Payment", { exact: true })).toHaveCount(0);
	} finally {
		await context.close();
	}
});

test("cashier unpaid Sales Invoice exposes the constrained Receive Payment workflow", async ({ browser }) => {
	const { context, page } = await newCashier(browser);
	try {
		const invoices = await apiGet(context, "retailedge.professional_selling.get_professional_selling_list", {
			document: "sales-invoice",
			status: "Unpaid",
			start: "0",
			page_length: "20",
		});
		expect(invoices.response.ok(), invoices.text).toBeTruthy();
		const rows = invoices.payload.message?.rows || [];
		const unpaid = rows.find(
			(row) => Number(row.docstatus || 0) === 1 && !Number(row.is_return || 0) && Number(row.outstanding_amount || 0) > 0.005
		);
		expect(unpaid, "expected a submitted unpaid cashier-visible Sales Invoice fixture").toBeTruthy();

		await openProductPage(page, "professional-selling", "Professional Selling");
		const records = page.locator(".selling-records-panel");
		const search = records.getByRole("searchbox", { name: "Search" });
		await expect(search).toBeVisible();
		await search.fill(unpaid.name);

		const invoiceRow = records.locator("tbody tr").filter({ hasText: unpaid.name }).first();
		await expect(invoiceRow).toBeVisible({ timeout: 20_000 });
		// A submitted invoice with a remaining balance must expose payment directly.
		const receivePayment = invoiceRow.getByRole("button", { name: "Receive Payment", exact: true });
		await expect(receivePayment).toBeVisible();
		await receivePayment.click();

		await expect(page).toHaveURL(new RegExp(`/cashier-customer-receipt/${unpaid.name}(?:$|[?#])`), { timeout: 20_000 });
		await expect(page.getByRole("heading", { name: "Receive Payment", exact: true })).toBeVisible({ timeout: 20_000 });
		await expect(page.getByRole("heading", { name: unpaid.name, exact: true })).toBeVisible();
		await expect(page.getByText("Invoice outstanding", { exact: true }).first()).toBeVisible();
		await expect(page.getByRole("button", { name: "Review Payment", exact: true })).toBeVisible();
	} finally {
		await context.close();
	}
});

test("cashier can post a real partial receipt linked to the exact submitted test invoice", async ({ browser }) => {
	// The browser fixture creates this invoice and its Cash mode on an
	// ephemeral CI site. Do not run this posting test on retail.local or
	// any merchant/production site.
	if (
		process.env.RETAILEDGE_CASHIER_POSTING_QA !== "ephemeral-ci-only"
		|| new URL(BASE_URL).hostname !== "retail-browser.localhost"
	) {
		test.skip(true, "Posting acceptance is restricted to an ephemeral seeded CI site.");
	}
	const { context, page } = await newCashier(browser);
	try {
		const invoices = await apiGet(context, "retailedge.professional_selling.get_professional_selling_list", {
			document: "sales-invoice", status: "Unpaid", start: "0", page_length: "30",
		});
		expect(invoices.response.ok(), invoices.text).toBeTruthy();
		const unpaid = (invoices.payload.message?.rows || []).find(
			(row) => Number(row.docstatus || 0) === 1
				&& !Number(row.is_return || 0) && Number(row.outstanding_amount || 0) > 200,
		);
		expect(unpaid, "Seeded submitted invoice with enough outstanding balance is required").toBeTruthy();

		await openProductPage(page, "professional-selling", "Professional Selling");
		const initial = await apiGet(
			context, "retailedge.cashier_customer_receipt.get_cashier_customer_receipt_context",
			{ sales_invoice: unpaid.name },
		);
		expect(initial.response.ok(), initial.text).toBeTruthy();
		expect(initial.payload.message?.branch).toBe(BRANCH);
		const outstanding = Number(initial.payload.message.invoice_outstanding);
		const modeName = "RetailEdge Browser Cash Receipt";
		const modes = await apiGet(context, "retailedge.cashier_customer_receipt.search_cashier_customer_receipt_modes", {
			sales_invoice: unpaid.name, txt: modeName,
		});
		expect(modes.response.ok(), modes.text).toBeTruthy();
		expect(modes.payload.message?.some(row => row.value === modeName)).toBeTruthy();

		const values = {
			posting_date: initial.payload.message.defaults.posting_date,
			mode_of_payment: modeName,
			amount: 100,
			reference_no: "",
			reference_date: initial.payload.message.defaults.reference_date,
		};
		const review = await apiGet(context, "retailedge.cashier_customer_receipt.preview_cashier_customer_receipt", {
			sales_invoice: unpaid.name, values: JSON.stringify(values),
		});
		expect(review.response.ok(), review.text).toBeTruthy();
		const reviewed = review.payload.message || {};
		expect(reviewed.sales_invoice).toBe(unpaid.name);
		expect(reviewed.can_post).toBe(true);
		expect(Number(reviewed.payment_amount)).toBe(100);
		expect(Number(reviewed.remaining_after_payment)).toBeCloseTo(outstanding - 100, 2);

		const posted = await apiPost(context, page, "retailedge.cashier_customer_receipt.post_cashier_customer_receipt", {
			sales_invoice: unpaid.name,
			values: JSON.stringify(values),
			expected_invoice_modified: reviewed.expected_invoice_modified,
			expected_outstanding_amount: reviewed.expected_outstanding_amount,
		});
		expect(posted.response.ok(), posted.text).toBeTruthy();
		expect(posted.payload.message?.sales_invoice).toBe(unpaid.name);
		expect(posted.payload.message?.payment_reference).toBeTruthy();
		expect(posted.payload.message?.posting_status).toBe("Posted");
		expect(Number(posted.payload.message?.payment_amount)).toBe(100);
		expect(Number(posted.payload.message?.invoice_outstanding)).toBeCloseTo(outstanding - 100, 2);

		// The second read must reflect authoritative ERPNext invoice/ledger truth,
		// not only the immediate in-memory response to the posted Payment Entry.
		const after = await apiGet(
			context, "retailedge.cashier_customer_receipt.get_cashier_customer_receipt_context",
			{ sales_invoice: unpaid.name },
		);
		expect(after.response.ok(), after.text).toBeTruthy();
		expect(Number(after.payload.message?.invoice_outstanding)).toBeCloseTo(outstanding - 100, 2);
	} finally {
		await context.close();
	}
});

test("cashier has Sales Invoice print authority and can open Document Output & Sharing", async ({ browser }) => {
	const { context, page } = await newCashier(browser);
	try {
		const outputContext = await apiGet(context, "retailedge.document_output.get_document_output_context");
		expect(outputContext.response.ok(), outputContext.text).toBeTruthy();
		const salesInvoice = (outputContext.payload.message?.documents || []).find((row) => row.key === "sales-invoice");
		expect(salesInvoice).toBeTruthy();
		expect(salesInvoice.can_read).toBeTruthy();
		expect(salesInvoice.can_print).toBeTruthy();
		expect(salesInvoice.can_email).toBeFalsy();

		await openProductPage(page, "document-output-sharing", "Document Output & Sharing");
		await expect(page.getByRole("heading", { name: "Find a permitted customer document", exact: true })).toBeVisible();
		const documentType = page.locator("#output-document-type");
		await expect(documentType).toBeVisible();
	} finally {
		await context.close();
	}
});
