# RIR2G2G21 — Sales Reporting Dependent Customer and Salesperson Option Scope

## Goal

Make shared RetailEdge Sales reporting Customer and Salesperson selectors context-aware without changing the underlying reports, forecasts, accounting truth or ERPNext master ownership.

## Gap

The shared `search_sales_reporting_options` endpoint receives Company and Branch context, but:
- Customer search reads the full permission-visible Customer master;
- Salesperson search reads the full permission-visible Sales Person master.

This allows irrelevant choices from outside the selected sales Company/Branch scope. The report itself remains safe because submitted Sales Invoice reads are Branch-scoped, but the form guidance is weaker than the ProcessEdge smart-form contract.

## Required contract

### Customer
- Customer options must originate from permission-filtered submitted Sales Invoices in the selected Company/operational Branch scope.
- When the caller supplies a date window, use it.
- Customer master read permission remains required before returning the Link option.
- Search remains bounded to `MAX_LINK_RESULTS`.
- Customer Opportunity Intelligence intentionally does not date-limit the selector so customers visible only in the prior comparison period are not hidden; Company/Branch scope still applies.

### Salesperson
- Salesperson options must be derived only after permission-filtered submitted Sales Invoice parent names are known.
- Sales Team child rows may then be read only for those permitted parents.
- Sales Person master read permission and enabled status remain required.
- The parent scan remains bounded by the existing `MAX_INVOICE_SCAN_ROWS`; if exceeded, fail with a narrow-scope message rather than silently omit options.
- Sales reporting pages pass their current date range.
- Sales Forecast passes the already-resolved historical window returned by its existing forecast dataset; no forecast calendar algorithm is duplicated.

### Frontend cascade
- Selecting a new Company in shared Sales Reporting clears Customer, Customer label, Salesperson, Branch and Warehouse dependent values.
- Selecting a new Branch clears Customer, Customer label, Salesperson and Warehouse.
- Clearing Branch may retain Customer/Salesperson because scope broadens from one Branch to all permitted Branches; this is not a stale-invalid combination.

## Safety

- No report calculation, Sales Invoice query semantics, forecasting algorithm, return treatment, cost/profit visibility, accounting or submitted-document behavior changes.
- No Customer/Sales Person master mutation.
- No new role or permission.
- No Branch Assignment precedence change.
- No raw SQL, `ignore_permissions`, manual database commit, or broad client-side preload.
- Existing Item/Item Group/Warehouse selectors remain unchanged.
- Salesperson Performance Dashboard option search is out of scope; this slice covers the shared Sales reporting/forecast/intelligence selector only.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Tests

- Company/Branch/date option scope delegates to the existing operational Branch authority.
- Customer choices originate from permission-aware Sales Invoice parents then permission-aware Customer masters.
- Salesperson choices read Sales Team only after permitted Sales Invoice parents are known.
- restricted-zero/invalid Branch behavior continues through `_invoice_branch_scope`.
- frontend callers pass date windows where authoritative.
- Company/new-Branch selection clears stale Customer/Salesperson values.
- no report or forecast calculation contract changes.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
