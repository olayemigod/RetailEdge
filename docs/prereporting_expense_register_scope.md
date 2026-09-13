# Pre-reporting Expense Register read-scope contract

## Business goal

Expense Register context, option searches, paginated rows, summaries and exports may expose Cashier Expenses only inside the current reader's authorised Company and operational Branch scope. Client-supplied defaults and filters remain selections, never authority.

## B4B7 scope

This slice covers Expense Register metadata context, Branch and Expense Category option searches, paginated register reads, summary cards and bounded exports. It does not change expense creation, submission, review, approval, rejection, reopening, ledger readiness, posting, dashboard composition or reporting capabilities.

## Company contract

- Company is mandatory before any Branch, Expense Category or Cashier Expense data search can run.
- The current reader must have native read permission for the selected Company.
- Cashier Expense rows, summaries and exports never fall back to a cross-company read.
- Company option searches remain permission-aware Frappe list reads.

## Branch contract

- The shared Cashier Expense read-scope applicator is authoritative for row, summary and export filters.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established legacy User Permission/default/Branch Profile compatibility fallback.
- Unrestricted readers retain company-wide blank-Branch reads and Branch options.
- A restricted reader with one allowed Branch and a blank Branch resolves to that Branch.
- A restricted reader with multiple allowed Branches and a blank Branch reads only their allowed union.
- A restricted reader with zero active Branches receives an impossible row predicate and no Branch options.
- An explicit Branch outside the current reader's allowed Branches fails closed.
- A stale or unauthorised default Branch is not reflected into the initial context.

## Data and safety boundaries

- Paginated rows, aggregate cards and exports reuse the same authoritative query-filter builder.
- Cashier-only readers remain restricted to their own Cashier Expense rows after Company/Branch scope is applied.
- Branch and Expense Category options use permission-aware, bounded `frappe.get_list` reads.
- Expense Category selection remains limited to active global categories or categories belonging to the selected Company.
- Page size, date range and export row limits remain unchanged.
- No Cashier Expense, Category, Company, Branch, accounting or stock document is mutated.
- No reporting feature is introduced by this slice.

## Manual QA checklist

1. Restricted reader with one Branch: initial context resolves to that Branch and rows, cards and export contain only it.
2. Restricted reader with multiple Branches: initial Branch remains blank, Branch options contain only the allowed union and a blank read contains only that union.
3. Restricted reader with zero active Branches: Branch options are empty and register/export return no rows.
4. Explicit unauthorised Branch: server rejects both register and export requests.
5. Stale unauthorised Branch default: initial context does not select it.
6. Different Company without native Company read permission: server rejects the request.
7. Missing Company/default: non-Company option search and register/export do not execute.
8. Unrestricted manager: blank Branch retains company-wide results and Branch options.
9. Cashier-only reader: cashier identity remains self-scoped and hidden as before.
10. Confirm no source document changes after context, option, page or export reads.
