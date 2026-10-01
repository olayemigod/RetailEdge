# RetailEdge — CoreEdge Reconciliation Case Submission

## Goal

Replace the temporary current-period reservation workaround for `FAIL_OPEN_UNRESERVED` sales with the governed CoreEdge evidence-and-decision protocol.

A RetailEdge sale that already committed during an allowed CoreEdge outage is historical business truth. RetailEdge must not create a new current-period quota reservation later just to account for that sale.

This implementation supersedes the temporary unreserved-recovery workflow previously proposed in RetailEdge PR #110; the corrected branch contains the valid review/finalization work plus central case submission.

## Dependency

This slice is stacked on RetailEdge sales-quota reconciliation PR #110.

CoreEdge dependency:

- V2.6E immutable reconciliation intake
- V2.6E committed usage reconciliation
- V2.6F governed administrative decision service
- explicit Service Client capability: `entitlement_usage / reconcile_submit`

RetailEdge should not receive the raw CoreEdge `entitlement_usage / reconcile` capability.

## Updated workflow

### Reservation-backed cases

Existing behaviour is preserved.

If a durable quota operation already has a Reservation Reference, a RetailEdge Manager may retry CoreEdge finalization.

RetailEdge does not create a second reservation.

### FAIL_OPEN_UNRESERVED

For a `Needs Review` operation with:

- no Reservation Reference;
- reason code `FAIL_OPEN_UNRESERVED`;
- a currently submitted source sales document;

RetailEdge now:

1. reads the authoritative source document and rejects a cancelled source;
2. derives the original business occurrence timestamp;
3. builds a stable Product Case Key from the existing quota-operation identity;
4. submits immutable evidence to CoreEdge;
5. stores the returned CoreEdge Case Reference/status/evidence hash/submission time;
6. keeps the RetailEdge quota operation in `Needs Review`;
7. writes an append-only local Review Event.

It does not reserve current quota.

It does not finalize usage locally.

It does not mutate the Sales Invoice or POS Invoice.

## Original business timestamp

For Sales/POS invoices the evidence timestamp is derived in this order:

1. `posting_date + posting_time`;
2. transaction date when applicable;
3. document creation timestamp as a final fallback.

This timestamp is sent to CoreEdge as `occurred_on`.

Therefore a September sale reviewed in October remains a September business event.

CoreEdge decides whether it belongs to a closed historical quota period or the live period.

## Stable evidence identity

Product Case Key:

`RetailEdge CoreEdge Quota Operation.operation_key`

The existing operation key is deterministic from:

`source DocType + source document name`

This means the same committed sale keeps the same CoreEdge business identity across retries.

## Request idempotency

Each evidence-submission attempt receives a new request idempotency key.

This is deliberate.

CoreEdge has two replay-protection layers:

1. Service Gateway idempotency for one request attempt.
2. immutable Product Case identity/evidence hash for the business event.

If a transport failure creates uncertainty, RetailEdge may retry with a new request key while preserving the same Product Case Key and evidence.

CoreEdge will return the existing case instead of creating duplicate commercial evidence.

## Stable evidence versus operator reason

The explicit RetailEdge operator reason is stored in the append-only local Review Event.

It is not embedded into the immutable CoreEdge product evidence payload.

CoreEdge receives stable product evidence:

- entitlement key;
- operation identity;
- case type;
- units;
- exact source DocType/name;
- original occurrence timestamp;
- local status;
- local reason code;
- bounded original error summary.

This prevents a retry with different operator prose from causing an immutable evidence-hash conflict.

A CoreEdge Platform Admin supplies a separate explicit reason when making the final central Apply/Reject decision.

## Local persisted fields

`RetailEdge CoreEdge Quota Operation` adds read-only engine-controlled fields:

- Reconciliation Case Reference
- Reconciliation Case Status
- Reconciliation Evidence Hash
- Reconciliation Submitted On
- Reconciliation Submission Idempotency Key

Once attached, these fields cannot be changed through normal DocType updates.

The governed case-submission engine flag is required.

## Local Review Event

`RetailEdge CoreEdge Quota Review Event` adds:

Action:

- `Submit CoreEdge Review`

Result:

- `Submitted`

Evidence:

- CoreEdge Reconciliation Case Reference

Older `Reconcile Unreserved` values remain valid for existing history.

## UI

For eligible unreserved cases the operation form now shows:

`Submit to CoreEdge Review`

It no longer shows:

`Reconcile Current Quota Period`

Once a Case Reference is stored, the submit button is hidden and the operation remains visible as `Needs Review` with its CoreEdge case identity.

The report recommendation becomes:

- `Submit to CoreEdge review` before submission;
- `CoreEdge review submitted` after submission.

## Remote contract

RetailEdge remote client adds:

`submit_reconciliation_case()`

Endpoint:

`coreedge.api.v1.service_entitlement_usage.submit_reconciliation_case`

The client sends its configured site identifier but does not send:

- Tenant
- Product App
- Service Client

CoreEdge derives those from the authenticated integration identity.

## Failure behaviour

### CoreEdge unavailable

RetailEdge:

- keeps status `Needs Review`;
- preserves root reason `FAIL_OPEN_UNRESERVED`;
- records last submission error;
- writes a Failed Review Event;
- permits a later retry with a new request idempotency key.

### Capability not activated / central rejection

RetailEdge:

- keeps status `Needs Review`;
- preserves root fail-open evidence;
- does not create a reservation;
- writes a Blocked Review Event.

### Success

RetailEdge:

- stores the CoreEdge Case Reference/status/evidence hash/submission time;
- leaves the operation `Needs Review`;
- leaves Reservation Reference empty;
- writes a Submitted Review Event.

Final Apply/Reject authority remains in CoreEdge.

## Accounting and stock safety

This slice does not:

- mutate submitted Sales Invoice;
- mutate POS Invoice;
- create or alter Payment Entry;
- create Journal Entry;
- write GL Entry;
- write Stock Ledger Entry;
- change invoice outstanding amount;
- fabricate a quota reservation;
- alter the source business timestamp.

## Tests

Focused regression coverage includes:

- exact remote case-submission contract and server-bound scope;
- historical sale uses original occurrence timestamp;
- no reserve/status call for unreserved recovery;
- capability failure keeps `FAIL_OPEN_UNRESERVED`;
- retry uses a new request idempotency key with the same Product Case Key;
- already-submitted local case does not send another request;
- manager-only mutation boundary;
- branch-scoped review visibility;
- case fields are immutable without the governed engine flag;
- governed case attachment leaves operation in `Needs Review`;
- Review Events remain append-only;
- form wording no longer exposes the current-period workaround.

## Migration and rollout

Run normal:

`bench --site <site> migrate`

No existing Sales/POS documents are changed.

No historical quota operation is auto-submitted.

Rollout order:

1. validate CoreEdge V2.6E/V2.6F;
2. grant `entitlement_usage / reconcile_submit` to a test RetailEdge Service Client;
3. validate one fail-open case end-to-end;
4. verify it appears in CoreEdge Usage Reconciliation Center;
5. apply/reject from CoreEdge;
6. only then expand product rollout.

No bulk auto-submission is enabled in this slice.
