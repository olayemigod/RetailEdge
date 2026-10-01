# RetailEdge Sales Quota Reconciliation

## Goal

Provide a report-first, audited operator workflow for RetailEdge sales quota exceptions without editing submitted
Sales Invoices/POS Invoices or bypassing CoreEdge entitlement enforcement.

This slice is stacked on the Sales Transaction Quota integration.

## Operational surface

Report:

`RetailEdge Sales Quota Reconciliation`

The report appears under **Reports Centre → Controls & Audit**.

Default view shows:

- Needs Review;
- Pending Finalize.

Optional filters:

- Company;
- Branch;
- Status;
- Source Type;
- Reason Code;
- Date From/To;
- Include Finalized.

Important source documents and quota-operation records are clickable.

## Permission model

Read/report roles:

- System Manager;
- RetailEdge Manager / RetailEdgeManager;
- RetailEdge Branch Manager / RetailEdgeBranchManager;
- RetailEdge Auditor / RetailEdgeAuditor.

Mutation roles:

- Administrator;
- System Manager;
- RetailEdge Manager / RetailEdgeManager.

Branch managers and auditors are read-only.

Direct DocType list/form access is protected by row-level permission-query conditions, not only by report filters.

For restricted users:

- Company must be readable;
- Branch must be one of the user's permitted RetailEdge Branches;
- Branch search only returns permitted configured Branches.

## Recovery actions

The quota-operation form exposes governed actions only to mutation-capable roles.

### Retry CoreEdge Finalization

Available when a Pending Finalize or Needs Review operation already has a reservation reference.

The operator must provide an explicit reason.

RetailEdge calls the existing finalization path with reconciliation authority.

Possible outcomes:

- Finalized;
- Pending Finalize after a transient remote failure;
- Needs Review after an authoritative CoreEdge terminal result.

The source Sales/POS document is never modified.

### Reconcile Current Quota Period

Available only when:

- Status = Needs Review;
- no reservation is attached;
- Reason Code = `FAIL_OPEN_UNRESERVED`.

This is the audited recovery path for a sale that was allowed during an explicitly configured temporary
CoreEdge outage.

RetailEdge first asks CoreEdge for the current quota period.

It compares that period with the original source sale date.

If the source sale belongs to the current period:

1. request a one-unit reservation using the original DocType/name as business reference;
2. register a rollback release callback immediately;
3. attach the recovered reservation through the governed reconciliation-only controller flag;
4. move the local operation to Pending Finalize and save it in the local database transaction;
5. write the append-only Review Event in the same transaction;
6. queue finalization only from an after-commit callback;
7. let the existing retry scheduler recover a queue outage or transient finalize failure.

This commit-first order is intentional. CoreEdge quota must not be finalized before RetailEdge has durably stored
the recovered reservation. If the local transaction rolls back, RetailEdge releases the central reservation
instead.

If the source sale belongs to an older/different period, automatic reconciliation is refused.

Reason:

`OUTSIDE_CURRENT_QUOTA_PERIOD`

RetailEdge must not charge a September sale into October merely because the platform recovered in October.

Current/Lifetime quotas with no bounded period dates are not rejected by this date test.

## Central quota remains authoritative

RetailEdge never force-increments quota usage.

An unreserved recovery still respects the current CoreEdge policy:

- Monitor Only;
- Warn;
- Block;
- active reservations;
- committed usage;
- Service Client permissions.

If CoreEdge returns `LIMIT_EXCEEDED`, the operation remains Needs Review.

There is no local bypass.

## Distributed transaction safety

Recovered quota follows the same safe transaction boundary as normal sales submission:

- remote reserve occurs before the local reconciliation state is committed;
- local reservation state and review history commit together;
- CoreEdge finalization is queued only after local commit;
- local rollback triggers best-effort CoreEdge release;
- queue failure after commit leaves a durable Pending Finalize row for the 10-minute retry worker.

The API may therefore return `Pending Finalize` after a successful recovery reservation. That means the hold
is safely durable locally and finalization is queued; it does not claim central usage is finalized yet.

## Lost-response recovery

The reconciliation path keeps the original source DocType/name as the CoreEdge business reference.

CoreEdge V2.6D therefore reuses an existing active reservation for the same business reference when a previous
reserve request succeeded but its response was lost.

This avoids a second hold.

## Controlled reopening

Normally:

- reservation/source identity is immutable;
- Needs Review is terminal.

This slice introduces one narrow controller flag:

`allow_retailedge_quota_reconciliation`

Only the reconciliation service uses it.

It may:

- attach a recovered reservation to an unreserved Needs Review row;
- update its reserve/finalize/release idempotency keys;
- reopen Needs Review to Pending Finalize;
- transition Needs Review to Finalized after authoritative CoreEdge confirmation.

It cannot rewrite:

- operation key;
- source DocType/name;
- Company;
- Branch;
- Entitlement Key;
- Units.

Finalized remains terminal.

## Append-only review history

New DocType:

`RetailEdge CoreEdge Quota Review Event`

Every governed review action records:

- quota operation;
- action;
- result;
- previous/new status;
- Company/Branch;
- source document;
- Entitlement Key;
- reservation reference;
- explicit operator reason;
- CoreEdge reason code/message;
- reviewer;
- review timestamp.

Review Events are:

- service-created only;
- read/report only to permitted roles;
- branch/company scoped;
- non-editable;
- non-deletable.

## No manual close button

There is deliberately no local “Resolved”, “Ignore”, or “Mark Complete” button that hides a discrepancy.

A quota exception is considered financially/commercially resolved only when CoreEdge confirms the usage
finalization.

Older-period unreserved discrepancies therefore remain visible for central/platform review.

## Report limits

The report loads at most 500 rows per execution.

The backend supports a hard maximum of 1,000.

If the visible query is truncated, the report warns the operator to narrow Company/Branch/date/status filters
before taking action.

Summary cards describe the visible scoped rows rather than pretending a truncated sample is an exact global
count.

## Accounting safety

Reconciliation does not:

- mutate submitted Sales Invoice;
- mutate submitted POS Invoice;
- cancel accounting documents;
- create credit notes;
- create Payment Entry;
- create Journal Entry;
- alter GL Entry;
- alter Stock Ledger Entry;
- alter POS Closing Entry;
- reserve/debit CoreEdge MONEY_NGN wallet.

Commercial access reconciliation remains separate from ERPNext accounting truth.

## Migration

Run normal:

`bench --site <site> migrate`

This adds:

- `RetailEdge CoreEdge Quota Review Event`;
- `RetailEdge Sales Quota Reconciliation` report;
- quota-operation form actions;
- row-level permission hooks for quota operations/review events;
- Branch Manager read/report permission behind branch scope.

No historical operation is rewritten.

## Tests

Focused suite:

`retailedge.tests.test_sales_quota_reconciliation`

Coverage includes:

- current-period date validation;
- recommended action rules;
- auditor/branch-manager branch scope;
- direct form/list row-level permission;
- report branch predicates before query;
- manager-only mutations;
- reservation-backed retry to Finalized;
- older-period unreserved refusal;
- current-period unreserved reserve + commit-before-finalize recovery;
- current Block limit denial;
- report/form UI contract;
- immutable reservation identity under normal writes;
- governed reconciliation-only reopening;
- append-only review-event protection.

## QA sequence

1. Migrate twice.
2. Confirm report appears under Controls & Audit.
3. Sign in as unrestricted RetailEdge Manager and verify Company-wide scoped visibility.
4. Sign in as Branch Manager and prove another Branch cannot be searched, listed or opened directly.
5. Sign in as Auditor and prove review buttons are absent.
6. Create a reservation-backed Needs Review case and retry finalization with a reason.
7. Prove the Review Event is created.
8. Create a same-period `FAIL_OPEN_UNRESERVED` case and reconcile it.
9. Confirm CoreEdge receives the original source DocType/name business reference.
10. Simulate lost reserve response and prove reservation reuse.
11. Simulate current Block limit exceeded and prove no local bypass.
12. Create an older-period unreserved sale and prove automatic reconciliation is refused.
13. Confirm submitted Sales/POS documents are unchanged.
14. Confirm Review Events cannot be edited/deleted.
15. Confirm the report warns when its bounded result set is truncated.

## Next boundary

If production requires resolution of older-period unreserved sales, add a **central CoreEdge historical usage
reconciliation** workflow with explicit period selection and platform-admin audit.

Do not solve that by charging old sales into the current quota period.
