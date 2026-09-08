# RIR2F2F1 — Standard Purchase Order Submit

## Goal

Close the everyday Purchase Order draft-completion gap for EdgeSuite users without bypassing ERPNext validation, configured approval Workflows, branch controls, subcontracting/inter-company rules, or procurement truth.

## Business contract

RetailEdge already owns standard Purchase Order draft creation and Purchase Order operational review. Before RIR2F2F1, an EdgeSuite-only buyer could create a draft but could not submit it without opening ERPNext Desk.

RIR2F2F1 adds a bounded standard path:

1. Draft Purchase Orders in the Professional Purchasing queue show **Review & Submit**.
2. The action opens an EdgeSuite review modal.
3. The server re-reads the current Purchase Order and returns items, totals, Branch and any blockers without saving anything.
4. Submission is available only when the draft is eligible for the standard path.
5. The final action calls normal ERPNext `doc.submit()` as the current user.
6. The user remains inside EdgeSuite after submission and the purchasing workspace refreshes.

## ERPNext remains authoritative

Purchase Order submission is not reimplemented by RetailEdge.

`doc.submit()` remains responsible for ERPNext validation and its legitimate purchasing side effects, including updates to ordered quantities/status on linked procurement documents. RetailEdge does not write those values directly.

Purchase Order submission itself does not create the later Purchase Receipt or Purchase Invoice. RIR2F2F1 does not create GL Entries or Stock Ledger Entries.

## Approval Workflow safety

The standard EdgeSuite submit path is deliberately disabled when an active Frappe Workflow targets `Purchase Order`.

This prevents a direct submit action from bypassing an organisation's approval states or approvers. Workflow-controlled Purchase Orders remain in the workflow-aware ERPNext approval path until a separate workflow-aware EdgeSuite design is explicitly implemented.

## Advanced cases excluded

Standard EdgeSuite submission is blocked for:

- subcontracted Purchase Orders;
- old subcontracting flow Purchase Orders;
- internal-supplier or inter-company Purchase Orders;
- On Hold, Closed or Cancelled states;
- users without Purchase Order submit permission;
- any active Purchase Order approval Workflow.

Those cases require Advanced ERPNext review.

## Branch safety

The server reads the actual Purchase Order Branch using the established RetailEdge transaction branch contract.

- A populated Branch is validated against the current user and Company.
- A restricted user cannot submit a draft with blank Branch attribution.
- Unrestricted users may submit a company-wide draft when ERPNext and permission rules otherwise allow it.

Frontend visibility is not treated as a security boundary.

## Stale-state and concurrency safety

The preview returns the Purchase Order `modified` token.

The POST submit endpoint:

1. locks the Purchase Order database row with `FOR UPDATE`;
2. re-fetches the current document;
3. revalidates Branch and items;
4. requires the preview `modified` value to match the current document;
5. re-evaluates all blockers and submit permission;
6. only then calls ERPNext `doc.submit()`.

A changed draft must be reviewed again before submission.

## EdgeSuite presentation

The Purchase Order table remains an operational EdgeSuite surface.

- Draft rows receive **Review & Submit**.
- Non-draft rows do not retain that action.
- Existing PO references remain non-routing references.
- Native `Open` remains an explicit Advanced ERPNext action for Native-Desk-authorized users only.
- Submitted standard POs proceed to the already-hardened Receipt preview/posting workflow.

The review modal shows:

- Purchase Order;
- Supplier;
- Company;
- Branch;
- total value;
- item count;
- item quantities, UOMs, rates, amounts, required dates and stock locations;
- tax row count;
- all blockers when standard submission is unavailable.

## Safety rules

RIR2F2F1 must not:

- mutate a submitted accounting document;
- create a Purchase Receipt or Purchase Invoice;
- write GL Entry or Stock Ledger Entry directly;
- use `ignore_permissions=True`;
- call `frappe.db.commit`;
- bypass an active Purchase Order Workflow;
- submit subcontracting or inter-company Purchase Orders through the standard path;
- weaken Branch permission checks;
- automatically route normal users into ERPNext Desk.

## Tests

Focused contracts freeze:

- preview non-persistence;
- Workflow detection and blocking;
- advanced-case blockers;
- submit permission enforcement;
- restricted blank-Branch fail-closed behavior;
- POST-only submission;
- database row locking;
- stale-preview rejection;
- ERPNext `doc.submit()` ownership;
- no direct ledger writes or permission bypass;
- review modal staying inside EdgeSuite;
- draft-only `Review & Submit` injection;
- capture-phase routing to the review overlay;
- overlay mount/unmount cleanup.

## Exact-head validation required

Before freezing RIR2F2F1, all four must pass on one exact SHA:

- RetailEdge Theme Compatibility;
- Linters / pre-commit / Semgrep / dependency audit;
- clean Frappe v16 standalone CI + full RetailEdge tests;
- governed EdgeSuite UI Candidate Compatibility + full RetailEdge tests.

## Manual QA still required

Automated gates do not replace the final browser/persona run. Before pre-reporting hardening is considered complete, manually verify at least:

- EdgeSuite-only buyer with submit permission;
- buyer without submit permission;
- restricted one-Branch user;
- restricted blank-Branch draft fails closed;
- unrestricted/company-wide user;
- draft standard PO review and submit;
- active Purchase Order Workflow blocks standard submit;
- subcontracting/inter-company draft blocks standard submit;
- stale draft review is rejected after another change;
- successful submit refreshes the queue and exposes the existing Receipt review path;
- Native-Desk advanced open remains explicit;
- representative light/dark themes and clean console/network behavior.

Reporting remains blocked until the wider pre-reporting hardening and persona QA sequence is complete.
