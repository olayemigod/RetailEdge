# RIR2F3F36 — Purchase Order Workflow Precedence

## Goal

Apply the F3F27 EdgeSuite workflow-precedence rule to the existing Professional Purchasing Purchase Order review/submit flow.

A standard Purchase Order already has an EdgeSuite **Review & Submit** surface. Before F3F36, an active Purchase Order Workflow correctly blocked direct submission but forced users back to ERPNext for the actual approval transition.

F3F36 closes that parity gap without changing Purchase Order creation, purchasing accounting, receiving, invoicing or advanced purchasing cases.

## Precedence

For Purchase Order:

1. active Frappe Workflow is authoritative;
2. when no active Workflow exists, the existing standard EdgeSuite direct-submit path remains available when all standard blockers pass;
3. no RetailEdge fallback workflow is invented for Purchase Order.

## Shared workflow readiness

Purchase Order preview now uses the shared F3F27 `get_workflow_readiness()` service.

The preview exposes:

- Workflow source;
- Workflow name;
- current Workflow state;
- currently permitted actions;
- next states;
- Workflow message;
- `workflow_eligible`.

The existing Purchase Order items, totals, Company, Branch, Supplier and tax-row preview remain unchanged.

## Direct submit behavior

Direct **Submit Purchase Order** is available only when:

- no active Purchase Order Workflow exists;
- the PO is still a draft;
- it is not On Hold, Closed or Cancelled;
- it is not subcontracted / old subcontracting flow;
- it is not internal-supplier / inter-company;
- it has positive-quantity items;
- Branch scope is valid;
- current user has normal Purchase Order submit permission.

When an active Workflow exists, the Workflow blocker is authoritative and direct submit permission is not used as a substitute for Workflow transition authority.

For the no-Workflow path, the existing standard endpoint still:

1. locks the Purchase Order row;
2. re-reads the PO;
3. revalidates Branch and item shape;
4. verifies the displayed `modified` snapshot;
5. re-evaluates blockers and submit permission;
6. calls normal ERPNext `doc.submit()`.

ERPNext remains authoritative for submission and procurement side effects.

## Workflow eligibility

An active Workflow does not make every Purchase Order suitable for workflow execution inside EdgeSuite.

F3F36 exposes Workflow buttons only when the active-Workflow blocker is the only blocker.

The following remain Advanced ERPNext cases:

- subcontracted PO;
- old subcontracting flow;
- internal supplier PO;
- inter-company PO;
- On Hold;
- Closed;
- Cancelled;
- invalid or inaccessible Branch;
- no positive-quantity item population;
- any other existing standard-path blocker.

This prevents Workflow from being used to bypass the standard Purchase Order safety boundary.

## Scoped workflow action

The new `apply_standard_purchase_order_workflow_action` endpoint is POST-only.

It:

1. validates Purchase Order and action;
2. verifies the PO exists and is readable;
3. locks the Purchase Order row with `FOR UPDATE`;
4. re-reads the current Purchase Order;
5. revalidates Branch scope;
6. revalidates positive-quantity items;
7. requires the preview `modified` snapshot to match;
8. rebuilds the authoritative preview;
9. requires the PO to remain `workflow_eligible`;
10. delegates the action to the shared F3F27 `apply_document_workflow_action`.

The shared workflow bridge then:

- rechecks the expected Workflow state;
- recomputes permitted transitions;
- rejects unavailable actions;
- delegates to Frappe's own `apply_workflow()`.

RetailEdge does not assign Workflow state or docstatus directly.

## EdgeSuite experience

The existing **Review & Submit Purchase Order** overlay remains the owner.

For a workflow-controlled standard PO it now shows:

- current Workflow state;
- the active Workflow name;
- Frappe's readiness message;
- only the currently permitted Workflow actions;
- each action's next state when supplied by Frappe.

Direct **Submit Purchase Order** is hidden while Workflow owns the document.

If no Workflow action is available to the current user, the overlay states that explicitly rather than inventing a transition.

After every Workflow action, EdgeSuite refreshes:

- the authoritative Purchase Order preview;
- the Professional Purchasing queue.

If the selected Workflow transition submits the Purchase Order, the overlay marks it submitted using the returned authoritative docstatus.

## Branch safety

The existing RetailEdge Branch contract remains authoritative.

- Populated Branch is revalidated for current user and Company.
- Restricted users cannot progress a Purchase Order with blank Branch attribution.
- Unrestricted Company-wide behavior is preserved where already supported.

Frontend visibility is not the security boundary.

## Accounting and procurement safety

F3F36 does not create:

- Purchase Receipt;
- Purchase Invoice;
- GL Entry;
- Stock Ledger Entry.

Purchase Order is not an accounting posting document by itself.

If a Workflow transition submits the Purchase Order, ERPNext remains responsible for the legitimate procurement-state effects of submission.

F3F36 does not:

- write Workflow state directly;
- write docstatus directly;
- use `ignore_permissions`;
- manually commit;
- mutate submitted accounting documents;
- weaken Purchase Order Branch or advanced-case rules.

## Compatibility

No schema migration is required.

Sites without an active Purchase Order Workflow preserve the existing F2F1 standard direct-submit behavior.

Sites with an active Purchase Order Workflow now receive the F3F27 workflow-precedence behavior inside EdgeSuite rather than a routine native approval handoff.

## Tests required

Focused contract coverage verifies:

- shared workflow readiness in PO preview;
- active Workflow blocks direct submit before submit-permission evaluation;
- workflow eligibility requires Workflow to be the only blocker;
- subcontracting/inter-company/status blockers remain authoritative;
- scoped action row-locks and revalidates PO scope/shape;
- stale `modified` is rejected;
- expected Workflow state is passed to F3F27;
- direct no-Workflow path still uses ERPNext `doc.submit()`;
- overlay renders only returned Workflow actions;
- direct submit is hidden under active Workflow;
- action refreshes preview and purchasing queue;
- UI never assigns Workflow state/docstatus;
- shared bridge continues using Frappe `apply_workflow()`.

The governed exact-head gates remain:

1. RetailEdge Theme Compatibility
2. Linters
3. clean Frappe v16 standalone CI
4. EdgeSuite UI Candidate Compatibility

## Manual QA at consolidated RIR2E acceptance

Validate at least:

1. no PO Workflow + standard draft + submit permission → direct Submit remains available;
2. active PO Workflow + standard draft → direct Submit disappears;
3. current user's permitted Workflow actions appear;
4. unavailable role action does not appear;
5. intermediate Workflow transition keeps draft and refreshes state/actions;
6. submit transition submits through Frappe Workflow;
7. stale PO `modified` blocks action;
8. stale expected Workflow state blocks action;
9. restricted Branch user cannot workflow-progress an out-of-scope PO;
10. blank Branch restricted PO fails closed;
11. subcontracted PO remains Advanced ERPNext;
12. inter-company PO remains Advanced ERPNext;
13. On Hold/Closed/Cancelled PO remains blocked;
14. no duplicate PO or downstream Receipt/Invoice is created;
15. queue refresh reflects final PO status.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.

## Out of scope

Purchase Receipt workflow parity is out of scope.

Purchase Invoice workflow parity is out of scope.

Purchase Return workflow parity is out of scope.

Also out of scope:

- Workflow configuration UI;
- subcontracting/inter-company workflow UX;
- Purchase Order create/edit redesign;
- receipt posting;
- invoice posting;
- supplier payment behavior.
