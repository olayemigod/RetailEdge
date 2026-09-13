# RIR2F3F19 — Sales Reporting Native-Detail Containment

## Goal

Preserve Sales by Item and Sales Invoice Register as EdgeSuite operational reporting surfaces while preventing users without final Native Desk capability from escaping into native ERPNext invoice, return, item, customer, DocType, or Report routes.

## Context

Purchase Reporting already applies the final Native Desk capability to native-detail clickability and menu handoffs under RIR2F3F14. Sales Reporting still exposes Sales Invoice, return-against, Item and Customer cells as clickable for every user and still routes DocType/Report menu items directly to native ERPNext.

This slice brings Sales Reporting to the same established ownership contract. It does not add a new sales workflow or change report data.

## Scope

- `retailedge/public/js/sales_reporting/SalesReportingReport.vue`
- focused contract test for native-detail and navigation containment
- this contract document

## Out of Scope

- sales report calculations, returns, taxes, outstanding or salesperson allocation
- report filters, export semantics, pagination or branch/company scope
- Sales Invoice lifecycle or payment handling
- Customer or Item maintenance
- native ERPNext permissions
- accounting/GL behavior
- schema, migration, patch or data changes
- Professional Selling redesign

## Implementation Requirements

1. Add fail-closed `canUseNativeDesk: false`.
2. Load final capability from `navigation.access.can_use_native_desk`.
3. Use the final master Business Hub context as the fallback navigation source.
4. Native invoice, return-against, item and customer cells must only be presented as clickable when `canUseNativeDesk` is true.
5. `openReportCell()` must fail closed before any native document route when Native Desk is unavailable.
6. `handleNavigation()` must block DocType and Report handoffs when Native Desk is unavailable while retaining permitted EdgeSuite Page/URL navigation.
7. Do not modify backend reporting, accounting, branch, export or document lifecycle semantics.

## Safety Rules

- ERPNext remains authoritative for Sales Invoice, Customer, Item and accounting truth.
- No submitted Sales Invoice or other accounting document may be mutated by this slice.
- Frontend containment does not replace backend/Frappe permissions.
- Do not weaken existing report read-scope, export, branch or company controls.
- Do not introduce a parallel customer, item or sales ledger.

## Tests Required

Focused contract tests must verify:

- `canUseNativeDesk` is fail closed and sourced from final navigation access context;
- final master Business Hub context is used for fallback navigation metadata;
- native report-cell clickability is conditional on Native Desk capability;
- native report-cell handoffs fail closed;
- DocType/Report menu handoffs fail closed;
- native Sales Invoice, Item and Customer routes remain available only behind that capability;
- no backend semantic change is required.

## Expected Deliverables

- focused contract documentation
- focused regression test
- smallest Vue correction
- exact-head governed CI evidence

## Freeze Rule

Mark F3F19 frozen only after RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI, and governed EdgeSuite UI Candidate Compatibility all pass on the same exact implementation head. Browser/persona QA remains deferred unless separately executed.
