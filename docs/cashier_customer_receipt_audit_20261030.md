# RetailEdge Cashier Customer Receipt Audit — 2026-10-30

## Trigger

Manual cashier acceptance on PR #239 showed submitted Sales Invoices with `Unpaid` / `Overdue` status and positive outstanding amounts, but Professional Selling did not expose a payment action. The existing action resolver intentionally required generic `Payment Entry` Create permission, while the canonical `RetailEdgeCashier` role intentionally has no generic Payment Entry authority.

## Platform baseline and native truth

The frozen PR validation application set remains Frappe 16.52.0 / ERPNext 16.51.1 / pinned EdgeSuite UI. Current public v16 research was checked before this change; dependencies are not upgraded inside the defect correction.

ERPNext remains authoritative for customer receivables and payment posting:

- a submitted Sales Invoice carries the authoritative outstanding amount;
- customer settlement is represented by an ERPNext `Payment Entry` with a Sales Invoice reference;
- Payment Entry validation, GL posting, Payment Ledger posting, Mode of Payment validation and accounting hooks remain authoritative;
- Payment Reconciliation is for allocating already-recorded payments and is not a substitute for recording a new cashier receipt;
- the native `get_payment_entry` helper is unsuitable as the direct cashier boundary because it explicitly requires generic Payment Entry Create permission before constructing the document.

ERPNext itself contains narrowly privileged source-bound payment creation patterns (for example Payment Request flows). That establishes that a constrained server-side exception can be valid when it remains tied to an exact authorised source document and still posts through the native Payment Entry document lifecycle.

## Industry pattern

Mature POS products separate the ability to take a customer payment from broad accounting administration. A point-of-sale/cashier persona normally receives task-specific checkout/payment authority at an assigned location while ledger configuration, account masters, unrestricted payment journals and financial administration remain separately governed.

RetailEdge therefore should not solve this defect by assigning the cashier Accounts User/Accounts Manager or generic Payment Entry permissions.

## Chosen design

Professional Selling exposes **Receive Payment** for a cashier only when the row is:

- a Sales Invoice;
- submitted (`docstatus = 1`);
- not a Return / Credit Note;
- currently outstanding by more than the accounting tolerance.

The action opens a focused EdgeSuite **Receive Payment** page bound to that exact Sales Invoice. The page does not expose the generic Payment Entry list/form.

### Server authority

`retailedge.cashier_customer_receipt` revalidates every consequential condition server-side:

1. current user has canonical/legacy `RetailEdgeCashier` authority;
2. Sales Invoice exists and is readable through normal Frappe/RetailEdge permission scope;
3. invoice is submitted, non-return and still outstanding;
4. invoice Company equals the active Working Company;
5. invoice Branch is permitted and matches the active Working Branch where selected;
6. restricted users fail closed when historical Branch attribution is absent;
7. initial cashier receipt supports company-currency invoices only;
8. payment-term-allocation invoices remain on the managed payment path;
9. Mode of Payment must be enabled and map to an active Company Bank/Cash account in the same currency;
10. payment amount must be positive and cannot exceed the latest invoice outstanding;
11. Bank receipts require a reference number/date;
12. active Payment Entry Workflow fails closed rather than being bypassed.

### Review and concurrency

The first action is **Review Payment**, not posting. The preview returns the authoritative invoice identity, customer, Company, Branch, outstanding amount, amount received, remaining outstanding, Mode of Payment and posting/reference details.

Preview also returns the invoice `modified` value and current outstanding amount. Posting:

- locks the exact Sales Invoice row with `FOR UPDATE`;
- reloads/revalidates the invoice;
- requires the reviewed `modified` and outstanding values still to match;
- rebuilds the payment from the current source document;
- therefore rejects stale/double/concurrent submissions instead of silently posting a duplicate receipt.

### Narrow permission exception

The canonical cashier continues to have **no generic Payment Entry Read/Create/Write/Submit permission** and no Account read permission.

At the final posting boundary only, RetailEdge constructs one standard `Payment Entry` bound to the validated Sales Invoice and validated Company payment account, sets `ignore_permissions` / account-permission bypass only on that server-side document operation, then calls normal `insert` and `submit` lifecycle methods.

This is intentionally narrow:

- no generic Payment Entry search/list/form access;
- no supplier payments;
- no Internal Transfer;
- no unallocated customer advances;
- no multi-invoice allocation;
- no Journal Entry creation;
- no direct GL Entry or Payment Ledger Entry creation;
- no direct mutation of Sales Invoice outstanding;
- no manual database commit.

Existing Payment Entry `validate` and `before_submit` hooks still execute, including RetailEdge Branch attribution and cash-custody validation. ERPNext remains the ledger truth.

## UX contract

For an eligible invoice, Professional Selling → **More** contains **Receive Payment**.

The receipt page shows:

- Sales Invoice and Customer;
- Company and Working Branch context;
- current invoice outstanding;
- Posting Date;
- searchable Mode of Payment;
- Payment Amount (partial receipt allowed);
- Remaining After Payment;
- bank reference details when applicable.

**Review Payment** produces an informed read-only review. **Post Payment** is a second explicit action and confirmation. On success the user sees the receipt reference, amount received and latest remaining outstanding, then returns to Professional Selling.

## Validation requirements

1. Role-exact cashier remains denied generic Payment Entry permissions.
2. Unpaid/Overdue/Partly Paid submitted Sales Invoice exposes Receive Payment.
3. Draft, Paid, Cancelled and Return/Credit Note rows do not expose the constrained action.
4. Preview rejects overpayment, invalid payment modes, multi-currency and Branch/Company mismatch.
5. Posting proves Sales Invoice row lock + reviewed-state comparison.
6. Payment posting uses standard Payment Entry lifecycle and does not mutate ledgers/invoice outstanding directly.
7. Clean browser acceptance opens Receive Payment from an unpaid invoice as `browser-cashier@example.com`.
8. Exact-head lint, CI, upgrade, EdgeSuite compatibility and browser-persona gates must all pass before PR #239 is marked Ready.
