# RIR2F3F22 — Cash Movement Native Detail Containment

## Goal

Keep Cash Movement as the RetailEdge EdgeSuite read/control surface while removing its remaining ordinary-user escapes into native ERPNext payment and voucher forms.

This is an ownership and presentation containment slice only. It does not change Cash Movement accounting data, classification, totals, filters, pagination, export, Company scope or Branch scope.

## Gap at F3F21 freeze

Cash Movement already reads posted ERPNext General Ledger Cash/Bank movement through the hardened B4B11 scope contract, but its frontend still had three independent native-Desk paths:

1. every voucher number was always clickable and opened its native ERPNext/Frappe Form;
2. the header **Payments** action always opened the native Payment Entry list even though RIR2F3F6 established Payment Management as the normal RetailEdge Payments owner;
3. generic DocType/Report navigation from the page did not independently enforce final `can_use_native_desk`.

The metadata fallback also called the base `edgesuite_ui` context rather than the hooked final `master_experience` context.

## Ownership Contract

1. Cash Movement remains read-only and continues to use the existing EdgeSuite report provider.
2. Final `navigation.access.can_use_native_desk` is fail-closed in the component.
3. Voucher numbers are clickable only when Native Desk is allowed.
4. `openReportCell` and `openSource` independently refuse native form navigation when Native Desk is unavailable.
5. **Payments** routes to EdgeSuite `payment-management` when that final permission-aware Page is present.
6. If Payment Management is unavailable, only a Native Desk-authorised user receives the explicit **Advanced: Payments in ERPNext** fallback.
7. An EdgeSuite-only user with no permitted Payment Management Page receives no dead/native Payments action.
8. Generic DocType/Report navigation from Cash Movement also requires Native Desk.
9. The fallback navigation context is the hooked final `retailedge.master_experience.get_retailedge_business_hub_context`, so access and final route composition are evaluated consistently.

## Scope

Runtime:
- `retailedge/public/js/cash_movement/CashMovementReport.vue`

Tests:
- `retailedge/tests/test_rir2f3f22_cash_movement_native_detail_containment_contract.py`
- existing Cash Movement tests remain authoritative for read/accounting behavior.

Documentation:
- this record.

## Explicitly Unchanged

No Cash Movement backend file is changed.

The following remain untouched:

- `retailedge/cash_movement.py`;
- report SQL and query preparation;
- GL attribution;
- movement classification;
- summary calculations;
- account filtering;
- pagination and export limits;
- B4B11 Company/Branch permission logic;
- Payment Entry creation/submission;
- payment allocation or reconciliation;
- Sales/Purchase Invoice lifecycle;
- General Ledger or Payment Ledger posting.

ERPNext General Ledger remains the accounting truth.

The B4B11 Branch/read-scope contract remains unchanged.

## Safety Rules

- Do not create a second cash ledger or payment ledger.
- Do not mutate GL Entry or submitted accounting documents.
- Do not broaden Company or Branch scope.
- Do not infer Native Desk permission from roles; use final EdgeSuite access context.
- Do not make native ERPNext routes ordinary RetailEdge navigation merely because the document is readable.
- Preserve Payment Management as the normal RetailEdge payment owner where permission-available.
- Preserve Frappe/ERPNext document permissions on any advanced native handoff.

## Tests Required

Focused source contracts must prove:

- final access context is used and defaults fail closed;
- voucher drill-through is not clickable for EdgeSuite-only users;
- direct voucher open handlers are defensively gated;
- Payments prefers `payment-management`;
- native Payment Entry fallback requires Native Desk and is explicitly advanced;
- generic DocType/Report navigation requires Native Desk;
- no Cash Movement backend/accounting/scope file is part of the slice.

## Freeze Rule

Freeze F3F22 only when RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and governed EdgeSuite UI Candidate Compatibility all pass on the same exact SHA.

Manual browser/persona QA remains part of consolidated RIR2E acceptance and is not claimed here.
