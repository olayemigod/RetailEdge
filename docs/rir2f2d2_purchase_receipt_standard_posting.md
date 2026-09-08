# RIR2F2D2 — Standard Purchase Receipt Posting

## Goal

Close the standard SME Purchase Receipt loop inside EdgeSuite without reimplementing ERPNext stock logic.

RIR2F2D2 promotes only the simple, already-preflighted Purchase Order → Purchase Receipt case. ERPNext remains the source of truth for mapping, document validation, submission and stock ledger posting.

## Frozen parent

RIR2F2D1 was frozen green at:

`cf50eb368f8f9a7551864f4278a9f34edd731371`

Exact-head gates passed on that parent:

- RetailEdge Theme Compatibility #411
- Linters #2252
- CI #2270
- EdgeSuite UI Candidate Compatibility #508

## In scope

For a submitted, open Purchase Order that passes the RIR2F2D1 standard receipt preflight:

1. User opens **Review Receipt** from Professional Purchasing.
2. EdgeSuite displays ERPNext's current PO → Purchase Receipt mapping.
3. The standard **Receive Stock** action is shown only when:
   - there are no advanced blockers; and
   - the current user has Purchase Receipt submit permission.
4. The user receives an explicit confirmation that stock will be posted.
5. The server locks the Purchase Order row, reloads current state, verifies the preview is not stale, re-runs permissions, branch scope and the ERPNext mapper, and re-evaluates blockers.
6. Only after those checks does the server call the mapped Purchase Receipt's normal `insert()` and `submit()` methods as the current user.
7. ERPNext owns all document, stock ledger and accounting consequences of submission.

## Standard-case blockers

EdgeSuite posting is unavailable when any of these conditions are present:

- serial-number handling required;
- batch handling required;
- purchase quality inspection required;
- rejected quantity handling required;
- subcontracted Purchase Order;
- no receivable quantity remains;
- receiving warehouse is unresolved;
- mapped receiving warehouse belongs to a different company.

These cases remain **Advanced ERPNext** workflows. RetailEdge does not fabricate defaults or bypass native controls.

## Concurrency and stale-preview safety

Receipt posting uses a `FOR UPDATE` lock on the Purchase Order before remapping. This serializes concurrent receipt attempts for the same PO and reduces double-click/concurrent duplicate-receipt risk.

The preview returns the Purchase Order `modified` value. Posting requires the same value after the row lock. If the Purchase Order changed after preview, posting fails and the user must refresh the receipt preview.

The preview value is not trusted as business truth; the server always remaps and revalidates after acquiring the lock.

## Branch and company safety

- The named Purchase Order must be readable by the current user.
- Existing RetailEdge branch scope rules remain authoritative.
- Restricted users cannot receive an unattributed Purchase Order.
- If the Purchase Receipt has a RetailEdge/Branch attribution field, the mapped receipt inherits the validated Purchase Order branch.
- A receiving warehouse must resolve and must belong to the Purchase Order company.
- ERPNext performs final warehouse/document validation during insert and submit.

## Permission safety

The EdgeSuite posting endpoint requires both:

- Purchase Receipt `create` permission; and
- Purchase Receipt `submit` permission.

The document is inserted and submitted as the current user. RIR2F2D2 does not use `ignore_permissions=True`.

## Accounting and stock safety

RIR2F2D2 does **not**:

- create Stock Ledger Entries directly;
- create GL Entries directly;
- mutate a submitted Purchase Receipt;
- bypass ERPNext validation;
- manufacture serial/batch/inspection data;
- change ERPNext stock or accounting semantics.

The only posting operation is ERPNext Purchase Receipt submission.

## Native Desk boundary

The existing advanced handoff remains available only where Native Desk access is allowed. It is a separate, explicit **Advanced: Prepare in ERPNext** action.

Advanced blockers never expose the standard EdgeSuite **Receive Stock** action.

## Out of scope

RIR2F2D2 does not add:

- partial quantity editing;
- rejected quantity entry;
- serial/batch bundle capture;
- quality inspection capture;
- subcontract receipt handling;
- Purchase Receipt amendment/cancellation/return flows;
- Purchase Invoice or payment changes;
- reporting development;
- RIR2F2D3+ purchasing enhancements.

## Required automated validation

On the final exact head:

- RetailEdge Theme Compatibility;
- Linters / pre-commit / Semgrep / dependency audit;
- clean Frappe v16 install, migrate, build and full RetailEdge test suite;
- EdgeSuite UI Candidate Compatibility;
- RIR2F2D1 preview regression contract;
- RIR2F2D2 standard posting contract.

## Required manual browser QA before final purchasing freeze

On `retail.local` or equivalent representative site:

### EdgeSuite-only purchasing user

- submitted standard PO shows **Review Receipt**;
- preview shows supplier, company, branch, quantities and receiving stock locations;
- standard eligible preview shows **Receive Stock** only when the user can submit Purchase Receipt;
- confirmation clearly states that stock will be posted;
- successful action creates one submitted Purchase Receipt and refreshes purchasing state;
- direct native Purchase Receipt list/form remains blocked by the shared operational guard;
- advanced receipt handoff is not visible.

### Advanced Native Desk user

- standard EdgeSuite receipt path still works;
- explicit **Advanced: Prepare in ERPNext** remains available;
- advanced blocker cases do not show **Receive Stock**.

### Safety cases

- stale preview is rejected and requires refresh;
- double click does not create duplicate submitted receipts;
- serial item is blocked to Advanced ERPNext;
- batch item is blocked to Advanced ERPNext;
- quality-inspection item is blocked to Advanced ERPNext;
- subcontracted PO is blocked to Advanced ERPNext;
- missing receiving warehouse is blocked;
- restricted user cannot receive another branch's or unattributed PO;
- representative light/dark rendering is clean;
- browser console/network shows no new application errors.

## Freeze rule

RIR2F2D2 is not frozen until all required exact-head automated gates are green. Manual browser QA must not be claimed from repository-only validation.

Reporting remains blocked, and PR #55 remains the authoritative draft/unmerged reconciliation line.
