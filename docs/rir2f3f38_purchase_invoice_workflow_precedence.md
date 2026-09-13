# RIR2F3F38 — Purchase Invoice Workflow Precedence

## Goal

Apply the shared F3F27 workflow-precedence rule to the existing F3F20 Supplier Document → Purchase Invoice EdgeSuite completion path without creating a second Purchase Invoice lifecycle.

The generic Guided Purchase Invoice flow remains draft-only in this slice. F3F38 is limited to the already-persisted, immutable Supplier Document Purchase Invoice Handoff because that is the bounded EdgeSuite-owned standard Purchase Invoice completion path that currently calls ERPNext `Purchase Invoice.submit()`.

## Existing ownership

F3F20 already establishes the safe Purchase Invoice boundary:

- accepted Supplier Document Intake and accepted extraction evidence are required;
- ERPNext `make_purchase_invoice(po.name)` prepares the authoritative Purchase Invoice draft from the submitted Purchase Order;
- the immutable `Supplier Document Purchase Invoice Handoff` identifies the exact draft that may be reviewed;
- extracted currency and total are advisory reconciliation evidence only;
- standard completion excludes `Update Stock`, missing/mismatched reconciliation evidence and broken Purchase Order linkage;
- Company, Supplier, Branch, normal document permissions and stale `modified` are revalidated server-side;
- ERPNext Purchase Invoice submission owns accounting consequences.

F3F38 preserves that contract and adds active Frappe Workflow precedence.

## Workflow precedence

For the handed-off Purchase Invoice:

1. active Frappe Workflow is authoritative;
2. when no active Frappe Workflow exists, the frozen F3F20 direct standard submit path remains available;
3. when an active Frappe Workflow exists, direct `Purchase Invoice.submit()` is blocked from the EdgeSuite standard path;
4. EdgeSuite may expose only workflow actions returned by Frappe for an otherwise-standard F3F20 draft;
5. no RetailEdge fallback Purchase Invoice workflow is invented.

EdgeSuite never assigns workflow state or docstatus directly.

## Generic Guided Purchase Invoice

`retailedge.guided_purchase_invoice.create_simple_purchase_invoice_draft` remains draft-only.

F3F38 does not turn Guided Purchase Invoice into a submit, approval or accounting engine. A future ownership decision may extend generic draft completion, but this slice does not broaden the frozen F3F20 handoff contract.

## Review payload

The existing Supplier Document Purchase Invoice review continues to load the exact Purchase Invoice referenced by the immutable handoff.

The review now also returns shared workflow readiness from `get_workflow_readiness(doctype="Purchase Invoice", doc=purchase_invoice)`.

When a Frappe Workflow is active:

- `workflow_readiness.source` is `frappe`;
- the workflow name, current state, permitted actions and next states come from Frappe;
- direct `can_submit` is false;
- the active-workflow blocker is distinguished from business-shape blockers;
- `workflow_eligible` is true only when the active-workflow blocker is the only blocker and the document remains a draft.

This distinction is important: active Workflow should prevent direct submit, but it should not incorrectly classify an otherwise-standard invoice as an advanced accounting case.

## Existing standard blockers remain authoritative

Workflow actions are available only while the handed-off Purchase Invoice remains within the existing F3F20 standard contract.

The following remain advanced / fail-closed:

- missing extracted currency;
- extracted currency mismatch;
- missing extracted total;
- extracted total differing from ERPNext mapped grand total beyond 0.01 tolerance;
- `Update Stock`;
- no mapped items;
- any item no longer linked to the authoritative Purchase Order;
- invalid Supplier, Company or Branch authority;
- missing/read-denied immutable handoff;
- stale document state;
- any unexpected non-draft lifecycle state.

F3F38 does not add multi-document, Update Stock, stock bundle, serial/batch, tax editing, account editing or generic invoice editing capability.

## Direct submit without Workflow

`submit_supplier_document_purchase_invoice` preserves the F3F20 path when no active Purchase Invoice Workflow exists.

It:

1. resolves and row-locks the exact handed-off Purchase Invoice;
2. revalidates intake, extraction, Purchase Order, Supplier, Company and Branch authority;
3. returns idempotently if the handed-off invoice is already submitted;
4. requires a draft otherwise;
5. stale-checks `expected_purchase_invoice_modified`;
6. rebuilds the authoritative review;
7. rejects active Frappe Workflow;
8. rejects all normal F3F20 blockers;
9. calls normal ERPNext `purchase_invoice.submit()`.

No alternate accounting path is introduced.

## Workflow action endpoint

The POST-only `apply_supplier_document_purchase_invoice_workflow_action` endpoint:

1. requires an explicit workflow action;
2. resolves the exact immutable handoff with the Purchase Invoice row locked;
3. revalidates normal read permission and Supplier Document authority;
4. requires the Purchase Invoice to remain draft;
5. stale-checks the expected Purchase Invoice `modified` snapshot;
6. rebuilds the authoritative F3F20 review and Branch/Company/Supplier/PO reconciliation;
7. requires `workflow_eligible`;
8. delegates to `retailedge.workflow_actions.apply_document_workflow_action` with the expected workflow state.

The shared F3F27 bridge recomputes currently permitted actions and delegates to Frappe `apply_workflow()`.

Frappe therefore remains authoritative for:

- transition role;
- transition condition;
- self-approval rules;
- workflow state;
- update fields;
- docstatus transition;
- any submit transition.

## Accounting and stock truth

ERPNext Purchase Invoice remains the accounting and payable truth.

F3F38 does not:

- create or mutate GL Entry directly;
- create or mutate Stock Ledger Entry directly;
- create Payment Entry directly;
- update invoice outstanding directly;
- assign workflow state directly;
- assign docstatus directly;
- use `ignore_permissions` in the standard completion/action path;
- manually commit;
- mutate a submitted Purchase Invoice.

If a Frappe Workflow action submits the Purchase Invoice, ERPNext/Frappe performs the legitimate Purchase Invoice validation, tax, payable, GL, Payment Ledger, outstanding and any supported stock consequences.

`Update Stock` remains outside the standard F3F38 path.

## EdgeSuite experience

The existing Supplier Document Review Purchase Invoice panel remains the operational owner.

### No active Purchase Invoice Workflow

- reconciled standard draft shows **Submit Purchase Invoice**;
- submission uses the existing F3F20 endpoint;
- Advanced ERPNext remains visible only to Native-Desk-capable users.

### Active Purchase Invoice Workflow

- direct **Submit Purchase Invoice** is hidden;
- Workflow name and current state are shown;
- the Frappe readiness message is shown;
- only actions returned in `workflow_readiness.available_actions` are rendered;
- next state is shown when available;
- selecting an action sends the stale `modified` and expected workflow state snapshot;
- after every action, the Supplier Document queue and exact Purchase Invoice review are refreshed;
- if the action submits the Purchase Invoice, the UI reports successful workflow submission.

If no action is currently available, EdgeSuite does not invent one.

## Compatibility and migration

No schema migration is required.

No new DocType or custom field is introduced.

Sites without an active Purchase Invoice Workflow retain the F3F20 direct standard submission contract.

The immutable Supplier Document Purchase Invoice Handoff remains the durable identity/idempotency boundary.

## Tests required

Focused contract coverage must prove:

- Guided Purchase Invoice remains draft-only;
- Supplier Document review loads shared Purchase Invoice workflow readiness;
- direct submit is disabled when active Frappe Workflow exists;
- active Workflow is separated from real F3F20 business-shape blockers;
- workflow eligibility requires an otherwise-standard draft;
- direct submit explicitly rejects active Workflow before `purchase_invoice.submit()`;
- workflow action resolves and row-locks the exact handed-off Purchase Invoice;
- stale Purchase Invoice snapshot is required;
- F3F20 Supplier/Company/Branch/PO/reconciliation checks are rebuilt before workflow delegation;
- expected Workflow state is passed to the shared F3F27 bridge;
- the UI renders only returned workflow actions;
- the UI sends expected `modified` and workflow state;
- direct Submit Purchase Invoice is not rendered in active-Workflow mode;
- the UI never assigns workflow state or docstatus;
- shared workflow bridge remains Frappe `apply_workflow()` authority;
- ERPNext remains accounting truth and no direct GL/SLE/payment mutation is added.

The four governed exact-head gates remain:

1. RetailEdge Theme Compatibility
2. Linters / Semgrep / vulnerable dependency audit
3. clean Frappe v16 standalone CI
4. EdgeSuite UI Candidate Compatibility

## Manual QA at consolidated RIR2E acceptance

Validate at least:

1. no Purchase Invoice Workflow + standard F3F20 handoff → direct Submit Purchase Invoice remains available;
2. active Purchase Invoice Workflow + standard F3F20 handoff → direct submit is hidden;
3. workflow name/state/actions match Frappe;
4. unavailable workflow action is not rendered and is rejected server-side;
5. intermediate workflow action refreshes the authoritative invoice state without direct accounting mutation;
6. submit transition submits exactly the handed-off Purchase Invoice once;
7. stale Purchase Invoice snapshot blocks action;
8. changed Supplier/Company/Branch/PO authority blocks action;
9. Update Stock remains advanced;
10. extraction currency/total mismatch remains advanced;
11. EdgeSuite-only user does not require Native Desk for a permitted standard workflow action;
12. Native-Desk-capable user retains the explicit Advanced ERPNext fallback;
13. no duplicate GL/SLE/Payment Entry is created by RetailEdge.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.

## Out of scope

- generic Purchase Invoice editing;
- Guided Purchase Invoice submit redesign;
- Update Stock Purchase Invoice completion;
- multi-document or multi-currency expansion beyond the existing F3F20 contract;
- Purchase Return workflow parity;
- Payment Reconciliation or Payment Order changes;
- Workflow configuration UI;
- manual browser/persona QA before consolidated RIR2E acceptance.
