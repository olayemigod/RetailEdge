# RIR2G2G19 — Salesperson Performance Native Detail Containment

## Goal

Keep the active EdgeSuite Salesperson Performance dashboard fully usable while containing native Sales Person, Customer and Sales Invoice drill-through for EdgeSuite-only users.

## Scope

- Active `SalespersonPerformanceDashboardV2.vue` runtime
- Dashboard shell DocType/Report navigation
- Allocation-detail native cells
- Sales Invoice list action

## Required contract

- The active dashboard reads `navigation.access.can_use_native_desk`.
- Shell DocType/Report navigation fails closed.
- Salesperson, customer and invoice identities remain visible, but native detail cells are clickable only with Native Desk.
- The Sales Invoices action is disabled and labelled as advanced without Native Desk.
- Cell and list handlers independently fail closed.
- Metrics, allocation truth, filters, pagination, export and print remain unchanged.
- The unmounted legacy component is not modified; the production bundle explicitly imports V2.

## Safety

- No salesperson allocation or reporting calculation changes.
- No Company/Branch scope, option-search, export, print, role or permission changes.
- No business-document mutation or shared EdgeSuite UI runtime change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only after all four governed workflows pass on one exact head.
