# Pre-reporting Salesperson Performance read-scope contract

## Business goal

Salesperson Performance may aggregate submitted Sales Invoices and their ERPNext Sales Team allocations only inside the current reader's authorised Company and operational Branch scope. A salesperson, customer, item, or client-supplied Branch filter never becomes an authority source.

## B4B6 scope

This slice covers the Salesperson Performance aggregate, legacy dashboard Branch options, and current dashboard option searches. It does not change Sales Team allocation, KPI calculations, pagination, export limits, dashboard capabilities, native document permissions, or any write workflow.

## Company contract

- Company is mandatory before the raw Sales Invoice aggregate can run.
- The current reader must have native read permission for the selected Company.
- A missing Company never becomes a cross-company SQL query.
- Company option searches continue to use permission-aware Frappe list reads.

## Branch contract

- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established legacy Branch User Permission/default/profile compatibility fallback.
- Unrestricted/advanced readers retain company-wide blank-Branch reads.
- A restricted reader with one allowed Branch and a blank Branch resolves to that Branch.
- A restricted reader with multiple allowed Branches and a blank Branch reads only their allowed union.
- A restricted reader with zero active Branches receives an impossible SQL predicate and no Branch options.
- An explicit Branch outside the current reader's allowed Branches fails closed.
- If the Sales Invoice schema has no supported Branch field, a restricted read fails closed instead of becoming company-wide.

## Data and safety boundaries

- Only submitted ERPNext Sales Invoices (`docstatus = 1`) remain sales truth.
- Sales Team allocation continues to use the shared R8/R11 allocation contract.
- Sales Invoice Item and Sales Team child reads remain bounded by the already-scoped invoice names.
- Customer, Item, Item Group, and Sales Person searches remain native permission-aware master searches, but now require a validated Company context first.
- No Sales Invoice, Sales Team, Customer, Item, accounting, stock, or payment document is mutated.
- No reporting feature is introduced by this slice.

## Manual QA checklist

1. Restricted reader with one Branch: blank Branch resolves to that Branch and only its submitted invoices contribute.
2. Restricted reader with multiple Branches: blank Branch aggregates only the allowed Branch union.
3. Restricted reader with zero active Branches: Branch options are empty and the dashboard returns no invoice rows.
4. Explicit unauthorised Branch: server rejects the request.
5. Different Company without native Company read permission: server rejects the request.
6. Missing Company/default: aggregate does not execute.
7. Unrestricted manager: blank Branch retains company-wide results.
8. Compare salesperson allocation, totals, filters, pagination, print, and export with pre-hardening behaviour for an authorised scope.
9. Confirm no source document changes after dashboard, option, print, or export reads.
