# RIR2F3F14 — Purchase Reporting Native-Detail Containment

## Goal

Preserve Purchase Register and Supplier Payables as EdgeSuite operational reporting surfaces while preventing users without final Native Desk capability from escaping into native ERPNext invoice, supplier, return, DocType, or Report routes.

## Context

`PurchaseReportingReport.vue` already receives `navigation.access.can_use_native_desk` and stores it in the fail-closed `canUseNativeDesk` capability. The existing EdgeSuite supplier-payment flow is also already owned by `SimplePaymentDialog`, while its explicit native Payment Entry fallback is separately guarded by `canUseNativeDesk`.

The remaining gap is narrower: report invoice/supplier/return cells and menu DocType/Report routes can still invoke native Desk without applying the final capability.

## Scope

- `retailedge/public/js/purchase_reporting/PurchaseReportingReport.vue`
- focused contract tests for native-detail and navigation containment
- this contract document

## Out of Scope

- purchase report calculations or ageing logic
- supplier outstanding-balance semantics
- supplier-payment posting or Payment Entry construction
- branch/company scope
- purchase invoice lifecycle rules
- native ERPNext permissions
- accounting/GL behavior
- schema, migration, patch, or data changes
- Professional Purchasing redesign

## Implementation Requirements

1. Reuse the existing fail-closed `canUseNativeDesk` capability loaded from `navigation.access.can_use_native_desk`.
2. Keep the EdgeSuite `payment_action` operational when Native Desk is unavailable.
3. Native invoice, return-against, and supplier cells must only be presented as clickable when `canUseNativeDesk` is true.
4. `openReportCell()` must still process the EdgeSuite supplier-payment action first, then fail closed before any native document route when Native Desk is unavailable.
5. `handleNavigation()` must block DocType and Report handoffs when Native Desk is unavailable while allowing permitted EdgeSuite Page/URL navigation to retain current behavior.
6. Preserve the existing Native Payment fallback guard.
7. Do not modify backend reporting, accounting, supplier-payment, branch, or document lifecycle semantics.

## Safety Rules

- ERPNext remains authoritative for Purchase Invoice, Supplier, Payment Entry and accounting truth.
- No submitted accounting document may be mutated by this slice.
- Frontend containment does not replace existing backend/Frappe permissions.
- Do not weaken or remove existing supplier-payment or report-scope checks.
- Do not introduce a new payment or purchasing model.

## Tests Required

Focused contract tests must verify:

- `canUseNativeDesk` remains fail closed and sourced from final navigation access context;
- native report-cell clickability is conditional on Native Desk capability;
- the EdgeSuite `payment_action` remains clickable independently of Native Desk capability;
- native report-cell handoffs fail closed;
- DocType/Report menu handoffs fail closed;
- native Payment Entry fallback remains guarded;
- no backend or migration file is required for this slice.

## Expected Deliverables

- focused contract documentation
- focused regression test
- smallest Vue correction
- exact-head governed CI evidence

## Freeze Rule

Mark F3F14 `CODE-FROZEN / QA-PENDING` only after Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI, and governed EdgeSuite UI Candidate Compatibility pass on the exact implementation head. Browser/persona QA remains a separate freeze requirement.
