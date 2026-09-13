# RIR2G2G24 — Discount & Sales Quality Date-Aware Dependent Option Scope

## Goal

Complete the shared Sales reporting smart-form contract for Discount & Sales Quality by passing the page's selected reporting period into Customer/Salesperson option search and clearing period-dependent selections when the date range changes.

## Gap

G2G21 made the shared `search_sales_reporting_options` endpoint Company/Branch/date aware. The active Discount & Sales Quality page still calls it with only Company, Branch and Item Group.

As a result, Customer and Salesperson choices are Company/Branch scoped but can include records that have no submitted sales in the selected reporting period.

## Required contract

- Pass `from_date` and `to_date` from the active Discount & Sales Quality filters to shared option search.
- From Date or To Date change marks Customer and Salesperson selections stale and clears them.
- Company and Branch cascades remain unchanged.
- Item Group, Item and Warehouse behaviour remain unchanged.
- Continue using G2G21's shared backend scope; do not add another Sales Invoice option-search engine.

## Out of scope

- Discount/sales-quality calculations, transactional cost/margin logic, returns, thresholds, pagination, export, native-detail containment or report SQL.
- Customer Opportunity Intelligence, whose all-time Company/Branch selector behaviour is intentionally preserved for comparison-period discoverability.
- Any accounting, stock, Sales Invoice, Customer or Sales Person mutation.

## Safety

- Frontend-only correction.
- No role/permission or Branch Assignment change.
- No server API or schema change.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
