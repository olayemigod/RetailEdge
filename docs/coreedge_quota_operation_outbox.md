# RetailEdge — CoreEdge Quota Operation Outbox

## Goal

Provide the durable local coordination layer required before RetailEdge can safely enforce CoreEdge consume-based quotas around committed ERPNext transactions.

This slice is stacked on the remote quota client foundation.

It deliberately does **not** attach quota enforcement to Sales Invoice, POS, purchasing, stock or any other production transaction yet.

## Distributed transaction problem

RetailEdge and central CoreEdge do not share one database transaction.

A naive flow is unsafe:

- reserve/consume in CoreEdge, then local ERPNext submit fails -> central quota is over-counted;
- submit locally, then ask CoreEdge for quota -> concurrent product sites can exceed a Block limit;
- finalize remotely inside `on_submit`, then the local request rolls back later -> CoreEdge counts a transaction that never committed.

Frappe v16 provides database transaction callbacks:

- `frappe.db.after_commit.add(...)`;
- `frappe.db.after_rollback.add(...)`.

The outbox uses those primitives together with CoreEdge V2.6D reserve/finalize/release.

## Local operation record

`RetailEdge CoreEdge Quota Operation` is a durable operational/outbox record.

It stores:

- deterministic Operation Key;
- Entitlement Key and units;
- local transaction DocType/name/event;
- Company and Branch context when available;
- CoreEdge reservation reference/status;
- reserve/finalize/release idempotency keys;
- reservation/finalize/release timestamps;
- lifecycle attempt count;
- retry timing;
- last safe error code/message;
- reconciliation reason.

Lifecycle statuses:

- Reserved;
- Finalize Pending;
- Finalized;
- Release Pending;
- Released;
- Expired;
- Reconciliation Required;
- Failed.

Human roles have read/report access only.

Direct insert, edit and delete are blocked by the controller. The governed coordinator owns lifecycle changes.

## Deterministic operation identity

The operation identity is derived from:

`Entitlement Key + Transaction DocType + Transaction Name + Transaction Event`

using a SHA-256-based key.

Remote idempotency keys are distinct:

- `reserve:<operation key>`;
- `finalize:<operation key>`;
- `release:<operation key>`.

This allows retries of one lifecycle action without colliding with another.

## Prepare/reserve contract

`prepare_transaction_quota(doc, entitlement_key=..., units=..., transaction_event=...)`:

1. requires a saved local document identity;
2. builds the deterministic operation key;
3. reuses an existing Reserved/Finalize Pending operation rather than reserving twice;
4. returns an already-Finalized operation idempotently;
5. refuses to silently restart terminal Failed/Expired/Released/Reconciliation Required history;
6. requests the CoreEdge reservation;
7. only after reservation approval inserts the local outbox row;
8. registers after-commit finalization and after-rollback release callbacks.

If CoreEdge blocks the reservation, no local outbox row is created and the caller receives a validation failure.

If remote reservation succeeds but local outbox persistence fails, RetailEdge immediately attempts a compensating release. If that network release also fails, CoreEdge's reservation TTL remains the final capacity-recovery mechanism.

## Local rollback

If the ERPNext transaction rolls back:

- the local outbox insert rolls back with the business transaction;
- `after_rollback` attempts the remote release using the stable release idempotency key;
- release errors are logged server-side;
- an unreachable CoreEdge reservation ultimately expires centrally.

No submitted accounting document is edited as compensation.

## Local commit

If the local transaction commits:

- the outbox row commits with it;
- `after_commit` queues `finalize_quota_operation()`;
- finalization is therefore attempted only after local database truth exists.

If queue submission fails, the outbox row remains `Reserved` and the scheduler is the recovery path.

## Finalization worker

`finalize_quota_operation(operation_key)` locks the local operation row before acting.

It first verifies the local business document:

- Submitted -> eligible for finalization;
- Draft -> Reconciliation Required;
- Missing -> Reconciliation Required;
- Cancelled before finalization -> Reconciliation Required.

RetailEdge deliberately does not guess whether a cancelled sale should consume or refund quota. Cancellation commercial policy belongs in the later transaction-enforcement slice.

If the CoreEdge reservation has already expired before finalization, the submitted local transaction is preserved and the operation becomes `Reconciliation Required`.

Remote/network/authentication/configuration errors before reservation expiry become `Finalize Pending` with a retry time.

A successful remote finalize changes the local operation to `Finalized`.

If CoreEdge finalized successfully but the local worker crashes before saving that status, retry is safe because CoreEdge finalization is idempotent.

## Release retry

`release_quota_operation()` uses the release idempotency key.

A successful release changes the local record to `Released`.

Transient failures become `Release Pending` and are retried.

If CoreEdge reports that the reservation already expired, the local row becomes `Expired` because capacity is already free.

If CoreEdge reports that it was already finalized or cannot be found, RetailEdge does not guess: the row becomes `Reconciliation Required`.

## Scheduler recovery

RetailEdge hooks now register:

`retailedge.integrations.quota_operations.retry_pending_quota_operations`

on a 2-minute cron.

The job is bounded to at most 200 operations per run and defaults to 100.

It retries:

- Reserved;
- Finalize Pending;
- Release Pending.

Rows with a future `next_retry_on` are skipped.

## Current Sales Invoice boundary

There is still **no quota function in the Sales Invoice `doc_events` block**.

This is enforced by tests.

No quota is therefore consumed by current RetailEdge users merely because this outbox exists.

## Canonical sale event audit

Current RetailEdge guided selling creates a normal ERPNext `Sales Invoice` draft and leaves normal ERPNext submission/completion behavior intact.

Current POSNext `develop` also creates and submits ERPNext `Sales Invoice` documents for POS sales and sets `is_pos = 1` / `update_stock = 1`.

POSNext offline sync uses `offline_id` plus `Offline Invoice Sync` to avoid re-submitting an already synchronized submitted Sales Invoice.

Therefore the strongest candidate for one future RetailEdge sale-transaction quota is:

> first successful submission of one non-return ERPNext Sales Invoice

with a stable business idempotency identity based on the Sales Invoice name.

This can cover guided sales, normal ERPNext full-form sales and current POSNext sales without creating a separate POS counter.

That policy is not enabled in this slice.

## Future Sales Invoice hook shape

After CoreEdge central PR #31 and this outbox are fully green, a separate enforcement PR may add:

### before_submit

For an eligible, non-return Sales Invoice:

1. determine the exact commercial Entitlement Key;
2. call `prepare_transaction_quota()` for one unit;
3. if reservation is blocked, stop submission;
4. otherwise continue normal ERPNext submission.

### after local commit

The callback/outbox finalizes centrally.

### after local rollback

The callback attempts remote release.

Do **not** call remote finalization directly from `on_submit` before the database commit is known to be durable.

## Returns and cancellation

Returns use Sales Invoice `is_return = 1` and should not automatically count as another sale unless the commercial plan explicitly says so.

A later policy must decide whether cancellation:

- leaves the originally committed sale counted;
- creates a separate compensating quota event;
- or is handled only for billing analytics.

Do not decrement committed CoreEdge usage merely because an ERPNext Sales Invoice is cancelled; that would silently rewrite commercial history.

## Offline POS constraint

POSNext is offline-resilient.

A browser can capture a sale while CoreEdge is unreachable and synchronize it later.

A strict central Block quota therefore cannot guarantee pre-sale authorization while the device is offline.

Before enabling Block mode for POS sales, ProcessEdge must choose one policy:

1. Monitor/Warn only for offline-capable POS transaction quotas;
2. pre-allocated offline quota leases/tokens;
3. allow offline capture but block later server sync when quota is unavailable, with explicit operator recovery.

This outbox does not invent an offline quota lease.

## Accounting safety

The outbox never:

- changes submitted Sales Invoice values;
- edits GL entries;
- changes Payment Entry;
- changes stock ledgers;
- converts or replaces ERPNext accounting documents.

Quota reconciliation is platform/commercial governance, not accounting correction.

## Tests

Focused suite:

`retailedge.tests.test_coreedge_quota_operation_outbox`

Coverage includes:

- deterministic operation identity;
- successful reserve + local outbox persistence;
- blocked reserve creates no outbox;
- repeated prepare does not reserve twice;
- successful finalize exactly once;
- transient finalize retry state;
- expired reservation -> reconciliation;
- cancelled local transaction -> reconciliation rather than guess;
- successful release;
- durable Release Pending state;
- scheduler retry of finalize and release;
- engine-only create/update/delete controls;
- distinct lifecycle idempotency keys;
- retry scheduler hook;
- Sales Invoice remains unhooked;
- human permissions remain read-only.

The earlier remote-client suite is also updated so it permits the outbox scheduler while continuing to reject quota code inside the Sales Invoice event block.

## Migration

Run normal `bench migrate`.

This adds one operational DocType and one scheduler hook.

No data patch is required.

No existing Sales Invoice, POS invoice, stock, payment or GL record changes.

No quota is activated automatically.

## Next gate

Do not enable live Sales Invoice Block enforcement until all of these are true:

1. CoreEdge PR #31 is validated on a functioning runner/local bench;
2. RetailEdge remote-client PR #98 is fully green;
3. this outbox PR passes migration, focused tests and full RetailEdge regression;
4. the production commercial Entitlement Key is explicitly approved;
5. cancellation policy is approved;
6. offline POS policy is approved;
7. POSNext/current Sales Invoice behavior is reverified against the exact deployed POSNext version.

Only then should the Sales Invoice submission hook be added as a separate narrow PR.