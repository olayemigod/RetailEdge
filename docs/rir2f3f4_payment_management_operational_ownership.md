# RIR2F3F4 — Payment Management Operational Ownership

## Goal

Contain native ERPNext payment fallbacks so ordinary RetailEdge users remain in EdgeSuite for standard customer and supplier payment work, without prematurely removing the native Payment Entry route that is still required for advanced and generic payment-history cases.

## Context

RIR2F3F1–F3F3 established safe standard payment submission for both directions:

- customer receipts and advances can be reviewed and submitted from Payment Management;
- supplier payments can be reviewed and submitted from the shared guided payment dialog;
- both submit through ERPNext Payment Entry and preserve ERPNext accounting authority;
- complex payment shapes remain explicit Advanced ERPNext cases.

The remaining ownership gap is presentation and routing. Payment Management and Supplier Payables still contain native Payment Entry escape paths that can be visible or invoked without consistently respecting the final `can_use_native_desk` access contract. Supplier Payables also retains a legacy post-save callback that can force navigation to the native Payment Entry form.

## Decision

F3F4 is a containment slice, not the final native-route retirement slice.

When the Payment Management page is available it remains the first everyday Money surface for payment operations. Native Payment Entry and Payment Reconciliation remain available in final navigation for compatibility and advanced accounting work until RetailEdge has a complete EdgeSuite-owned generic payment-history/revisit surface for both customer and supplier payments.

The existence of a safe standard create/submit flow is not by itself sufficient reason to remove the generic native Payment Entry route.

## Implementation Contract

### Payment Management

Payment Management must:

1. consume the final master Business Hub context when the shared browser cache helper is unavailable;
2. derive `canUseNativeDesk` from `navigation.access.can_use_native_desk`;
3. show the header `Advanced ERPNext` action only when `canUseNativeDesk` is true;
4. show the reviewed-draft `Open in ERPNext` action only when `canUseNativeDesk` is true;
5. guard direct native Payment Entry navigation methods in code as well as in the template;
6. keep standard customer draft review and submission entirely in EdgeSuite;
7. never make a successful standard submit force a native Payment Entry route.

### Supplier Payables

Supplier Payables must:

1. continue to use the governed shared `SimplePaymentDialog` with `pay-supplier` intent;
2. consume the final master Business Hub context when the shared browser cache helper is unavailable;
3. derive `canUseNativeDesk` from the final access context;
4. never force a successful standard supplier payment back to the native Payment Entry form;
5. guard its explicit native Payment Entry fallback with `canUseNativeDesk`;
6. stay on Supplier Payables and refresh authoritative outstanding data after a normal saved/submit handoff.

## Navigation Contract

F3F4 does **not** remove `Payment Entry` or `Payment Reconciliation` from the Money group.

The current promotion order remains intentional:

1. `Payment Management` is promoted ahead of native `Payment Entry` when the page is available;
2. `Payment Register` may remain alongside it for read-only review;
3. native `Payment Entry` remains a compatibility/advanced fallback;
4. native `Payment Reconciliation` remains an advanced repair/reconciliation fallback.

Native peer retirement requires a later bounded slice proving that customer and supplier payment history, draft revisit, submitted-payment inspection, and required advanced handoffs are all safely covered without stranding users.

## Accounting Safety

F3F4 changes no accounting engine or document semantics.

It must not modify:

- `standard_customer_payment_submit.py`;
- `standard_supplier_payment_submit.py`;
- `guided_payment.py` accounting behavior;
- Payment Entry submission logic;
- GL Entry or Payment Ledger Entry behavior;
- invoice outstanding calculations;
- payment allocation/reconciliation calculations.

ERPNext remains source of truth. Submitted accounting documents are not mutated by this slice.

## Out of Scope

- replacing the generic Payment Entry list/history experience;
- implementing a new payment ledger;
- removing Payment Entry from final navigation;
- removing Payment Reconciliation from final navigation;
- redesigning Payment Management;
- supplier-payment reporting expansion;
- new DocTypes or schema patches;
- changes to payment posting, allocation, cancellation, write-off, or exchange-difference rules.

## Validation

Required validation on the exact F3F4 candidate head:

- focused `test_rir2f3f4_payment_management_operational_ownership_contract.py`;
- affected historical payment handoff/submit contract tests;
- full RetailEdge test suite;
- RetailEdge Theme Compatibility;
- Linters / pre-commit / Semgrep / vulnerable-dependency audit;
- clean Frappe v16 standalone CI;
- governed EdgeSuite UI Candidate Compatibility.

Manual browser/persona QA remains deferred to the consolidated QA pass and is not claimed by this checkpoint.
