# RIR2G2 — EdgeSuite UI Completion Reconciliation Audit

## Goal

Reconcile RetailEdge's final ordinary-user UI after Phase 1 Readiness Hardening and Phase 2 Core Operational Workflows. Phase 3 must remove accidental Native Desk dependencies and incomplete EdgeSuite ownership without rebuilding deliberate Advanced ERPNext specialist workflows.

## Classification

Every ordinary-user surface or handoff is classified as:

- `EDGESUITE_OWNED`
- `INTENTIONAL_ADVANCED_NATIVE`
- `UI_COMPLETION_BLOCKER`
- `DEFERRED_NON_MVP`

## Initial Composition Findings

### Confirmed EdgeSuite-owned areas

Repository evidence already shows governed EdgeSuite ownership for:

- Business Hub guided selling, payment, cash movement, expense and stock-draft entry;
- Professional Selling;
- Professional Purchasing;
- Payment Management and standard customer/supplier payment completion;
- Expense Register, Business Expenses and Cashier Expense review;
- Stock Movement History Page and Stock Position;
- Bank Matching and Banking Readiness;
- Customer Receivables and Supplier Payables;
- Daily Sales Audit and Cash Shift Verification;
- standard Customer/Supplier/Item Quick Entry;
- Setup consolidation for RetailEdge-managed setup DocTypes.

These must not be rebuilt merely because native ERPNext compatibility routes still exist in the repository.

### Deliberate advanced boundaries

The Phase-2 closure explicitly retains Advanced ERPNext/system-of-record ownership for specialist cases including:

- complex Stock Entry and Serial/Batch stock transfer completion;
- final Stock Reconciliation posting beyond the guided draft path;
- Payment Reconciliation and complex treasury/allocation;
- Payment Request / Dunning specialist review;
- POS Opening/Closing Shift lifecycle;
- complex accounting/stock reports and exceptional document lifecycle cases.

Phase 3 must make these boundaries explicit and capability-gated, not silently convert them into ordinary EdgeSuite operations.

## G2A blocker — native navigation survives EdgeSuite-only composition

The base navigation builder currently hides only entries explicitly marked `mode = "native_fallback"` when `can_use_native_desk = false`.

Many raw DocType and Query Report routes are not marked with that mode. Examples include:

- Customer, Item, Warehouse, Batch, Serial No;
- native sales/pricing/assets/service masters;
- Accounts Receivable/Payable and accounting reports;
- Stock Balance, Stock Ledger and detailed stock reports;
- review/audit Query Reports;
- Budget, Cost Center and Journal Entry;
- POS Opening / Closing after runtime resolution.

Therefore an EdgeSuite-only user can still receive native Desk routes despite the intended product model.

The final `master_experience` composition can also append native Project and project-report routes after the base access filter, so base filtering alone is insufficient.

The Business Hub client currently routes any received DocType or Report without independently checking final Native Desk capability.

### Classification

**UI_COMPLETION_BLOCKER**

### Safe correction

RIR2G2A must:

1. filter raw `DocType` and `Report` navigation entries for EdgeSuite-only users at the base navigation builder;
2. repeat final containment after `master_experience` promotions/appends;
3. retain Page and approved URL navigation;
4. preserve all native DocType/Report navigation for Native-Desk-capable users;
5. add a client-side fail-closed guard so stale/tampered DocType/Report navigation cannot route when `nativeFallbackEnabled = false`;
6. add the same defensive guard to Business Hub `openNative*` handlers;
7. not remove underlying ERPNext permissions, DocTypes or Reports;
8. not reclassify deliberate advanced-native functionality as EdgeSuite-owned.

## Remaining RIR2G2 audit after G2A

After G2A freezes, continue the audit for:

- ordinary quick actions that create a draft but require another surface/user for completion;
- table sorting and consistent sort affordances;
- responsive table behavior;
- loading/error/empty states;
- date presentation consistency;
- Link-field filtering and parent→dependent cascade;
- permission-safe option searches;
- stale dependent values;
- document identity/status usability where native detail links are hidden;
- per-page Native Desk detail/fallback containment.

Do not start Phase 4 Business Hub expansion or Phase 5 Reporting until Phase 3 is reconciled code-complete.
