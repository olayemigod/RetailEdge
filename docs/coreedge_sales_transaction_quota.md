# RetailEdge — Sales Transaction Quota Integration

## Goal

Connect committed RetailEdge sales to the CoreEdge remote entitlement-usage reservation protocol without
changing ERPNext accounting truth or double-counting POS consolidation.

This slice is stacked on the RetailEdge CoreEdge remote-client foundation and depends on CoreEdge V2.6D.

## Default state

The integration is **disabled by default**.

No existing RetailEdge site starts reserving, blocking, or consuming sales quota after migration unless the
operator explicitly enables the site-level policy.

Protected/non-UI site configuration:

- `retailedge_sales_quota_enabled` — default 0;
- `retailedge_sales_quota_entitlement_key` — default `SALES_TRANSACTIONS`;
- `retailedge_sales_quota_fail_closed` — default 1;
- `retailedge_sales_quota_reservation_seconds` — default 3600, allowed 60–3600.

The underlying CoreEdge connection still uses the protected keys documented by the remote-client foundation:

- `coreedge_remote_usage_enabled`;
- `coreedge_base_url`;
- `coreedge_site_identifier`;
- `coreedge_api_key`;
- `coreedge_api_secret`;
- `coreedge_timeout_seconds`.

Credentials remain outside RetailEdge Settings and source control.

## What counts as one Sales Transaction

The `SALES_TRANSACTIONS` contract counts one successfully submitted positive sale document.

### Counted

- submitted positive `POS Invoice`;
- submitted positive `Sales Invoice` where `is_consolidated = 0`;
- Sales Invoice mode used by ERPNext POS is counted as the Sales Invoice transaction itself.

### Not counted

- draft saves;
- form opens;
- quotations;
- sales orders;
- delivery notes;
- reports/previews;
- `POS Invoice.is_return = 1`;
- `Sales Invoice.is_return = 1`;
- ERPNext consolidated Sales Invoices generated from POS Invoice closing where
  `Sales Invoice.is_consolidated = 1`.

ERPNext v16 consolidates already-submitted POS Invoices into a Sales Invoice at POS closing. Counting the
consolidated invoice again would charge the same retail transactions twice, so that document is explicitly
excluded.

## Returns, cancellation and amendment

This first contract measures successful submit events, not net surviving invoice count.

Therefore:

- a return/credit note does not consume a new `SALES_TRANSACTIONS` unit;
- cancelling an already-submitted counted sale does **not** refund quota;
- no CoreEdge usage decrement is attempted on cancellation;
- an amended replacement with a new ERPNext document name is a new successful submit event and may consume
  another unit.

This preserves append-only commercial usage history and avoids mutating historical quota based on later
accounting actions.

If ProcessEdge later wants a net-transaction commercial model, that should be introduced as a separate,
audited adjustment contract rather than silently subtracting usage during ERPNext cancellation.

## Submit lifecycle

The integration is attached only to:

- `Sales Invoice.before_submit`;
- `POS Invoice.before_submit`.

For an eligible sale:

1. RetailEdge requests a one-unit CoreEdge reservation.
2. The request carries the exact source DocType/name as the business reference.
3. CoreEdge holds capacity immediately.
4. RetailEdge inserts a local `RetailEdge CoreEdge Quota Operation` in the same database transaction.
5. ERPNext continues its normal submit flow.
6. If the transaction rolls back, an `after_rollback` callback performs best-effort CoreEdge release.
7. If the transaction commits, an `after_commit` callback queues finalization.
8. The finalization worker verifies the source document is actually submitted, then finalizes the reservation.
9. If the finalize acknowledgement is lost, the durable local operation remains Pending Finalize and is retried.

The quota service never modifies the submitted Sales Invoice or POS Invoice.

## Business-reference retry protection

A reserve request uses a unique attempt-level service idempotency key.

The source DocType/name is also sent to CoreEdge.

CoreEdge V2.6D reuses an existing active reservation for the same:

`Service Client + Entitlement + quota period + source DocType + source name`.

This protects the case where CoreEdge successfully reserved quota but RetailEdge lost the HTTP response.

A later submit attempt can use a new request key without creating a second active hold for the same invoice.

## Local operation record

New DocType:

`RetailEdge CoreEdge Quota Operation`

Statuses:

- Pending Finalize;
- Finalized;
- Needs Review.

It stores:

- source DocType/name;
- company/branch snapshot where available;
- Entitlement Key;
- units;
- CoreEdge reservation reference and expiry;
- reserve/finalize/release idempotency bases;
- warning/reason/message;
- reserve/finalize lifecycle timestamps;
- finalize attempt count;
- last error.

The source/reservation identity and idempotency fields are immutable after creation.

Normal users cannot create, edit or delete operation history.

System Manager, RetailEdge managers and RetailEdge auditors have read/report access.

## Finalization reliability

The finalization job is **not** enqueued synchronously inside the invoice database transaction.

RetailEdge registers an `after_commit` callback.

That means Redis/RQ availability cannot cause ERPNext to roll back a sale after quota was successfully
reserved.

If queueing fails after commit:

- the local operation remains Pending Finalize;
- a scheduled retry worker will pick it up later.

Retry scheduler:

`0/10 * * * *`

Method:

`retailedge.coreedge_sales_quota.retry_pending_sales_quota_operations`

Each background finalize attempt uses a distinct service-idempotency key while keeping the same CoreEdge
reservation reference.

This is deliberate:

- if an earlier finalize succeeded but its acknowledgement was lost, CoreEdge sees the reservation already
  Finalized and returns success without double counting;
- if an earlier service operation stored a transient failed response, the next attempt is not trapped replaying
  that failure forever.

## Reservation expiry and Needs Review

Sales reservations default to the CoreEdge maximum of 3600 seconds.

If a committed sale cannot be finalized before the hold expires, the local operation becomes
`Needs Review`.

RetailEdge does not mutate or cancel the submitted invoice.

This is the correct accounting-safe failure mode: the commercial usage discrepancy is reviewed separately
from the ERPNext transaction.

A future operator reconciliation workflow may resolve these cases against CoreEdge usage history.

## CoreEdge outage policy

When the integration is enabled, the default is fail closed:

`retailedge_sales_quota_fail_closed = 1`.

If CoreEdge cannot be reached before reservation, submission is blocked because RetailEdge cannot prove
capacity.

An operator may explicitly configure fail-open behavior.

Fail-open is a deliberate commercial-risk setting: the sale proceeds without a reservation and may therefore
be absent from central quota usage.

An explicit CoreEdge quota denial always blocks the sale, even when outage handling is configured fail-open.

## Offline POS

True commercial Block enforcement requires CoreEdge to be reachable when the server submits the counted
POS transaction.

An offline browser may continue collecting local work according to the POS application's own offline behavior,
but quota acceptance is not guaranteed until synchronization reaches the server and the `before_submit` hook
can reserve CoreEdge capacity.

Do not enable Block-mode `SALES_TRANSACTIONS` for an offline-first POS deployment until the POS client
clearly surfaces:

- pending synchronization;
- server-side quota rejection;
- retry/recovery action;
- no false local indication that a blocked transaction is fully committed.

This slice does not alter POSNext offline behavior.

## Security and tenant isolation

RetailEdge never supplies trusted Tenant or Product App values.

The protected CoreEdge API credential authenticates the exact Service Client/site.

CoreEdge derives Tenant/Product and resolves the Entitlement inside that scope.

RetailEdge sends only:

- Entitlement Key;
- one unit;
- service idempotency;
- source DocType/name;
- request/correlation metadata.

## Accounting safety

This integration does not:

- modify submitted Sales Invoices;
- modify submitted POS Invoices;
- create credit notes;
- cancel invoices;
- create Payment Entries;
- create Journal Entries;
- create GL Entries;
- change stock ledgers;
- change POS Closing Entries;
- alter outstanding balances.

Quota state is operational/commercial platform state, not ERPNext accounting state.

## Migration

Run normal `bench migrate`.

The migration adds only the RetailEdge quota-operation DocType and scheduler/hook metadata.

No historical sale is backfilled automatically.

No existing document is changed.

The integration remains disabled until site configuration explicitly enables it.

## Focused tests

`retailedge.tests.test_sales_transaction_quota`

Coverage includes:

- positive Sales Invoice counting;
- positive POS Invoice counting;
- return exclusion;
- consolidated POS-closing Sales Invoice exclusion;
- unsupported document exclusion;
- disabled-by-default policy;
- successful reservation contract;
- after-commit finalization queue registration;
- after-rollback release registration;
- explicit central denial;
- fail-closed outage handling;
- explicit fail-open outage handling;
- stable local operation identity;
- direct operation creation blocking;
- immutable reservation/source identity;
- non-deletable operation history;
- finalize success;
- transient finalize retry;
- attempt-scoped finalize service idempotency;
- expired reservation -> Needs Review;
- scheduled Pending Finalize retry;
- source-contract assertion that no cancellation refund hook exists.

## Out of scope

This slice does not:

- enable quota by default;
- backfill historical sales;
- refund quota on cancellation;
- count returns as new sales;
- change POSNext offline UX;
- automatically resolve Needs Review operations;
- create CoreEdge capability grants;
- provision API credentials;
- debit CoreEdge wallet balances;
- change payment/accounting workflows.

## QA sequence before enabling on a site

1. Validate CoreEdge PR #31 migration and focused/full suites.
2. Validate RetailEdge remote-client PR #100.
3. Migrate the RetailEdge sales-quota branch.
4. Configure a test Service Client and exact `entitlement_usage` capabilities.
5. Configure a test `SALES_TRANSACTIONS` Entitlement in Monitor Only first.
6. Submit a normal Sales Invoice and prove exactly one operation/finalized unit.
7. Submit a POS Invoice and prove exactly one operation/finalized unit.
8. Close POS and prove the consolidated Sales Invoice creates no second operation.
9. Submit returns and prove no new quota unit.
10. Simulate rollback and prove reservation release.
11. Simulate lost finalize acknowledgement and prove retry does not double count.
12. Simulate queue outage and prove the sale commits while the durable operation remains retryable.
13. Test quota exhaustion while still in Monitor Only using status/reporting.
14. Move to Warn.
15. Enable Block only after POS online/offline behavior is explicitly accepted.
