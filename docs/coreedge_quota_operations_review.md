# RetailEdge Quota Operations Review Center

## Goal

Give RetailEdge managers and auditors an actionable, permission-aware review surface for CoreEdge sales quota exceptions without changing ERPNext accounting documents or inventing a local quota override.

The page is:

`/app/quota-operations-review`

It is placed under **Operations Review**, not under normal Sales or POS transaction navigation.

## Why this surface exists

The sales transaction quota integration is intentionally asynchronous after the ERPNext database commit.

Most transactions should move automatically:

`Pending Finalize -> Finalized`

Exceptions can remain:

- Pending Finalize after temporary queue/network failure;
- Needs Review after CoreEdge reports an expired, released, missing or inaccessible reservation;
- Needs Review / `FAIL_OPEN_UNRESERVED` when a sale was deliberately allowed during a temporary CoreEdge availability outage.

Those states must be visible and actionable to operators.

## Roles

Read access:

- Administrator;
- System Manager;
- RetailEdge Manager;
- RetailEdgeManager;
- RetailEdge Auditor;
- RetailEdgeAuditor.

Mutation/reconciliation access:

- Administrator;
- System Manager;
- RetailEdge Manager;
- RetailEdgeManager.

Auditors are read-only.

## Filters

The review page supports:

- Status;
- Company;
- Branch;
- Source document type;
- From date;
- To date;
- free-text search across document/reservation/reason/error fields.

Default Status is `Open`, which means:

- Pending Finalize;
- Needs Review.

Company and Branch filters follow RetailEdge operating-context governance.

If a Branch-restricted user leaves Branch blank, the backend automatically scopes the review to all of that
user's currently allowed Branches for the selected Company.

A restricted user with zero active Branch access fails closed and is not treated as unrestricted.

All operation and history lists use permission-aware `frappe.get_list`; the page does not use `get_all`.

## Summary cards

The page shows exact counts in the selected Company/Branch/date/search scope for:

- Needs Review;
- Pending Finalize;
- Finalized;
- Total.

Rows are server-paginated with a maximum page size of 100.

## Source-document navigation

Every row links back to the exact source:

- Sales Invoice;
- POS Invoice.

Opening the source document is read/navigation behavior only.

The review page never mutates the source invoice.

## Safe actions

### Pending Finalize -> Retry

A manager may retry normal finalization.

This calls the existing durable sales-quota finalizer.

If CoreEdge confirms finalization, the local operation becomes Finalized.

If the remote service is temporarily unavailable, the operation remains Pending Finalize.

### Needs Review with reservation -> Review & Retry

A manager must provide an explicit reason.

RetailEdge asks CoreEdge for the authoritative reservation result.

Only CoreEdge success can move:

`Needs Review -> Finalized`

RetailEdge does not treat its cached expiry timestamp as authority and does not force-count the quota locally.

### FAIL_OPEN_UNRESERVED -> Attempt Reconciliation

A manager must provide an explicit reason.

RetailEdge verifies that the source transaction reached submitted/cancelled-after-submit state.

It then asks CoreEdge to reserve the original sale unit using:

- the original Entitlement Key;
- exact source DocType;
- exact source document name;
- one unit.

CoreEdge's business-reference deduplication protects uncertain retries.

If reservation succeeds, RetailEdge attaches that reservation once to the previously unreserved local operation and immediately asks CoreEdge to finalize it.

If CoreEdge blocks the reservation because the commercial limit is exhausted, the sale remains Needs Review. RetailEdge does not force the usage count.

### Other Needs Review states

Expired, released, missing, inaccessible, or otherwise terminal reservation problems remain Needs Review when CoreEdge cannot safely finalize them.

The UI labels these as requiring platform review.

There is no local force-finalize button.

## Guarded local lifecycle

`RetailEdge CoreEdge Quota Operation` remains engine-controlled.

Ordinary saves still cannot change:

- operation identity;
- source DocType/name;
- Company/Branch;
- Entitlement Key;
- units;
- reservation identity;
- idempotency fields.

The review service has one narrow exception:

- a Needs Review operation with **no reservation** may attach one reconciliation reservation;
- it may then move Needs Review -> Finalized only after CoreEdge confirms finalization.

An existing reservation reference cannot be rewritten even by the reconciliation flag.

## Review audit

The operation stores the latest review metadata:

- Review Action;
- Review Reason;
- Reviewed By;
- Reviewed On.

Every actual operator retry/reconciliation attempt is also written to the append-only:

`RetailEdge CoreEdge Quota Review Event`

Each event records:

- quota operation;
- action;
- result status;
- source DocType/name;
- reservation reference;
- operator reason;
- reason code/message;
- actor;
- timestamp.

Review Events cannot be manually created, edited or deleted.

The page exposes this history inline through a History action, so auditors do not need to navigate to a hidden DocType.

## No accounting mutation

The review center does not:

- cancel or amend Sales Invoice;
- cancel or amend POS Invoice;
- create credit notes;
- create Payment Entry;
- create Journal Entry;
- alter GL Entry;
- alter Stock Ledger Entry;
- alter POS Closing Entry;
- debit or reserve CoreEdge wallet money.

Commercial quota reconciliation remains separate from ERPNext accounting truth.

## Failure semantics

The review center never converts a CoreEdge failure into local success.

Examples:

- quota blocked -> remains Needs Review;
- CoreEdge unavailable -> remains Pending/Needs Review as appropriate;
- authentication/config invalid -> action fails;
- source never reached submitted state -> remains Needs Review;
- reservation already finalized -> CoreEdge authoritative response allows local Finalized recovery;
- reservation expired/released/missing -> remains Needs Review.

## Navigation

Workspace:

**Operations Review -> Quota Operations Review**

Sidebar:

**Operations Review -> Quota Operations Review**

The page is deliberately not placed in Sales or Point of Sale because users should not encounter exception-management controls during routine selling.

## Migration

Run normal:

`bench --site <site> migrate`

This slice adds:

- review audit fields to RetailEdge CoreEdge Quota Operation;
- RetailEdge CoreEdge Quota Review Event;
- quota operations review Page;
- EdgeSuite review bundle/component;
- Operations Review workspace/sidebar link.

No historical sales or quota usage is changed.

Existing quota operations remain valid.

## Focused tests

`retailedge.tests.test_coreedge_quota_review`

Coverage includes:

- review reason validation;
- Pending Finalize retry;
- unreserved Needs Review routing;
- reason-required Needs Review retry;
- CoreEdge-blocked reconciliation;
- successful reservation attachment + finalization;
- unsubmitted-source rejection;
- restricted-zero Branch scope fail-closed;
- restricted multi-Branch implicit scoping;
- unrestricted Branch filtering;
- permission-aware `get_list` contract;
- EdgeSuite ownership/no direct client writes;
- Operations Review navigation placement;
- auditor read-only role contract;
- ordinary reservation-attachment rejection;
- governed one-time reservation attachment;
- permission-aware summary/pagination execution;
- append-only Review Event creation/history/edit/delete protection;
- Needs Review -> Finalized only through governed reconciliation.

## Manual QA

1. Migrate twice.
2. Open Quota Operations Review as System Manager.
3. Confirm default Open filter shows Pending Finalize and Needs Review only.
4. Verify Company -> Branch filtering.
5. Verify a restricted-zero Branch user cannot access another Branch through the API.
6. Verify Auditor can view rows/history but sees no mutation actions.
7. Create a Pending Finalize test operation and retry; confirm successful CoreEdge finalization.
8. Simulate CoreEdge outage; confirm retry remains pending/review without invoice mutation.
9. Create FAIL_OPEN_UNRESERVED operation with submitted source.
10. Attempt reconciliation with explicit reason.
11. Confirm CoreEdge Block leaves Needs Review.
12. Restore quota capacity and retry; confirm one reservation is attached and operation finalizes.
13. Retry the same reconciliation path after lost response; confirm CoreEdge business-reference dedupe prevents double counting.
14. Confirm review reason/actor/time update.
15. Open History and confirm append-only events.
16. Attempt direct edit/delete of Review Event; confirm blocked.
17. Attempt to rewrite an existing reservation reference; confirm blocked.
18. Open the Sales/POS source from the table; confirm document remains unchanged.
19. Confirm workspace/sidebar placement under Operations Review.
20. Verify mobile/table overflow and dark-mode readability.

## Rollout

Keep sales quota enforcement disabled by default until:

- CoreEdge V2.6C/V2.6D passes migration and focused/full regression locally or on a functioning runner;
- RetailEdge remote-client and sales-quota PRs are green;
- this review surface passes manual QA;
- online POS/Sales Invoice flows are validated before any offline-first Block rollout.
