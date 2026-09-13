# RIR2G2G22 — Salesperson Performance Dependent Customer and Salesperson Option Scope

## Goal

Make the active Salesperson Performance dashboard Customer and Salesperson selectors follow the same authorised Company, operational Branch and reporting-date context as the dashboard data, without changing salesperson allocation, KPI, invoice, item or accounting truth.

## Gap

The active `SalespersonPerformanceDashboardV2.vue` sends only Company to `search_salesperson_dashboard_options`.

As a result:
- Customer search reads the full permission-visible Customer master.
- Salesperson search reads the full permission-visible enabled Sales Person master.
- Branch and date changes can leave a previously selected Customer or Salesperson stale for the new reporting scope.

The dashboard aggregate itself is already Company/Branch/date scoped, so this is a smart-form guidance gap rather than a reporting-truth defect.

## Required contract

### Context
- Customer and Salesperson option searches require a validated Company.
- Explicit Branch is revalidated through `resolve_salesperson_performance_read_scope`.
- Blank Branch follows the existing unrestricted / permitted-union / single-branch auto-resolution / restricted-zero behaviour.
- When a date window is supplied, both dates are required and From Date must not exceed To Date.

### Customer
- Candidate Customers originate only from submitted Sales Invoices in the authorised Company/Branch/date scope.
- Customer master read permission remains authoritative before a Link option is returned.
- Search remains bounded to `MAX_LINK_RESULTS`.

### Salesperson
- Permission-filtered submitted Sales Invoice parent names are resolved first.
- The parent scan is bounded by `MAX_INVOICE_SCAN_ROWS`; oversized searches fail with a narrow-scope message.
- Sales Team child rows are read only for those scoped invoice parents.
- Sales Person master read permission and enabled status remain authoritative.
- Synthetic dashboard identities such as Unallocated Sales Team and Unassigned Salesperson are not Link options.

### Frontend cascade
- Search requests pass Company, Branch, From Date and To Date.
- Selecting a new Company clears Branch, Customer and Salesperson.
- Selecting a new Branch clears Customer and Salesperson.
- Changing the reporting date range clears Customer and Salesperson because their validity depends on the period.
- Clearing Branch may retain Customer/Salesperson because the scope broadens to all permitted Branches.

## Out of scope

- Item and Item Group option scoping.
- Salesperson allocation rules.
- Dashboard calculations, SQL aggregation, pagination, export or print.
- Native Desk containment already frozen in G2G19.
- Any Sales Invoice, Sales Team, Customer, Sales Person, accounting, stock or payment mutation.

## Safety

- No role, permission or Branch Assignment precedence change.
- No `ignore_permissions`.
- No manual database commit.
- No submitted-document mutation.
- Existing dashboard Company/Branch authority remains the single scope authority.
- Browser/persona QA remains deferred to consolidated RIR2E.

## Tests

- Company/Branch/date option scope reuses the existing Salesperson Performance read-scope contract.
- Customer options originate from scoped submitted invoice parents before Customer master search.
- Salesperson options resolve scoped invoice parents before Sales Team rows and Sales Person master search.
- restricted-zero / missing Branch field fails closed.
- Frontend passes Branch/date context and clears stale Customer/Salesperson values on narrowing parent changes.
- Item/Item Group option behaviour remains unchanged.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
