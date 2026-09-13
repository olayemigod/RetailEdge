# RIR2F3F37 — Purchase Receipt Workflow Precedence

## Goal

Apply the F3F27 workflow-precedence rule to the standard Purchase Order → Purchase Receipt EdgeSuite flow without bypassing ERPNext stock controls or creating duplicate receipt drafts.

The existing standard path already uses ERPNext's `make_purchase_receipt()` mapper, validates Branch/warehouse/stock-control complexity, and submits the mapped receipt through normal ERPNext document APIs.

F3F37 adds the missing active-Workflow behavior while preserving that stock truth.

## Workflow precedence

For Purchase Receipt:

1. active Frappe Workflow is authoritative;
2. when no active Workflow exists, the existing standard one-step insert + submit path remains available;
3. no RetailEdge fallback workflow is invented for Purchase Receipt.

RetailEdge does not assign Workflow state or docstatus directly.

## Why a saved draft is required

ERPNext's PO → Purchase Receipt mapper initially returns an unsaved Purchase Receipt document.

Frappe Workflow actions require an actual persisted document with an authoritative workflow state and current permitted transitions.

F3F37 therefore does **not** apply Workflow to the unsaved mapper result.

For an active Purchase Receipt Workflow, EdgeSuite first persists exactly one standard Purchase Receipt draft. Workflow actions are then applied to that saved draft through the shared F3F27 bridge.

## Read-only preview

The existing **Review Purchase Receipt** preview remains read-only.

It still:

- loads the submitted/open Purchase Order;
- validates Company/Branch scope;
- uses ERPNext `make_purchase_receipt()`;
- validates mapped Company/Supplier;
- validates receiving warehouses;
- detects serial-number requirements;
- detects batch requirements;
- detects purchase Quality Inspection requirements;
- detects rejected quantities;
- detects subcontracting;
- detects missing warehouse;
- rejects no-receivable-quantity cases.

If no active Purchase Receipt Workflow exists, the existing **Receive Stock** behavior remains unchanged.

If an active Workflow exists and no saved standard draft exists, the preview exposes **Start Receipt Approval** instead of direct stock receipt submission.

No document is persisted by merely opening the preview.

## Start Receipt Approval

The POST-only `start_standard_purchase_receipt_workflow` endpoint:

1. row-locks the Purchase Order;
2. re-reads the Purchase Order;
3. requires it to remain submitted and open;
4. requires the preview `modified` snapshot to remain current;
5. revalidates Branch scope;
6. remaps the Purchase Receipt through ERPNext;
7. re-evaluates all standard/advanced blockers;
8. confirms an active Purchase Receipt Frappe Workflow still exists;
9. checks for existing draft Purchase Receipts already linked to the PO;
10. reuses exactly one valid standard draft when present;
11. otherwise requires normal Purchase Receipt create permission and inserts one draft;
12. returns workflow readiness from the saved draft.

The start action never calls `submit()`.

Stock is not received merely by starting the approval process.

## Duplicate prevention and idempotency

A draft Purchase Receipt does not normally update the Purchase Order's submitted received quantity. Without an explicit duplicate guard, a network retry could therefore map and create another draft for the same remaining PO quantity.

F3F37 prevents that.

Before creating a workflow draft, RetailEdge searches draft, non-return Purchase Receipts linked through Purchase Receipt Item → Purchase Order.

Rules:

- no linked draft → one standard draft may be created;
- exactly one linked readable standard draft → reuse it idempotently;
- multiple linked drafts → fail closed to Advanced ERPNext review;
- one linked draft that the current user cannot read → fail closed;
- one linked draft that no longer matches the standard contract → fail closed.

The duplicate scan exists only for correctness and never bypasses document read permission when returning or acting on a draft.

## Standard draft equivalence

A workflow-controlled draft remains inside the simplified EdgeSuite path only while it continues to match ERPNext's current standard PO receipt mapping.

The comparison includes:

- exactly one source Purchase Order;
- Company;
- Supplier;
- mapped Branch attribution;
- Purchase Order Item identity;
- Item Code;
- positive quantity;
- receiving warehouse;
- rejected quantity;
- rate;
- conversion factor.

The same advanced stock controls remain disqualifying:

- serial number handling;
- batch handling;
- purchase Quality Inspection;
- rejected quantity;
- subcontracting;
- missing/invalid receiving warehouse.

If the PO changes, another submitted receipt changes the remaining quantities, or a user materially edits the draft, RetailEdge does not guess. The draft exits the standard path and requires Advanced ERPNext review.

Partial quantity editing remains out of scope.

## Workflow action

The POST-only `apply_standard_purchase_receipt_workflow_action` endpoint operates on the saved Purchase Receipt draft.

It:

1. validates Purchase Receipt and requested action;
2. requires normal read permission on the exact Purchase Receipt;
3. row-locks the Purchase Receipt;
4. re-reads it;
5. requires docstatus 0 so this standard slice cannot become a submitted-document cancellation path;
6. requires exactly one linked Purchase Order;
7. row-locks and revalidates that Purchase Order;
8. revalidates PO open state and Branch scope;
9. confirms this remains the only linked standard draft;
10. remaps current ERPNext receipt truth;
11. revalidates standard draft equivalence and advanced blockers;
12. confirms the active Purchase Receipt Workflow still exists;
13. rejects stale Purchase Receipt `modified`;
14. delegates to `retailedge.workflow_actions.apply_document_workflow_action` with the expected Workflow state.

The shared F3F27 bridge then recomputes currently permitted transitions and delegates to Frappe's own `apply_workflow()`.

## Stock and accounting truth

ERPNext Purchase Receipt remains the stock and accounting truth.

F3F37 does not:

- create Stock Ledger Entry directly;
- create GL Entry directly;
- use `ignore_permissions`;
- manually commit;
- assign Workflow state directly;
- assign docstatus directly;
- mutate a submitted Purchase Receipt.

If a Frappe Workflow transition moves the Purchase Receipt into a submitting state, ERPNext/Frappe performs the normal Purchase Receipt submission lifecycle and its legitimate stock/accounting consequences.

## EdgeSuite experience

The existing **Review Purchase Receipt** overlay remains the operational owner.

### No active Workflow

The existing behavior remains:

- standard preview;
- **Receive Stock** button when eligible and the user has submit permission;
- confirmation that stock will be posted;
- normal ERPNext insert + submit.

### Active Workflow, no draft yet

The overlay shows:

- standard receipt preview;
- explanation that approval starts by saving one draft;
- **Start Receipt Approval**;
- no **Receive Stock** button.

Starting approval does not post stock.

### Active Workflow, saved draft

The overlay shows:

- Purchase Receipt reference;
- current Workflow state;
- Workflow readiness message;
- only the actions currently returned by Frappe;
- next state where available.

If no action is currently available to the user, the overlay says so rather than inventing a transition.

After an intermediate transition, EdgeSuite reloads the authoritative receipt/Workflow state.

If the selected transition submits the Purchase Receipt, EdgeSuite reports successful stock receipt and refreshes Professional Purchasing.

## Approver permissions

The user who creates the workflow draft must have normal Purchase Receipt create permission.

A later approver does not need create permission merely to review an already-created draft. They must be able to read that exact Purchase Receipt and satisfy Frappe Workflow's own transition rules.

This preserves separation between operational receipt creation and approval roles.

## Branch safety

The existing RetailEdge Branch contract remains authoritative.

- The source Purchase Order Branch is revalidated for the current user.
- Restricted users cannot start or progress a receipt for an out-of-scope Purchase Order.
- Restricted users cannot receive a PO with missing Branch attribution.
- The mapped Purchase Receipt must retain the validated/mapped Branch context.
- Receiving warehouses must belong to the PO Company.

Frontend controls are not treated as the permission boundary.

## Compatibility and migration

No schema migration is required.

No custom field is added to Purchase Receipt.

Draft ownership is derived from the authoritative Purchase Receipt Item → Purchase Order links and strict standard-draft validation.

Sites without an active Purchase Receipt Workflow preserve the frozen RIR2F2D2 direct standard posting path.

## Tests required

Focused contract coverage verifies:

- preview remains read-only;
- Workflow mode is detected without persisting from preview;
- no-Workflow direct submit remains ERPNext insert + submit;
- active Workflow blocks direct submit;
- Start Receipt Approval locks/stale-checks/remaps before insert;
- Start does not submit;
- duplicate draft detection;
- one safe draft is idempotently reused;
- multiple drafts fail closed;
- existing draft requires read permission;
- Company/Supplier/Branch and single-PO validation;
- strict item quantity/rate/conversion/warehouse equivalence;
- existing serial/batch/quality/rejected/subcontracting blockers remain authoritative;
- saved-draft action row-locks and revalidates both Receipt and PO;
- stale Receipt snapshot and expected Workflow state are enforced;
- EdgeSuite distinguishes Start Approval from Receive Stock;
- only Frappe-returned workflow actions are rendered;
- UI never assigns Workflow state or docstatus;
- submitting Workflow transition reports stock received;
- shared bridge remains Frappe `apply_workflow()` authority.

The four governed exact-head gates remain:

1. RetailEdge Theme Compatibility
2. Linters
3. clean Frappe v16 standalone CI
4. EdgeSuite UI Candidate Compatibility

## Manual QA at consolidated RIR2E acceptance

Validate at least:

1. no PR Workflow + standard PO → existing Receive Stock flow still works;
2. active PR Workflow + standard PO → Receive Stock is hidden;
3. Start Receipt Approval creates one draft and does not post stock;
4. retrying Start does not create a second draft;
5. approver can reopen the PO receipt preview and see the existing draft;
6. approver without create permission can act when Frappe Workflow permits;
7. permitted actions match Frappe Workflow;
8. unavailable action is not rendered and is rejected server-side;
9. intermediate action refreshes state/actions without stock posting;
10. submitting action submits exactly one Purchase Receipt and posts stock once;
11. stale PO preview blocks Start;
12. stale Purchase Receipt snapshot blocks Workflow action;
13. multiple draft receipts linked to one PO fail closed;
14. materially edited quantity/rate/warehouse draft fails closed;
15. serial/batch/quality/rejected/subcontracting receipt remains Advanced ERPNext;
16. restricted Branch user cannot start or progress another Branch's receipt;
17. no direct GL/SLE duplicate is created by RetailEdge.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.

## Out of scope

- Partial quantity editing remains out of scope.
- Serial/batch bundle capture remains out of scope.
- Quality Inspection capture remains out of scope.
- Rejected quantity and subcontract receipt handling remain out of scope.
- Purchase Receipt return/cancellation/amendment remains out of scope.
- Purchase Invoice workflow parity remains out of scope.
- Purchase Return workflow parity remains out of scope.
- Workflow configuration UI remains out of scope.
