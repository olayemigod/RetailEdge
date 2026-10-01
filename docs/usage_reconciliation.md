# RetailEdge Usage Reconciliation

## Goal

Give authorised RetailEdge managers and auditors a safe review queue for sales whose platform usage state is
not fully confirmed.

The user-facing surface is named **Usage Reconciliation**. Internal implementation may retain CoreEdge names,
but normal RetailEdge users do not need platform-internal terminology.

This slice is stacked on the Sales Transaction Quota integration.

## Navigation

The page is placed under:

**Operations Review → Usage Reconciliation**

It is not placed under everyday Sales, Point of Sale, Reports or Setup.

Visible roles:

- System Manager;
- RetailEdge Manager;
- RetailEdgeManager;
- RetailEdge Auditor;
- RetailEdgeAuditor.

Auditors are read-only.

Retry finalization is limited to Administrator/System Manager and RetailEdge Manager roles.

## Scope and permissions

All queue reads use `frappe.get_list`, not `frappe.get_all`.

The page reuses RetailEdge operating-context governance:

- Company must be within the user's permitted Company set;
- Company → Branch options are permission-aware;
- a selected Branch must belong to the permitted operating scope;
- restricted users with a blank Branch are limited to their allowed Branch set;
- a restricted reviewer cannot retry a branchless operation;
- when several Companies are available and there is no active/default Company, the user must choose one.

The queue is bounded and paginated.

## Filters

The page supports:

- Company;
- Branch;
- Status;
- source document type;
- search by source document, reservation reference or reason.

Statuses:

- Needs Review;
- Pending Finalize;
- Finalized;
- All.

## Summary

The review page shows:

- Needs Review;
- Pending Finalize;
- Open;
- Finalized.

Counts are calculated through permission-aware grouped reads inside the resolved Company/Branch scope.

## Safe actions

### Open Sale

Opens the existing ERPNext Sales Invoice or POS Invoice.

The reconciliation page never edits the invoice.

### Retry Finalization

Available only to authorised managers and only when the operation already has a platform reservation reference.

Retry:

1. rechecks the source document state;
2. calls the existing reservation finalization path;
3. asks CoreEdge for the authoritative reservation state;
4. may move a local `Needs Review` operation to `Finalized` only when CoreEdge confirms finalization.

No new reservation is created.

## Governed status transition

Normal quota-operation updates still cannot change terminal status.

The only new transition is:

`Needs Review → Finalized`

and it requires the internal reconciliation flag set by the server-side retry service.

Direct document editing cannot perform this transition.

`Finalized` remains terminal.

## Unreserved fail-open sales

A `FAIL_OPEN_UNRESERVED` operation has no existing platform reservation.

The page deliberately does not call `reserve_usage` for it.

Reason:

a post-fact reserve could occur in a later Daily/Monthly/Subscription-Term period and incorrectly attribute
the already-committed sale to the wrong commercial period.

The page therefore marks the row as requiring platform reconciliation and tells the operator not to create a
replacement accounting/business document.

A later CoreEdge administrative adjustment protocol may resolve these rows centrally with explicit audit.

## Expired/released/missing reservations

The page may retry finalization of an existing reservation reference to verify CoreEdge's authoritative state.

If CoreEdge still reports:

- Expired;
- Released;
- Not Found;
- access denied;

the row remains `Needs Review` and should be escalated.

RetailEdge does not create a replacement reservation.

## Cancellation

A cancelled Sales Invoice/POS Invoice can still represent a sale that was successfully submitted earlier.

Cancellation therefore does not refund the usage event.

If its original reservation is still reconcilable, the page may confirm/finalize that existing usage record.

This remains separate from ERPNext accounting correction.

## Accounting safety

Usage Reconciliation does not:

- amend submitted Sales Invoice;
- amend submitted POS Invoice;
- cancel documents;
- create credit notes;
- create Payment Entry;
- create Journal Entry;
- write GL Entry;
- change stock;
- change POS Closing Entry;
- reserve/debit wallet money.

It is a commercial usage-control review surface only.

## Failure behaviour

A failed retry does not mutate the business document.

Transport/platform failures leave the quota operation in its existing review state with updated attempt/error
information.

No request handler performs a manual database commit.

## Page/API

Page:

`/app/usage-reconciliation`

Read API:

`retailedge.usage_reconciliation.get_usage_reconciliation`

Mutation API:

`retailedge.usage_reconciliation.retry_usage_finalization`

Retry requires HTTP POST when invoked through Frappe HTTP.

## Tests

Focused suites:

- `retailedge.tests.test_usage_reconciliation`;
- `retailedge.tests.test_usage_reconciliation_page_contract`.

Coverage includes:

- Company/Branch scope filters;
- restricted blank-Branch filtering;
- unreserved escalation-only behavior;
- existing-reservation retry eligibility;
- permission-aware bounded queue reads;
- post-fact reserve prohibition;
- governed retry path;
- direct `Needs Review → Finalized` rejection;
- reconciliation-authorised `Needs Review → Finalized`;
- page roles;
- generic user-facing wording;
- POST retry contract;
- Company→Branch clearing;
- pagination;
- Operations Review navigation placement.

## Migration

Run normal `bench migrate`.

The slice adds one standard Frappe Page and no new accounting or transactional schema.

The existing quota-operation DocType status values are unchanged.

## Manual QA

1. Open Usage Reconciliation as RetailEdge Manager.
2. Confirm Company/Branch choices follow current permitted operating scope.
3. Confirm an Auditor can view but cannot retry.
4. Confirm a normal Sales User cannot open the page.
5. Create/seed a Pending Finalize row with an active existing reservation.
6. Retry and confirm it becomes Finalized only after CoreEdge confirmation.
7. Simulate a lost-finalize acknowledgement and prove retry does not double-count.
8. Open a `FAIL_OPEN_UNRESERVED` row and confirm no Retry Finalization action appears.
9. Confirm the unreserved row instructs platform escalation.
10. Confirm a restricted reviewer cannot access another Branch or a branchless operation.
11. Open the source invoice from the review row and confirm no invoice fields were changed.
12. Verify dark mode and mobile layout.
13. Verify the page appears under Operations Review only.
