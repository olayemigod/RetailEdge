# RetailEdge Advanced Payment Management

## Dependency / PR topology

This work is intentionally stacked on `agent/professional-selling-invoice-completion` (PR #41).

Branch creation predecessor head:

`b9d4fbc61be04b9c2171a936e17e371ef364aa53`

Do not retarget this work to `main` until PR #41 has merged or the stack has been explicitly reconciled.

## Business goal

RetailEdge must support customer money received before an invoice exists and later apply that money safely to Sales Invoices. The experience should be simpler than the native accounting screens without introducing a second accounting ledger.

Supported foundation workflows:

1. Record a customer advance as a draft ERPNext Payment Entry with no invoice references.
2. Submit/review the Payment Entry through the standard ERPNext document lifecycle.
3. Discover submitted customer receipts that still have `unallocated_amount > 0`.
4. Show only advances eligible for the selected Sales Invoice by Customer, Company, currency and RetailEdge branch context.
5. Apply all or part of an advance through ERPNext Payment Reconciliation.
6. Leave the unused Payment Entry amount available for future invoices.

## Source of truth

RetailEdge does **not** maintain a custom customer-deposit balance.

Authoritative records remain:

- Payment Entry for the receipt and unapplied amount;
- Payment Reconciliation for post-receipt allocation;
- Payment Ledger Entry / General Ledger generated and reposted by ERPNext;
- Sales Invoice for invoice/outstanding state.

RetailEdge never writes Sales Invoice outstanding amounts or GL rows directly.

## Accounting safety contract

- New advance receipts are created as **draft** Payment Entries only. RetailEdge does not auto-submit them.
- Applying an existing submitted advance requires native Payment Reconciliation permission.
- The guided application path calls ERPNext `PaymentReconciliation.get_unreconciled_entries()`, `allocate_entries()` and `reconcile()` rather than updating submitted accounting rows itself.
- Customer and Company must match between Payment Entry and Sales Invoice.
- Allocation cannot exceed the Payment Entry's current unapplied amount or the invoice's current outstanding amount.
- The latest ERPNext unreconciled snapshots are fetched again immediately before reconciliation to protect against stale UI data.
- Branch mismatches are blocked where branch context exists.
- The guided path is initially company-currency only.
- Separate advance-account accounting and multi-currency cases are redirected to full ERPNext Payment Reconciliation until they receive dedicated coverage.

## Backend APIs

### `retailedge.advanced_payments.get_customer_advance_context`

Returns an operational summary and authoritative unallocated Payment Entry rows.

### `retailedge.advanced_payments.list_customer_advances`

Permission-aware bounded query for submitted `Receive` Payment Entries belonging to Customers with remaining `unallocated_amount`.

### `retailedge.advanced_payments.create_customer_advance_draft`

Creates an unallocated **draft** customer Payment Entry. Invoice references are deliberately rejected on this route so the intent cannot be confused with normal allocated receipt entry.

### `retailedge.advanced_payments.get_sales_invoice_advance_context`

Returns invoice-specific eligible advances and outstanding/available values.

### `retailedge.payment_application.apply_customer_advance`

Applies a chosen amount through ERPNext Payment Reconciliation after permission, company, customer, branch, account, currency and current-balance checks.

## Backward compatibility

No standard ERPNext DocType is overridden. No submitted invoice is mutated by RetailEdge. No database patch, fixture or custom balance table is introduced by this foundation.

The existing `guided_payment.py` behaviour remains unchanged, including its requirement for at least one invoice reference. The new advance path is separate so existing simple-payment contracts and tests are preserved.

## Tests

Focused tests cover:

- authoritative submitted/unallocated Payment Entry filtering;
- bounded advance lookup;
- draft advance creation without invoice reference rows;
- rejection of accidental invoice allocations on the advance-entry route;
- invoice/customer/company scoping;
- multi-currency fallback;
- reconciliation delegation;
- partial allocation;
- amount bounds;
- customer/company mismatch rejection;
- separate advance-account fallback.

## Manual QA

1. Create a company-currency customer advance from RetailEdge.
2. Confirm a standard draft Payment Entry is created with no invoice references.
3. Submit the Payment Entry in ERPNext and confirm the amount is unallocated.
4. Open a submitted Sales Invoice for the same Customer/Company/Branch.
5. Confirm the advance appears with its latest available amount.
6. Apply only part of the advance.
7. Confirm ERPNext reduces Sales Invoice outstanding and Payment Entry unallocated amount correctly.
8. Confirm the remaining advance is still available for a second invoice.
9. Attempt a wrong-customer, wrong-company and wrong-branch application; each must be blocked.
10. Attempt a multi-currency or separate-advance-account case; RetailEdge must direct the user to full Payment Reconciliation.
11. Verify Accounts permissions: a user without reconciliation rights must not be able to apply an advance.
12. Verify cancellation/amendment behaviour remains governed by ERPNext.

## Next slices

After this backend/accounting foundation passes CI and QA:

1. EdgeSuite Payment Management page and invoice `Apply Advance` UX.
2. Customer Advance Register / Unallocated Payment Register / Advance Utilisation reporting.
3. Mixed payment UX (existing advance + new receipt + residual receivable).
4. Sales Order advance linkage where ERPNext semantics allow it.
5. Project receipt context as a dependent stacked slice for Project Funds Management.
