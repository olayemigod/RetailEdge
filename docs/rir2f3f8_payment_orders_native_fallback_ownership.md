# RIR2 F3F8 — Payment Orders native fallback ownership

## Goal
Keep everyday supplier payment inside RetailEdge EdgeSuite UI while preserving ERPNext Payment Order as an advanced accounting/treasury workflow.

## Ownership decision

### Everyday supplier payment — RetailEdge owned
The operational path remains:

1. Suppliers & Payables → Supplier Payables.
2. Select a submitted Purchase Invoice with outstanding balance.
3. Open the guided `pay-supplier` flow.
4. Create/review the ERPNext Payment Entry draft.
5. Submit through RetailEdge's standard supplier-payment submit service.

ERPNext remains the accounting source of truth. RetailEdge must not mutate submitted Purchase Invoices, GL Entries, Payment Ledger Entries, or balances directly.

### Payment Orders — advanced ERPNext fallback
ERPNext Payment Order is not the ordinary supplier-payment entry screen. It groups initiated Payment Requests or submitted Payment Entries for company-bank/treasury processing and can create downstream payment records for its governed references.

Therefore `Suppliers & Payables → Payment Orders` remains a native ERPNext DocType route, but it is an advanced fallback only:

- hidden when EdgeSuite access says native Desk is unavailable;
- restricted to the existing finance-role contract;
- still subject to ERPNext read permission;
- never used as the default supplier-payment route.

## Scope
- Add native-fallback metadata to the existing Payment Orders navigation item.
- Reuse the F3F7 `can_use_native_desk` navigation gate.
- Add source-contract tests proving Supplier Payables remains the everyday payment owner.

## Out of scope
- No new Payment Order page.
- No rewrite or proxy of ERPNext Payment Order.
- No Payment Entry accounting changes.
- No Purchase Invoice mutation.
- No workflow, schema, patch, role-profile, branch-scope, or migration changes.
- No change to Payment Reconciliation F3F7.

## Safety
- ERPNext Payment Entry submit remains authoritative for standard supplier payments.
- ERPNext Payment Order remains authoritative for advanced payment-order processing.
- Native fallback exposure is governed by both EdgeSuite native-Desk access and ERPNext permissions.

## Manual QA deferred
Manual browser/persona QA remains deferred unless executed separately. Automated governed gates are required before this slice can be frozen.
