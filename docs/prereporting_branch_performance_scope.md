# Pre-reporting Branch Performance Read Scope Contract

## Purpose

B4B2 aligns RetailEdge Branch Performance data, diagnostics and Branch filter options with the Branch Assignment-aware operating scope established in B3 and reused by B4A/B4B1.

## Scope authority

Branch Performance uses `retailedge.operating_context.get_operational_branch_scope()` as its read-scope authority.

The established precedence remains unchanged:

- global RetailEdge branch-access users are unrestricted;
- when Branch Assignment history exists, active Branch Assignments are authoritative;
- without Branch Assignment history, the operating-scope helper retains the legacy User Permission/default/Branch Profile compatibility fallback.

A restricted user with zero active permitted Branches is never interpreted as unrestricted.

## Report rules

For Branch Performance reads:

- restricted + explicit Branch requires that Branch to be in the active permitted set;
- restricted + exactly one permitted Branch and blank Branch resolves to that Branch;
- restricted + multiple permitted Branches and blank Branch reads the union of only those permitted Branches;
- restricted + zero permitted Branches uses an impossible SQL predicate and returns no report data;
- unrestricted + blank Branch preserves the current company-wide behavior.

The multi-Branch boundary is enforced inside the shared Sales Invoice and RetailEdge/ERPNext document query builders so sales, payment, cashier-expense, daily-audit and stock-activity datasets use the same permitted Branch set.

## Fallback attribution and diagnostics

Fallback resolution for legacy/unattributed Sales Invoices is also constrained by the same permitted Branch set. For a restricted user, a fallback row is excluded unless it resolves to an active permitted Branch. An unresolved fallback row is therefore not treated as safe branch data for a restricted user.

The no-data diagnostic counts now use the effective Branch scope as well, preventing company-wide diagnostic totals from leaking outside the permitted Branch set.

## Dashboard filter rules

The EdgeSuite Branch Performance Branch picker uses the same operational scope:

- restricted users see only active permitted Branches;
- restricted users with zero active Branches receive no Branch options;
- unrestricted users retain permission-aware company-wide Branch search;
- non-Company option searches recheck Company read permission server-side.

## Non-goals

B4B2 does not:

- change Gross Sales, Cash Sales, Bank Sales, expenses, expected cash, audit variance, payment-issue or review-status calculations;
- change submitted Sales Invoices, Payment Entries, stock records, audits or accounting ledgers;
- change ERPNext posting, reconciliation or document lifecycle semantics;
- change the global legacy `get_branch_query_filters()` helper used by unrelated compatibility paths;
- broaden roles, DocType permissions, Page permissions or EdgeSuite routing;
- begin reporting-development work.
