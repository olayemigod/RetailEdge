# RIR2F3F21 — Transaction Workspace Operational Ownership Reconciliation

## Goal

Reconcile Transaction Workspace with the EdgeSuite ownership contracts already frozen in RIR2F1 and RIR2F2, without creating another selling, purchasing, stock or accounting engine.

The workspace predates those ownership slices. It still describes and opens Sales Order, Delivery Note, Purchase Order and Purchase Receipt as ordinary native ERPNext full-form workflows even though Professional Selling and Professional Purchasing now own the routine RetailEdge paths.

## Existing Gap

Before F3F21:

- Sales Order and Delivery Note creation/read actions still fell through to generic native ERPNext routes.
- Purchase Order and Purchase Receipt creation/read actions still fell through to generic native ERPNext routes.
- generic DocType/Report shell navigation could open native Desk without checking the final EdgeSuite Desk Access capability.
- POS Opening / Closing shortcuts were exposed as ordinary actions even though they are native-provider administration/shift surfaces.
- Sales Invoice and Stock Transfer child-dialog native fallbacks were not explicitly bound to the final Transaction Workspace access capability.
- the Transaction Workspace documentation still described pre-RIR2 native ownership.

This is a composition/presentation defect, not a reason to rebuild the underlying ERPNext workflows.

## Ownership Contract

1. Sales Invoice remains the existing guided Transaction Workspace entry; everyday read/manage delegates to Professional Selling.
2. Purchase Invoice remains the existing guided Transaction Workspace entry; everyday read/manage delegates to Purchase Register.
3. Stock Transfer remains the existing guided Transaction Workspace entry.
4. Sales Order and Delivery Note delegate routine create/read management to Professional Selling when that final Page is present for the current user.
5. Purchase Order and Purchase Receipt delegate routine create/read management to Professional Purchasing when that final Page is present for the current user.
6. If an EdgeSuite owner Page is unavailable, an authorised Native Desk user may still use the native ERPNext compatibility path. An EdgeSuite-only user must fail closed rather than receive a disguised native route.
7. Transaction Workspace reads `navigation.access.can_use_native_desk` from the final Business Hub context. DocType/Report menu navigation, generic native create/read helpers, and child-dialog native fallbacks require that capability.
8. POSNext/ERPNext POS launch ownership is unchanged. Native POS Opening/Closing shortcuts are shown only as explicit Advanced actions when Native Desk is allowed.
9. No backend transaction engine is added. Existing Professional Selling, Professional Purchasing, guided invoice/stock services, ERPNext permissions and document lifecycles remain authoritative.
10. The Stock Movement History parity hold remains unchanged. F3F21 must not promote `stock-movement-history` or substitute a non-equivalent stock read surface.

## Page-availability Safety

Transaction Workspace uses the final permission-aware Business Hub navigation composition to decide whether the relevant EdgeSuite owner Page is actually available.

It does not assume that a user with DocType create permission automatically has Page permission. If the owner Page is absent:

- Native Desk-capable users retain the compatibility fallback.
- EdgeSuite-only users are not shown a dead native create/view action.

This preserves the existing RIR2 rule that Page permissions and ERPNext permissions remain authoritative and that UI composition must not broaden business authority.

## Scope

Runtime:
- `retailedge/public/js/transaction_workspace/TransactionWorkspace.vue`

Tests:
- `retailedge/tests/test_rir2f3f21_transaction_workspace_operational_ownership_reconciliation_contract.py`
- existing Transaction Workspace source-contract tests remain applicable.

Documentation:
- this decision record.
- `docs/transaction_workspace_posnext.md` is reconciled with the current ownership model.

## Out of Scope

- new Sales Order, Delivery Note, Purchase Order or Purchase Receipt editors;
- Purchase Receipt serial/batch/quality/subcontracting expansion;
- Stock Movement History promotion or parity work;
- POSNext offline/runtime redesign;
- ERPNext POS lifecycle redesign;
- accounting, GL, Stock Ledger, valuation, pricing, tax or workflow changes;
- Company/Branch authority changes;
- schema, patch, migration or data changes;
- Business Hub redesign;
- reporting expansion.

## Safety Rules

- ERPNext remains the document, accounting, stock, pricing, tax and workflow source of truth.
- Do not mutate submitted documents.
- Do not bypass Frappe/ERPNext permissions or Page permissions.
- Do not use native Desk availability as permission to make native routes ordinary RetailEdge navigation.
- Keep existing EdgeSuite owners canonical when they are permission-available.
- Preserve native compatibility only as an explicit advanced fallback.
- Preserve POSNext provider and offline boundaries.
- Preserve the Stock Movement History parity hold.

## Tests Required

Focused source contracts must verify:

- final `can_use_native_desk` is fail-closed in Transaction Workspace;
- Sales Order/Delivery Note delegate to Professional Selling;
- Purchase Order/Purchase Receipt delegate to Professional Purchasing;
- Purchase Invoice read/manage remains Purchase Register;
- Sales Invoice/Stock Transfer guided creation remains in place;
- generic native create/read and DocType/Report routes require Native Desk;
- native POS Opening/Closing shortcuts require Native Desk and are labelled Advanced;
- owner Page absence retains native fallback only for Native Desk-capable users;
- no `stock-movement-history` promotion is introduced.

## Freeze Rule

F3F21 may freeze only when RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and governed EdgeSuite UI Candidate Compatibility all pass on the same exact SHA.

Manual browser/persona QA remains part of the consolidated RIR2E acceptance and is not claimed by this slice.
