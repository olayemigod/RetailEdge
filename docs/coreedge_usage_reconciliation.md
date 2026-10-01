# RetailEdge Usage Reconciliation

## Goal

Provide a safe operator surface for CoreEdge sales-usage records that are still Pending Finalize or Needs Review.

The page is a management/review surface. It does not alter Sales Invoice, POS Invoice, GL, stock, payment, or wallet records.

## Route

`/app/usage-reconciliation`

Navigation:

`Review & Approvals → Usage Reconciliation`

Visible only to:

- System Manager;
- RetailEdge Manager / RetailEdgeManager;
- RetailEdge Auditor / RetailEdgeAuditor.

Auditors are read-only.

## Data source

The page reads `RetailEdge CoreEdge Quota Operation` through the permission-aware API:

`retailedge.coreedge_sales_quota.get_sales_quota_review`

Queries use `frappe.get_list`, not `frappe.get_all`, and are bounded to 500 rows maximum.

Filters:

- Status;
- Source DocType;
- Company;
- Branch.

The response surfaces:

- Pending Finalize count;
- Needs Review count;
- Finalized count;
- current bounded result count;
- truncation warning.

## Retry rules

The only mutation exposed by the page is:

`retailedge.coreedge_sales_quota.retry_sales_quota_review`

The endpoint:

- requires HTTP POST;
- requires System Manager or RetailEdge Manager role;
- requires read permission on the exact quota operation;
- requires an existing CoreEdge reservation reference;
- never mutates the source Sales Invoice/POS Invoice;
- calls the existing governed finalization service.

A reservation-backed Needs Review record may move directly to Finalized if CoreEdge confirms finalization.

It does not move back to Pending Finalize.

## Unreserved fail-open rows

A `FAIL_OPEN_UNRESERVED` record has no CoreEdge reservation.

The page explicitly marks it as:

`Manual commercial reconciliation is required.`

There is no retry button for such a row.

This prevents a UI action from pretending an unreserved sale has been centrally reconciled.

## Status governance

Allowed engine transitions:

- Pending Finalize → Pending Finalize;
- Pending Finalize → Finalized;
- Pending Finalize → Needs Review;
- Needs Review → Needs Review;
- Needs Review → Finalized;
- Finalized → Finalized only.

Normal users still cannot create, edit, delete, or directly change quota-operation status.

## Source document access

Each row includes an Open Source action that routes to the original Sales Invoice or POS Invoice.

The page never writes to that document.

## EdgeSuite UI

The page uses EdgeSuite UI components for:

- page header;
- filter bar;
- link fields;
- dropdowns;
- summary cards;
- status badges;
- loading/error/empty states.

Company and Branch filters use permission-aware Frappe Link search.

Branch search cascades from the selected Company.

## Out of scope

This page does not:

- mark an unreserved row resolved;
- create a replacement CoreEdge reservation;
- override a CoreEdge quota decision;
- refund cancelled sales quota;
- delete quota history;
- edit submitted invoices;
- alter accounting;
- expose CoreEdge credentials;
- expose the page to cashiers or ordinary branch operators.

## Tests

Focused suite:

`retailedge.tests.test_usage_reconciliation`

Coverage includes:

- auditor read-only access;
- manager retry permission;
- unreserved Needs Review rows showing manual reconciliation;
- non-governance role denial;
- retry delegation to governed finalization;
- retry denial without reservation;
- permission-aware `get_list`;
- POST-only mutation;
- Needs Review → Finalized engine transition;
- Needs Review cannot return to Pending Finalize;
- governance-only Page roles;
- no manual status override in frontend;
- Review & Approvals navigation entry.

## Migration

Run normal:

`bench --site <site> migrate`

No historical quota record is changed by migration.

## Next step

After this page passes the standard RetailEdge validation gates, the remaining operational gap is explicit reconciliation for `FAIL_OPEN_UNRESERVED` rows.

That should not be implemented as a simple Mark Resolved button. It needs a central CoreEdge reconciliation contract that can record after-the-fact commercial usage with reason, actor, audit history, and a clear policy for already-exhausted quotas.
