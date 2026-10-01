# RetailEdge — CoreEdge Reconciliation Status Sync

## Goal

Close the product-side reconciliation loop after RetailEdge submits a `FAIL_OPEN_UNRESERVED` case to CoreEdge.

RetailEdge may read the authoritative CoreEdge case outcome and mirror that outcome locally.

RetailEdge still cannot apply or reject CoreEdge usage itself.

## Dependency

This slice is stacked on RetailEdge PR #113.

CoreEdge dependency:

- CoreEdge V2.6H reconciliation case status service
- capability `entitlement_usage / reconcile_status`

## Workflow

### Open

When the stored CoreEdge Case Status is `Open`:

- RetailEdge remains `Needs Review`;
- Reservation Reference remains empty;
- root reason `FAIL_OPEN_UNRESERVED` remains unchanged;
- Last Checked On is refreshed;
- an append-only `Refresh CoreEdge Review` event is written.

### Resolved

CoreEdge `Resolved` is accepted only when its controlled decision summary says:

`decision_type = Apply Usage`

RetailEdge then:

- changes the local quota-operation status to `Resolved`;
- stores the CoreEdge decision/result fields;
- stores the CoreEdge usage Reconciliation Reference when supplied;
- leaves Reservation Reference empty;
- preserves the original `FAIL_OPEN_UNRESERVED` root reason;
- writes an append-only `Resolved` Review Event.

Local `Resolved` is deliberately different from `Finalized`.

`Finalized` means a normal CoreEdge reservation was finalized.

`Resolved` means an exceptional fail-open case was administratively decided by CoreEdge.

### Rejected

CoreEdge `Rejected` is accepted only when:

`decision_type = Reject`

RetailEdge then:

- changes local status to `Rejected`;
- stores the controlled decision/result fields;
- does not create any usage reservation;
- writes an append-only `Rejected` Review Event.

## Fail-closed contract checks

RetailEdge refuses local closure when:

- CoreEdge returns a different Case Reference;
- CoreEdge returns an unknown case status;
- `Resolved` does not carry `Apply Usage`;
- `Rejected` does not carry `Reject`;
- the status endpoint is unavailable;
- CoreEdge denies the status request.

Any such case stays `Needs Review`.

## Local persisted fields

The quota operation stores:

- Reconciliation Case Status
- Reconciliation Last Checked On
- Reconciliation Decision Reference
- Reconciliation Decision Type
- Reconciliation Result Status
- Reconciliation Result Reason Code
- Reconciliation Applied Usage
- CoreEdge Usage Reconciliation Reference
- Reconciliation Decided On

These fields are read-only and engine-controlled.

Only the status-sync service may populate/change them through:

`allow_retailedge_quota_case_status_sync`

## Terminal-state rules

The local terminal statuses are:

- `Finalized` — normal reservation lifecycle completed;
- `Resolved` — CoreEdge administrative usage reconciliation completed;
- `Rejected` — CoreEdge rejected the submitted evidence.

Once a quota operation is Finalized, Resolved, or Rejected it cannot move to another state.

## Operator surface

For `Needs Review` rows with a CoreEdge Case Reference, the form shows:

`Refresh CoreEdge Review Status`

The operator provides an explicit reason before the status read.

The action is available only to existing quota-review mutation roles.

Auditor and Branch Manager remain read-only.

## Report behaviour

The default report still shows unresolved operational work:

- Needs Review
- Pending Finalize

Terminal rows are excluded by default.

The existing technical filter field `include_finalized` is retained for backward compatibility, but its visible label becomes:

`Include Closed / Finalized`

When enabled, the report may include:

- Finalized
- Resolved
- Rejected

The report also exposes controlled CoreEdge case/decision fields for audit.

## Remote client

RetailEdge adds:

`CoreEdgeRemoteUsageClient.get_reconciliation_case_status()`

Endpoint:

`coreedge.api.v1.service_entitlement_usage.get_reconciliation_case_status`

The client sends:

- configured Site Identifier;
- exact CoreEdge Case Reference;
- Request ID;
- Correlation ID;
- Source Path.

It does not send Tenant, Product App, or Service Client.

## Accounting and stock safety

Status synchronization does not:

- mutate Sales Invoice;
- mutate POS Invoice;
- create/finalize/release a CoreEdge reservation;
- increment quota itself;
- create Payment Entry;
- create Journal Entry;
- alter GL Entry;
- alter Stock Ledger Entry;
- alter invoice outstanding;
- alter POS Closing.

It only mirrors authoritative CoreEdge case metadata into the local governance record.

## Tests

Focused coverage includes:

1. Open CoreEdge case stays Needs Review.
2. Open refresh writes Last Checked On without creating a reservation.
3. Resolved + Apply Usage closes locally as Resolved.
4. Rejected + Reject closes locally as Rejected.
5. Root `FAIL_OPEN_UNRESERVED` remains unchanged.
6. Case Reference mismatch fails closed.
7. Invalid status/decision pairing fails closed.
8. Remote status error remains Needs Review.
9. Already-terminal local case returns without another remote call.
10. Remote client sends no Tenant/Product/Service Client scope.
11. Normal DocType update cannot forge CoreEdge decision fields.
12. Governed status-sync flag can close Needs Review without a reservation.
13. Resolved/Rejected are terminal.
14. Form exposes Refresh CoreEdge Review Status.
15. Default report excludes closed statuses.

## Rollout

Required Service Client capabilities:

- `entitlement_usage / reconcile_submit`
- `entitlement_usage / reconcile_status`

Do not grant:

- `entitlement_usage / reconcile`

Initial rollout remains operator-triggered status refresh.

Do not add aggressive polling or automatic bulk closure in this slice.
