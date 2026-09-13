# RIR2F3F39 — Purchase Return / Supplier Debit Note Workflow Precedence

## Goal

Apply F3F27 workflow precedence to the existing F3F17 standard Purchase Return and Supplier Debit Note EdgeSuite completion paths without changing ERPNext return, stock, valuation, tax, payable or accounting truth.

Purchase Return and Supplier Debit Note remain separate explicit business intents. RetailEdge never automatically creates one because the other exists.

## Existing F3F17 contract

F3F17 already owns the normal standard return completion surface:

- Purchase Receipt return uses ERPNext `make_purchase_return`;
- Supplier Debit Note uses ERPNext `make_debit_note`;
- preview maps in memory only and is persistence-free;
- source and mapped target Company, Supplier, Branch, `is_return`, `return_against` and negative quantities are validated;
- Serial Number and Batch-controlled stock returns fail closed to Advanced ERPNext;
- direct standard completion locks and stale-checks the submitted source, remaps current truth, inserts the canonical target and calls ERPNext `submit()`;
- source documents are never mutated by RetailEdge;
- ERPNext alone owns stock/accounting effects.

F3F39 preserves that contract and adds active Frappe Workflow precedence.

## Workflow precedence

The mapped target DocType controls the return:

- Purchase Receipt Workflow controls Purchase Receipt returns;
- Purchase Invoice Workflow controls Supplier Debit Notes.

Rules:

1. active Frappe Workflow is authoritative;
2. without an active target Workflow, the existing F3F17 one-step insert + submit path remains;
3. with an active target Workflow, EdgeSuite does not direct-submit the unsaved mapper result;
4. EdgeSuite never applies Workflow to an unsaved return;
5. exactly one canonical return draft is persisted or idempotently reused before workflow actions are exposed;
6. no RetailEdge fallback Workflow is invented.

EdgeSuite never assigns workflow state or docstatus directly.

## Preview

`get_purchase_return_review` remains persistence-free.

It:

1. loads and validates the submitted non-return source;
2. maps current canonical ERPNext return truth;
3. reuses the existing F3F17 target and stock-control validation;
4. detects whether the target DocType has an active Frappe Workflow;
5. if no active Workflow exists, preserves the normal F3F17 review;
6. if an active Workflow exists and no saved return draft exists, exposes **Start Return Approval** or **Start Debit Note Approval**;
7. if exactly one linked draft exists, validates it against current ERPNext mapping and returns its authoritative workflow readiness.

Merely opening the preview never persists a target.

## Why a saved draft is required

Frappe Workflow actions operate on persisted documents.

ERPNext's return mappers initially return unsaved Purchase Receipt / Purchase Invoice return documents. F3F39 therefore persists a draft only when an active Workflow requires it, and only after the submitted source has been row-locked, stale-checked and remapped.

Starting approval does not post stock or accounting.

## Duplicate prevention

A draft return does not complete the source return lifecycle. Retrying a workflow-start request must not silently create another return draft.

For the exact source DocType and source name, F3F39 searches for draft documents where:

- `docstatus = 0`;
- `is_return = 1`;
- `return_against = source.name`.

Rules:

- no linked draft → one standard draft may be inserted;
- exactly one readable linked standard draft → reuse it idempotently;
- multiple linked drafts → fail closed to Advanced ERPNext review;
- unreadable linked draft → fail closed;
- linked draft that no longer matches the standard contract → fail closed.

The duplicate guard applies to the standard workflow path and does not rewrite or delete advanced drafts.

## Standard draft equivalence

A saved workflow draft remains in the standard EdgeSuite path only while it matches the current canonical ERPNext return mapping.

Validation includes:

- target DocType;
- draft docstatus;
- `is_return = 1`;
- exact `return_against`;
- Company;
- Supplier;
- Branch;
- Purchase Invoice `update_stock` where applicable;
- all item quantities remain negative;
- source child-row identity where ERPNext exposes it;
- Item Code;
- quantity;
- warehouse;
- rate;
- conversion factor;
- Serial Number / Batch standard-path exclusions.

The saved draft item signature must match a freshly mapped ERPNext target. If another return or source change alters current returnable truth, the saved draft exits the standard path rather than being guessed or silently rewritten.

Partial/custom quantity editing remains out of scope.

## Start approval

The POST-only `start_purchase_return_workflow` endpoint:

1. row-locks the submitted source;
2. revalidates source read/scope and non-return status;
3. confirms an active Frappe Workflow controls the target DocType;
4. stale-checks `expected_source_modified`;
5. remaps current ERPNext return truth;
6. re-runs F3F17 advanced blockers;
7. searches for linked draft returns;
8. idempotently reuses one valid standard draft when present;
9. otherwise requires normal target create permission and inserts exactly one canonical draft;
10. verifies the saved draft remains standard-equivalent;
11. returns current Frappe workflow readiness.

The endpoint never calls `submit()`.

## Workflow action

The POST-only `apply_purchase_return_workflow_action` endpoint:

1. requires source identity, exact saved target and requested action;
2. row-locks and revalidates the submitted source;
3. rejects stale source `modified`;
4. requires the exact target to exist and be readable;
5. row-locks the target;
6. requires the target to remain draft;
7. requires the source to have exactly that single linked draft;
8. confirms the target DocType still has an active Frappe Workflow;
9. remaps current ERPNext return truth;
10. re-runs F3F17 blockers;
11. validates saved-draft equivalence;
12. rejects stale target `modified`;
13. delegates to `retailedge.workflow_actions.apply_document_workflow_action` with expected workflow state.

The shared F3F27 bridge recomputes currently permitted transitions and delegates to Frappe `apply_workflow()`.

Frappe therefore remains authoritative for transition role, conditions, self-approval, state updates, docstatus changes and submit transitions.

## Direct submit without Workflow

`submit_purchase_return_review` keeps the F3F17 behavior only when no active target Workflow exists.

It still:

- row-locks the source;
- requires normal target create and submit permissions;
- stale-checks the source;
- remaps the target;
- re-runs all standard blockers;
- inserts and submits through ERPNext.

If an active target Workflow exists, direct submission is rejected and EdgeSuite directs the user to start approval.

## Stock and accounting truth

ERPNext remains the return, stock, valuation and accounting truth.

F3F39 does not:

- mutate a submitted source;
- create Stock Ledger Entry directly;
- create GL Entry directly;
- create Payment Entry or Journal Entry directly;
- assign workflow state directly;
- assign docstatus directly;
- use `ignore_permissions=True`;
- manually commit;
- auto-chain Purchase Return and Supplier Debit Note.

If a Frappe Workflow transition submits the return/debit note, ERPNext/Frappe alone performs legitimate stock, valuation, tax, payable and accounting consequences.

## EdgeSuite experience

### No active target Workflow

The frozen F3F17 behavior remains:

- review canonical mapped return;
- show standard blockers;
- confirm and submit through ERPNext;
- Native-Desk-capable users retain explicit **Advanced: Prepare in ERPNext** fallback.

### Active target Workflow, no draft yet

The overlay shows:

- mapped return context and items;
- Workflow name;
- readiness explanation;
- **Start Return Approval** or **Start Debit Note Approval**;
- no direct submit button.

Starting approval saves one draft only. It does not post.

### Active target Workflow, saved draft

The overlay shows:

- exact return draft name;
- Workflow name and current state;
- only actions returned by Frappe;
- next state when available.

After an intermediate transition, the overlay refreshes current source/target truth and workflow actions.

If a transition submits the target, the overlay closes, reports completion and refreshes Professional Purchasing.

## Compatibility and migration

No schema migration is required.

No custom field or new DocType is introduced.

Sites without an active Purchase Receipt/Purchase Invoice Workflow preserve the F3F17 direct standard path.

Existing advanced draft-preparation endpoints remain explicit Native Desk fallback tools and are not promoted into the standard workflow path.

## Tests required

Focused contract coverage must prove:

- F3F17 preview remains persistence-free;
- no-Workflow direct insert + submit remains;
- active Workflow blocks direct submit;
- workflow start locks/stale-checks/remaps source before persistence;
- workflow start does not submit;
- duplicate linked draft detection and idempotent reuse;
- multiple/unreadable/non-standard drafts fail closed;
- standard draft equivalence covers return linkage, Company/Supplier/Branch, Update Stock and canonical item signature;
- Serial Number and Batch exclusions remain authoritative;
- saved-draft action locks/revalidates source and target;
- stale source and target snapshots are enforced;
- expected workflow state is passed to the shared bridge;
- UI distinguishes Start Approval, Workflow Actions and direct Submit;
- UI renders only Frappe-returned actions;
- UI never assigns workflow state or docstatus;
- Purchase Return and Supplier Debit Note remain separate intents;
- shared F3F27 bridge remains Frappe `apply_workflow()` authority;
- no direct GL/SLE/payment/journal mutation is added.

The four governed exact-head gates remain:

1. RetailEdge Theme Compatibility
2. Linters / Semgrep / vulnerable dependency audit
3. clean Frappe v16 standalone CI
4. EdgeSuite UI Candidate Compatibility

## Manual QA at consolidated RIR2E acceptance

Validate at least:

1. no Purchase Receipt Workflow + standard Purchase Receipt source → existing direct Purchase Return works;
2. active Purchase Receipt Workflow → direct submit hidden and Start Return Approval shown;
3. no Purchase Invoice Workflow + standard Purchase Invoice source → existing direct Supplier Debit Note works;
4. active Purchase Invoice Workflow → direct submit hidden and Start Debit Note Approval shown;
5. Start Approval creates exactly one draft and posts nothing;
6. retrying Start reuses the same valid draft;
7. multiple linked return drafts fail closed;
8. materially edited return draft fails closed;
9. stale source blocks Start/Action;
10. stale saved target blocks Action;
11. Frappe-permitted actions and states match EdgeSuite;
12. intermediate action does not directly post stock/accounting;
13. submitting transition posts through ERPNext exactly once;
14. Serial/Batch return remains advanced;
15. restricted Branch user cannot act outside scope;
16. Purchase Return never auto-creates Supplier Debit Note and vice versa;
17. no duplicate GL/SLE/payment/journal side effect is created by RetailEdge.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.

## Out of scope

- automatic Purchase Return + Supplier Debit Note pairing;
- serial/batch bundle capture;
- generic partial/custom return editing;
- cancellation/amendment workflow;
- tax/accounting override editing;
- Incoming Quality Inspection or Landed Cost changes;
- Workflow configuration UI.
