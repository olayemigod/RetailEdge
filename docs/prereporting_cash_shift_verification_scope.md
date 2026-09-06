# Pre-reporting Cash Shift Verification read-scope contract

## Business goal

Cash Shift Verification may expose Daily Sales Audit rows and their derived cash position only inside the current reader's authorised Company and operational Branch scope. A selected Cashier, POS Profile, shift or client-supplied Branch remains a business filter, never an authority source.

## B4B8 scope

This slice covers Cash Shift Verification context defaults, Branch/Cashier/POS Profile option searches, the Daily Sales Audit-backed dataset, bounded pagination/export and child reads derived from scoped audit rows. It does not change Daily Sales Audit review actions, cash formulas, Cash Deposit semantics, invoice verification state, provider composition or any mutation workflow.

## Company and permission contract

- Company is mandatory before a Cash Shift dataset or non-Company option search can run.
- The current reader must have native read permission for both the selected Company and RetailEdge Daily Sales Audit.
- The legacy report engine enforces the same authority when invoked directly, not only through the EdgeSuite page.
- Company options remain permission-aware Frappe list reads.

## Branch contract

- Cash Shift Verification reuses the hardened Daily Sales Audit query-scope applicator.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established legacy User Permission/default/Branch Profile compatibility fallback.
- Unrestricted readers retain company-wide blank-Branch reads.
- A restricted reader with one allowed Branch and blank Branch resolves to that Branch.
- A restricted reader with multiple allowed Branches and blank Branch reads only their allowed union.
- A restricted reader with zero active Branches receives an impossible predicate and no Branch, Cashier or POS Profile options.
- An explicit Branch outside the current reader's allowed Branches fails closed.
- A selected Cashier, POS Profile or shift cannot replace the current reader as the access principal.

## Option and child-read boundaries

- Branch options continue through the bounded, Company-aware operational Branch query.
- Cashier and POS Profile candidates are returned only when they occur in Daily Sales Audit rows inside the resolved scope.
- Deposit totals receive only opening shifts from the scoped audit rows plus the selected Company.
- Invoice verification counts receive only Daily Sales Audit names from the scoped audit rows, and invoice reads remain bounded by those audit child rows.

## Preserved behavior

- Expected Cash, Cash Variance and status calculations are unchanged.
- The 1,000-row dataset guard, 100-row page limit and 20-result option limit are unchanged.
- Page and export endpoints reuse the same bounded dataset builder.
- The existing shared export-action gate may require a restricted multi-Branch reader to select one Branch before invoking the same bounded export builder.
- No Daily Sales Audit, Payment Entry, Sales Invoice, POS shift or verification record is mutated.
- Reporting development remains blocked.

## Manual QA checklist

1. Restricted reader with one Branch: blank context resolves to it and page/export contain only that Branch.
2. Restricted reader with multiple Branches: blank context stays blank and the page contains only the allowed union; where the shared export-action gate requires it, select one authorised Branch before exporting.
3. Restricted reader with zero active Branches: all operational options are empty and page/export return no rows.
4. Explicit unauthorised Branch: server rejects page, export and dependent option searches.
5. Unrestricted manager: blank Branch retains company-wide behavior.
6. Missing or unreadable Company: operational search and dataset do not execute.
7. Reader without Daily Sales Audit read permission: context, searches, page and export are rejected.
8. Cashier and POS Profile options: no values outside the resolved audit scope are returned.
9. Compare expected cash, deposits, variance, statuses, invoice counts, pagination and export with pre-hardening results inside an authorised scope.
10. Confirm no source document changes after context, search, page or export reads.
