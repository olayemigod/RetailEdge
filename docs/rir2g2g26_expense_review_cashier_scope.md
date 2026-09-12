# RIR2G2G26 — Expense Review Branch/Date-Aware Cashier Option Scope

## Goal

Make the Expense Review Cashier selector context-aware so users only see valid cashiers evidenced by RetailEdge Cashier Expense records inside the currently authorised Company, operational Branch and review date window.

## Gap

The Expense Review dataset already reads Cashier Expense records through the hardened `get_cashier_expenses_for_daily_audit` path, which applies current Company/Branch read scope.

The selector does not follow that authority:
- it loads all enabled permission-visible Users;
- the page sends only Company to option search;
- Company/Branch/date changes can leave a stale Cashier selected.

This is a smart-form guidance gap, not a review-workflow or accounting defect.

## Required contract

### Scope authority
- Reuse `apply_cashier_expense_read_scope` as the authoritative Company/Branch scope.
- Company is required for scoped Cashier search.
- Explicit Branch outside current RetailEdge operating scope fails closed through the existing read-scope contract.
- Restricted blank Branch continues to resolve to the existing permitted single branch / permitted union / impossible zero-branch predicate.

### Cashier option evidence
- Candidate Cashier identities originate only from permission-aware `RetailEdge Cashier Expense` reads inside the authorised Company/Branch/date scope.
- From Date and To Date, when supplied, constrain `expense_date`.
- Search remains bounded.
- User master read permission and enabled state remain authoritative before a Cashier option is returned.
- Blank date range preserves the Company/Branch-scoped behaviour.

### Frontend cascade
- Option search passes Company, Branch, From Date and To Date.
- Selecting a new Company clears Branch and Cashier.
- Selecting or clearing Branch clears Cashier.
- Changing From Date or To Date clears Cashier because its validity is period-dependent.
- Cashier display label is cleared whenever the Cashier value is cleared.

## Out of scope

- Expense Review dataset calculations, review status logic, posting-ready logic, include/exclude/clarify mutations, report provider, sorting, pagination, export or native-detail containment.
- Expense Category option scope.
- Cashier Expense posting, accounting or workflow semantics.
- Role, permission or Branch Assignment changes.

## Safety

- No submitted-document mutation.
- No `ignore_permissions`.
- No manual database commit.
- No broad User preload.
- Existing Cashier Expense read scope remains authoritative.
- Browser/persona acceptance remains deferred to consolidated RIR2E.

## Tests

- Cashier option filters reuse `apply_cashier_expense_read_scope`.
- Company/Branch/date predicates are applied before Cashier Expense option evidence is read.
- Cashier candidates originate from scoped Cashier Expense rows, then are rechecked through enabled permission-aware User master search.
- Frontend passes Branch/date context and clears stale Cashier on Company/Branch/date changes.
- Existing review mutation endpoints remain untouched.

## Freeze gate

Freeze only when Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and EdgeSuite UI Candidate Compatibility all pass on one exact head.
