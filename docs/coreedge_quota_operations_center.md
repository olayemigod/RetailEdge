# RetailEdge — CoreEdge Quota Operations Center

## Goal

Provide an operational control surface for RetailEdge/CoreEdge sales-quota lifecycle exceptions without changing ERPNext accounting truth or inventing a browser-side reconciliation authority.

This slice is stacked on:

- RetailEdge remote quota client;
- RetailEdge sales transaction quota integration;
- CoreEdge V2.6D remote usage reservations.

## Route

`/app/quota-operations`

Navigation:

`Operations Review → Quota Operations`

## Intended users

Initial page access is limited to roles that already have safe read access to
`RetailEdge CoreEdge Quota Operation`:

- System Manager;
- RetailEdge Manager;
- RetailEdgeManager;
- RetailEdge Auditor;
- RetailEdgeAuditor.

RetailEdge Auditor is read-only.

Retry is limited to:

- System Manager;
- RetailEdge Manager;
- RetailEdgeManager.

### Branch Manager boundary

RetailEdge Branch Manager is deliberately **not** granted this page in the first slice.

The quota-operation DocType does not yet have a dedicated row-level permission rule that restricts native record access by operational Branch. Adding the Page role alone would create a risk that a Branch Manager could bypass the EdgeSuite filters and read other Branches through a native DocType route.

A later Branch Manager rollout must first implement and test a row-scoped DocType permission contract.

## Default view

The initial filter is:

`Status = Open`

Open means:

- Pending Finalize;
- Needs Review.

Other filters:

- Company;
- Branch;
- Status;
- Source Type;
- Search.

Current source types:

- Sales Invoice;
- POS Invoice.

Search matches:

- source document name;
- CoreEdge reason code;
- latest local error;
- safe remote message.

## Permission and Branch scope

The browser never supplies trusted scope.

The backend:

1. requires an allowed Quota Operations role;
2. requires DocType read permission;
3. validates requested Company against the user's permitted operating contexts;
4. resolves the user's operational Branch scope;
5. when the user is Branch-restricted, blank Branch means all **permitted** Branches, never all Company Branches;
6. validates any explicitly selected Branch server-side;
7. uses `frappe.get_list`, not `frappe.get_all`;
8. bounds the matching dataset before pagination.

Dataset cap:

`2,000 rows`

If more than 2,000 operations match, the user must narrow the filters.

## Visible operational information

The page exposes only information needed for review:

- status;
- source transaction;
- Company;
- Branch;
- Entitlement Key;
- CoreEdge/local reason;
- bounded issue/message text;
- reserve timestamp;
- last finalize attempt;
- attempt count;
- safe action.

The page does not expose:

- API credentials;
- service-client secrets;
- idempotency keys;
- raw request payloads;
- internal CoreEdge tenant/product authority fields.

## Safe actions

### Pending Finalize

Permitted managers may choose:

`Retry Finalization`

This does **not** finalize quota in the browser request.

The POST endpoint:

1. rechecks user role;
2. reads the operation permission-aware;
3. revalidates Company/Branch scope;
4. requires current status `Pending Finalize`;
5. queues the existing durable finalization worker.

The existing worker remains the authority for:

- source-document state;
- CoreEdge reservation state;
- idempotent finalize retries;
- transition to Finalized or Needs Review.

### Needs Review

Needs Review is intentionally read-only.

The first control-center slice does not provide:

- force finalize;
- create replacement reservation;
- write central usage;
- decrement usage;
- waive usage;
- change Entitlement;
- edit reservation identity;
- alter submitted ERPNext documents.

Those actions require a separate governed reconciliation contract in CoreEdge.

### Finalized

Finalized operations are history only.

No browser action is available.

## Accounting safety

Quota Operations does not:

- amend Sales Invoice;
- amend POS Invoice;
- cancel or submit ERPNext documents;
- create Payment Entry;
- create Journal Entry;
- create GL Entry;
- change Stock Ledger Entry;
- change POS Closing Entry;
- reserve/debit CoreEdge MONEY_NGN wallet.

The control surface observes and retries commercial quota finalization only.

## EdgeSuite UI

The page uses the standard RetailEdge/EdgeSuite shell:

- EdgeAppShell;
- EdgeReportShell;
- EdgeLinkField;
- EdgeDropdown.

The native Frappe sidebar is hidden.

The Source Transaction cell opens the source document only when:

- the server confirms source read permission; and
- the current EdgeSuite session allows Native Desk.

This avoids unnecessarily exposing platform internals to normal product users.

## Tests

Focused suite:

`retailedge.tests.test_coreedge_quota_operations_center`

Coverage includes:

- restricted blank-Branch scope cannot widen access;
- unrestricted users do not receive an invented Branch filter;
- explicit Branch selection is server validated;
- dataset cap fails closed;
- retry revalidates operation scope;
- only Pending Finalize can be retried;
- Needs Review cannot be queued;
- backend uses permission-aware reads;
- no accounting commit/mutation path;
- EdgeSuite runtime contract;
- no direct browser finalizer;
- Operations Review navigation placement;
- Branch Manager is excluded from the new unsafe raw-record permission boundary;
- unrelated existing Branch Manager navigation roles remain present.

## Migration

Run normal:

`bench --site <site> migrate`

Then build RetailEdge assets.

No historical operation is changed.

No quota status is migrated.

No accounting record is changed.

## Manual QA

1. Migrate the candidate twice.
2. Build assets.
3. Sign in as System Manager.
4. Open `Operations Review → Quota Operations`.
5. Confirm default status is Open.
6. Confirm Pending Finalize and Needs Review appear.
7. Confirm Finalized is hidden until selected.
8. Filter Company.
9. Filter Branch.
10. Confirm Company change clears the previous Branch.
11. Confirm a Branch outside the permitted scope is rejected server-side.
12. Search by invoice name.
13. Search by reason code.
14. Confirm auditors cannot retry.
15. Confirm managers can retry only Pending Finalize.
16. Confirm retry queues work rather than running CoreEdge finalization synchronously in the browser request.
17. Confirm Needs Review has no force-repair action.
18. Confirm Finalized has no action.
19. Confirm source documents open only when Native Desk/read permission allows.
20. Simulate more than 2,000 matching operations and confirm the page requires narrower filters.
21. Confirm no submitted Sales Invoice/POS Invoice fields change during any page action.
22. Confirm no wallet or GL entry is created.
23. Confirm Branch Manager does not see the page until row-level DocType permission governance is implemented.

## Next slice

After this page is validated, the next CoreEdge-side design should be a governed **Quota Reconciliation Decision** contract for selected Needs Review cases.

That future contract should distinguish at least:

- reservation expired before acknowledgement;
- CoreEdge finalized but RetailEdge lost acknowledgement;
- fail-open unreserved committed sale;
- reservation released unexpectedly;
- reservation missing/inaccessible;
- operator-approved commercial adjustment.

It must remain append-only, reasoned, auditable, tenant/product/service-client scoped, and must never mutate submitted ERPNext accounting documents.
