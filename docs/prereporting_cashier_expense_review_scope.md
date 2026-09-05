# Pre-reporting Cashier Expense Review scope contract

## Business goal

Cashier Expense Review rows, summaries, charts, pages and exports may expose Cashier Expenses only inside the current reader's authorised Company and operational Branch scope. Client-supplied Company and Branch filters remain selections, never authority.

## B4B10 scope

This slice consolidates the native Cashier Expense Review report and the EdgeSuite Expense Review page/export on the hardened Cashier Expense read authority delivered in B4B4. It removes the native report's residual legacy Branch pre-filter. It does not change expense calculations, review decisions, approval, rejection, reopening, ledger readiness, posting, navigation or reporting capabilities.

## Company and Branch contract

- `get_cashier_expenses_for_daily_audit()` remains the single row-query authority for the native report, EdgeSuite page and EdgeSuite export.
- The authority validates native Cashier Expense read permission before querying.
- Company resolves from the explicit selection or the current reader's Company default.
- A non-global reader without an explicit or default Company fails closed.
- A global reader retains the established companyless compatibility path.
- Branch Assignment history is authoritative when it exists; the established legacy User Permission/default/Branch Profile fallback remains available only when assignment history does not exist.
- An explicit unauthorised Branch is rejected.
- A restricted blank Branch resolves to its single allowed Branch, the allowed union, or an impossible predicate for zero active Branches.
- An unrestricted blank Branch remains Company-wide.

## Data and safety boundaries

- Native report rows, totals, chart and summary are derived from the same scoped row set.
- EdgeSuite pagination, summary and bounded export reuse one scoped dataset builder.
- Posting-ready filtering remains an in-memory presentation filter applied after the authorised row query.
- Date presets, date validation, columns, calculations, chart composition, totals and row limits remain unchanged.
- Review action endpoints and Cashier Expense mutation functions are not routed through the read-scope applicator or otherwise changed.
- No Cashier Expense, Company, Branch, accounting or stock document is mutated by a read path.
- No reporting feature is introduced by this slice.

## Manual QA checklist

1. Restricted reader with one Branch: native report, EdgeSuite page and export contain only that Branch.
2. Restricted reader with multiple Branches and a blank Branch: all three surfaces contain only the allowed union.
3. Restricted reader with zero active Branches: all three surfaces return no expense rows.
4. Explicit unauthorised Branch: native report, page and export requests fail closed.
5. Non-global reader without an explicit/default Company: all three surfaces fail before reading Cashier Expenses.
6. Unrestricted manager with a selected Company and blank Branch: all three surfaces retain Company-wide results.
7. Global reader using the established companyless compatibility path: the native report behavior remains unchanged.
8. Posting-ready, review-status and date filters produce matching native/page/export subsets inside the authorised scope.
9. Confirm summaries, charts and totals contain only values derived from visible rows.
10. Confirm no source document changes after report, page or export reads.
