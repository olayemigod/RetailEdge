# Pre-reporting Cashier Expense Dashboard Branch Scope Contract

## Purpose

B4B3 aligns the RetailEdge Cashier Expense Dashboard read boundary with the Branch Assignment-aware operating scope already established by B3 and reused by B4A, B4B1 and B4B2.

## Scope authority

The dashboard uses `retailedge.operating_context.get_operational_branch_scope()` as its Branch read-scope authority.

The existing precedence remains unchanged:

- global RetailEdge branch-access users are unrestricted;
- when Branch Assignment history exists, active Branch Assignments are authoritative;
- without Branch Assignment history, the operating-scope helper retains the legacy User Permission/default/Branch Profile compatibility fallback.

A restricted user with zero active permitted Branches is never interpreted as unrestricted.

## Dashboard read rules

For Cashier Expense Dashboard reads:

- Company is required; when it is omitted, the user's default Company is used when available;
- restricted + explicit Branch requires that Branch to be in the active permitted set;
- restricted + exactly one permitted Branch and blank Branch resolves to that Branch;
- restricted + multiple permitted Branches and blank Branch reads only the union of those permitted Branches;
- restricted + zero permitted Branches uses an impossible Branch filter and returns no expense rows;
- unrestricted + blank Branch preserves the existing company-wide behavior;
- POS Profile, Cashier and date filters continue to apply inside the effective Company/Branch scope.

The dashboard continues to return the same totals, status buckets, posting-readiness counts, daily-audit review counts, top-cashier/category summaries and recent-expense payload shape. Only the read scope changes.

## Security boundary fixed

The previous dashboard used the legacy `get_branch_query_filters()` compatibility helper. That helper accepts an explicit Branch before calculating the user's active operational Branch scope and represents an empty allowed-branch list ambiguously unless strict mode is requested.

B4B3 removes that helper from this dashboard surface. Explicit Branch requests are revalidated against active Branch scope and restricted zero-Branch users fail closed.

## Non-goals

B4B3 does not:

- change Cashier Expense creation, approval, rejection, posting or cancellation;
- change expense totals, status interpretation or daily-audit calculations;
- change Branch Assignment records or their precedence;
- alter the global legacy `get_branch_query_filters()` helper for unrelated compatibility paths;
- broaden roles, DocType permissions, Page permissions or EdgeSuite routing;
- begin reporting-development work.

Remaining operational read services continue as separate B4 audit slices until the pre-reporting Branch-read boundary is complete.
