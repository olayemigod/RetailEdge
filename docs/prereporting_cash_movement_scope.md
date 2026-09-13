# Pre-reporting Cash Movement read-scope contract

## Business goal

Cash Movement context, Branch options, GL rows, summary cards, pagination and export may expose posted Cash/Bank ledger movement only inside the current reader's authorised Company and operational Branch scope. Client-supplied defaults and filters remain selections, never authority.

## B4B11 scope

This slice replaces Cash Movement's legacy empty-list Branch convention with the operational Branch scope introduced in B3. It covers the EdgeSuite Cash Movement context, Branch option search, shared SQL query preparation, paginated rows, summary aggregates and bounded export. It does not change GL attribution, movement classification, calculations, account selection, voucher links, page composition, accounting documents or reporting capabilities.

## Company and Branch contract

- Company remains mandatory before Cash Movement data, Branch options or Cash/Bank Account options can load.
- The current reader must retain native Company read permission and an allowed Cash Movement role.
- Branch Assignment history is authoritative when it exists.
- Users without Branch Assignment history retain the established legacy User Permission/default/Branch Profile compatibility fallback.
- An unrestricted reader with a blank Branch retains the Company-wide view, including unattributed adjustments.
- A restricted reader with one or more active Branches and a blank Branch reads only the allowed Branch union.
- A restricted reader with zero active Branches receives an impossible SQL predicate and no Branch options.
- An explicit Branch outside the current reader's active scope fails closed.
- A stale restricted default Branch is removed from initial context; a single unambiguous active Branch is selected instead.

## SQL and safety boundaries

- Row, summary, pagination and export endpoints reuse `_prepare_query()` and its authoritative Branch predicate.
- Branch values are bound as SQL parameters and never interpolated into the query.
- A restricted scope fails closed when no supported voucher Branch attribution field exists, because no attributed row can match the permitted Branch values.
- Posted ERPNext GL Entry and Account data remain the accounting truth.
- Cash/Bank account constraints, cancelled-row handling, movement classification, date limits, paging and export limits remain unchanged.
- No GL Entry, Payment Entry, Sales Invoice, POS Invoice, Purchase Invoice, Account, Company or Branch document is mutated.
- No reporting feature is introduced by this slice.

## Manual QA checklist

1. Restricted reader with one Branch: context, rows, summaries and export contain only that Branch.
2. Restricted reader with multiple Branches and a blank Branch: rows, summaries and export contain only the allowed union.
3. Restricted reader with zero active Branches: Branch options are empty and rows/export return no movements.
4. Explicit unauthorised Branch: page and export requests fail closed.
5. Stale unauthorised default Branch: context removes it and selects only a single unambiguous active Branch.
6. Unrestricted legacy reader: blank Branch remains Company-wide and includes unattributed adjustments.
7. Different Company without native read permission: context/query is rejected.
8. Cash/Bank Account outside the selected Company: query is rejected.
9. Confirm page and export totals reconcile to the same authorised GL population for identical filters.
10. Confirm no accounting or source document changes after context, option, page or export reads.
