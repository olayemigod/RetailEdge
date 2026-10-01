# RetailEdge CoreEdge Quota Review

## Goal

Give RetailEdge managers and auditors one operational surface for sales-quota exceptions without inventing automatic historical quota correction.

The report is:

`RetailEdge CoreEdge Quota Review`

and is registered under:

`Reports Centre -> Controls & Audit`

## Default view

The report defaults to operations that still need attention:

- Pending Finalize;
- Needs Review.

Finalized operations remain available through the Status filter.

The default date window is the current month.

## Filters

- Needs Attention Only;
- Status;
- Company;
- Branch;
- Source Type;
- Entitlement;
- From Date;
- To Date.

Branch is filtered by the selected Company. Changing Company clears the current Branch selection.

Backend retrieval uses permission-aware `frappe.get_list`.

The result set is bounded to 1,000 visible operations. The report warns when results are truncated.

## Columns

The report exposes:

- quota operation;
- operation status;
- source DocType;
- clickable source document;
- Company;
- Branch;
- Entitlement Key;
- CoreEdge reservation reference;
- reserved / expiry / finalized timestamps;
- finalize attempt count;
- operation age;
- reason code;
- latest error;
- recommended next action.

## Next-action classification

### Pending Finalize

Next action:

`Retry Finalize`

RetailEdge Manager/System Manager users receive an in-report retry button.

Auditors see the recommended action as text only.

The retry calls the existing finalization service. It does not create a new quota unit.

### FAIL_OPEN_UNRESERVED

Next action:

`Reconcile central usage`

No automatic button is provided because this committed sale has no CoreEdge reservation.

Historical usage correction requires a separate governed CoreEdge reconciliation contract.

### Expired / released / missing reservation

Next action:

`Platform review required`

The report does not create a replacement reservation automatically because a new reservation could belong to the wrong quota period or be blocked under a later commercial state.

### Service Client access denied

Next action:

`Check Service Client access`

Operators should fix the platform credential/capability problem before attempting further reconciliation.

### Source document state issue

Next action:

`Verify source document`

RetailEdge does not alter the source accounting document from the quota-review report.

## Safe retry action

Whitelisted method:

`retailedge.coreedge_sales_quota.retry_sales_quota_finalize`

Rules:

- HTTP POST when invoked over HTTP;
- Administrator, System Manager, RetailEdge Manager or RetailEdgeManager only;
- operation must be readable by the current user;
- operation must still be `Pending Finalize`;
- `Needs Review` and `Finalized` rows cannot use this action.

## Accounting safety

The report and retry action do not:

- mutate submitted Sales Invoice;
- mutate submitted POS Invoice;
- cancel documents;
- create credit notes;
- post Payment Entry or Journal Entry;
- write GL Entry;
- write Stock Ledger Entry;
- change POS Closing Entry;
- debit or reserve wallet money;
- force historical quota usage.

## Migration

Run normal:

`bench --site <site> migrate`

This adds one standard Script Report and no data patch.

## Tests

Focused suite:

`retailedge.tests.test_coreedge_quota_review`

Coverage includes:

- default attention filter;
- explicit Status override;
- Company/Branch/date filters;
- invalid date rejection;
- permission-aware bounded retrieval;
- next-action classification;
- source contract forbidding `frappe.get_all`;
- Company -> Branch UI cascade;
- manager-only retry button;
- Controls & Audit registration;
- successful Pending Finalize retry;
- rejection of retry for Needs Review.

## Out of scope

This slice intentionally does not implement:

- forced historical quota consumption;
- automatic replacement reservations;
- automatic resolution of FAIL_OPEN_UNRESERVED;
- entitlement-plan mutation;
- subscription adjustment;
- wallet correction;
- invoice/accounting mutation.

Those require a separate CoreEdge reconciliation protocol with explicit period, reason and audit semantics.
