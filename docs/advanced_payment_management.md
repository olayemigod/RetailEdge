# RetailEdge Advanced Payment Management

## Dependency / PR topology

This work is intentionally stacked on `agent/professional-selling-invoice-completion` (PR #41).

Branch creation predecessor head:

`b9d4fbc61be04b9c2171a936e17e371ef364aa53`

Do not retarget this work to `main` until PR #41 has merged or the stack has been explicitly reconciled.

## Business goal

RetailEdge supports customer money received before an invoice exists and later applies that money safely to Sales Invoices. The experience is simpler than the native accounting screens without introducing a second accounting ledger.

Implemented workflows:

1. Record a customer advance as a draft ERPNext Payment Entry with no invoice references.
2. Review and submit the Payment Entry through the standard ERPNext document lifecycle.
3. Discover submitted customer receipts that still have `unallocated_amount > 0`.
4. Show only advances eligible for a selected Sales Invoice by Customer, Company, currency and RetailEdge Branch context.
5. Apply all or part of an advance through ERPNext Payment Reconciliation.
6. Leave the unused Payment Entry amount available for future invoices.
7. Operate these workflows from the EdgeSuite Payment Management page.
8. Apply an eligible advance directly from a submitted Sales Invoice using `Payments → Apply Customer Advance`.
9. Review current open advances using the RetailEdge Customer Advance Register.

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
- Branch mismatches are blocked where Branch context exists.
- The guided write path is company-currency only.
- Separate advance-account accounting and multi-currency cases are redirected to full ERPNext Payment Reconciliation until they receive dedicated coverage.
- Native Payment Entry remains available in the Money menu as the full accounting fallback.

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

Applies a chosen amount through ERPNext Payment Reconciliation after permission, Company, Customer, Branch, account, currency and current-balance checks.

## EdgeSuite Payment Management

The standard Frappe Page `payment-management` is the operational entry point for customer advances.

It provides:

- Company, Branch and Customer filtering;
- current available-advance total and count;
- bounded listing of authoritative Payment Entries;
- Record Advance dialog that creates a draft Payment Entry;
- Apply to Invoice dialog that revalidates invoice eligibility before reconciliation;
- links back to Payment Entry documents;
- native EdgeSuite navigation and theme behaviour.

The page is promoted into the governed RetailEdge **Money** navigation only when the Page exists and the user has permission to read it.

## Sales Invoice integration

A submitted, non-return Sales Invoice with positive outstanding can show `Payments → Apply Customer Advance` when at least one eligible advance exists.

The action:

- fetches current invoice-specific advance context;
- displays only eligible Payment Entries;
- supports full or partial application;
- validates the amount in the browser for usability;
- revalidates all accounting conditions on the server;
- delegates the write to ERPNext Payment Reconciliation;
- reloads the invoice after successful reconciliation.

If the optional RetailEdge advance context cannot be loaded, standard ERPNext Sales Invoice remains usable.

## Customer Advance Register

`RetailEdge Customer Advance Register` is a standard Script Report backed by Payment Entry.

Filters:

- Company;
- Branch;
- Customer;
- From Date;
- To Date.

It shows current submitted Customer receipts with a positive `unallocated_amount`, including:

- receipt amount;
- already allocated portion;
- currently available advance;
- Branch;
- currency;
- Mode of Payment;
- payment reference.

The server scan is bounded to 2,000 rows and respects Payment Entry, Company and Branch access.

The register deliberately excludes fully consumed receipts. It is a **current open-advance register**, not a custom historical wallet or reconstructed advance-provenance ledger.

## Backward compatibility

No standard ERPNext DocType is overridden. No submitted invoice is mutated directly by RetailEdge. No database accounting patch, fixture or custom balance table is introduced.

The existing `guided_payment.py` behaviour remains unchanged, including its normal allocated-receipt workflow. The advance path is separate so existing simple-payment contracts are preserved.

Normal app deployment / `bench migrate` is required to install the standard Page and Report definitions.

## Automated tests

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
- separate advance-account fallback;
- Payment Management Page and bundle contract;
- guarded Sales Invoice action contract;
- governed Money navigation while retaining Payment Entry fallback;
- current-open Customer Advance Register contract and bounded source-of-truth query.

## Manual QA gate

Before merge readiness:

1. Deploy the PR stack to a test site and run `bench migrate` plus asset build.
2. Open Money → Payment Management and verify role-aware visibility.
3. Create a company-currency customer advance and confirm a standard draft Payment Entry is created with no invoice references.
4. Submit the Payment Entry in ERPNext and confirm the amount is unallocated.
5. Open a submitted Sales Invoice for the same Customer/Company/Branch and verify `Payments → Apply Customer Advance` appears.
6. Apply only part of the advance.
7. Confirm ERPNext reduces Sales Invoice outstanding and Payment Entry unallocated amount correctly.
8. Apply the remaining advance to a second invoice and confirm the remaining balance behaves correctly.
9. Re-test using stale browser data after another allocation and confirm the server rejects an excessive/stale allocation.
10. Attempt wrong-Customer, wrong-Company and wrong-Branch applications; each must be blocked.
11. Attempt a multi-currency or separate-advance-account case; RetailEdge must direct the user to full Payment Reconciliation.
12. Verify a user without reconciliation rights cannot apply an advance.
13. Verify the Customer Advance Register totals and links against the underlying Payment Entries.
14. Verify light mode, dark mode and mobile layout for Payment Management and the Sales Invoice dialog.
15. Verify cancellation/amendment behaviour remains governed by ERPNext.

## Later slices

The following are intentionally not part of this PR:

1. Mixed-payment UX combining an existing advance, a new receipt and residual receivable in one guided transaction.
2. Sales Order-specific advance UX beyond ERPNext's existing semantics.
3. Multi-currency guided reconciliation.
4. Separate advance-party-account guided reconciliation.
5. Historical advance-utilisation analytics where provenance can be derived reliably from ERPNext accounting records.
6. Project receipt context and Project Funds Management as a dependent stacked slice after this payment foundation is stable.
