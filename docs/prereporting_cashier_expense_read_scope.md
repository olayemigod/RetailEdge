# Pre-reporting Cashier Expense Read Scope Contract

## Purpose

B4B4 hardens the remaining Cashier Expense summary, totals, variance and Daily Audit read family after B4B3 hardened the dedicated Cashier Expense Dashboard.

This slice is read-only. It does not change Cashier Expense creation, submission, approval, rejection, reopening, Daily Audit review actions, ledger readiness or posting semantics.

## Scope authority

Cashier Expense read filters use `retailedge.operating_context.get_operational_branch_scope()` through the shared `cashier_expense_read_scope` applicator.

The established precedence remains unchanged:

- global RetailEdge branch-access users are unrestricted;
- when Branch Assignment history exists, active Branch Assignments are authoritative;
- without Branch Assignment history, legacy User Permission/default/Branch Profile behaviour remains the compatibility fallback;
- a restricted user with zero active permitted Branches is never interpreted as unrestricted.

## Read rules

For dictionary-based summary, totals, variance and Daily Audit reads:

- explicit Company is used when supplied;
- otherwise the user's default Company is used when available;
- restricted + explicit Branch requires that Branch to be actively permitted;
- restricted + one permitted Branch and blank Branch resolves to that Branch;
- restricted + multiple permitted Branches and blank Branch scopes to their union;
- restricted + zero permitted Branches uses an impossible Branch predicate and returns no records;
- unrestricted + blank Branch preserves company-wide behaviour;
- non-global users cannot omit Company when no default Company can be resolved.

For existing Frappe list-filter callers:

- supported Company/Branch equality filters keep list form;
- the authoritative Branch predicate is appended when Branch is blank;
- explicit Branch is revalidated server-side;
- non-equality or contradictory Company/Branch predicates fail closed instead of bypassing scope.

Global advanced users without a Company continue to retain the pre-existing cross-company compatibility behaviour.

## Permission boundary

Some Cashier Expense reads use `frappe.get_all`, which does not itself enforce normal DocType read permissions. B4B4 therefore requires `RetailEdge Cashier Expense` read permission before the shared scope applicator permits those reads to proceed.

Branch Assignment scope is additional to the existing DocType role permissions; it does not broaden those permissions.

## Surfaces covered

B4B4 covers the filter boundaries used by:

- Cashier Expense status summary;
- Cashier Expense totals, including the existing Frappe list-filter compatibility call;
- Cashier Expense variance rows and totals;
- Cashier Expense Daily Audit rows, totals and review summary.

## Non-goals

B4B4 does not:

- change the B4B3 Cashier Expense Dashboard baseline;
- change Cashier Expense calculations or status interpretation;
- change approval/rejection/reopen or Daily Audit mutation functions;
- change accounting documents, posting readiness or ledger-posting behaviour;
- change Branch Assignment precedence or records;
- alter the global legacy `get_branch_query_filters()` contract for unrelated callers;
- modify Daily Sales Audit context resolution outside the Cashier Expense read helper it already calls;
- begin reporting development.

Daily Sales Audit and other remaining operational read surfaces stay separate B4 audit slices.
