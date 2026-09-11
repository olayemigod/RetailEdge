# RIR2F3F35 — Payment Entry Workflow Precedence

## Goal

Apply the F3F27 EdgeSuite workflow rule to standard Payment Entry submission.

Customer receipts/customer advances and supplier invoice payments are already owned by EdgeSuite review flows. When Payment Entry has an active Frappe Workflow, those EdgeSuite flows must honor that Workflow instead of bypassing it with a direct `doc.submit()`.

## Precedence

For Payment Entry:

1. active Frappe Workflow is authoritative;
2. when no active Workflow exists, the existing standard EdgeSuite direct-submit path may be used if all existing standard-shape and permission checks pass;
3. no RetailEdge fallback workflow is invented for Payment Entry.

This slice does not change the Frappe Workflow configuration itself.

## Backend preview contract

Both:

- `standard_customer_payment_submit`;
- `standard_supplier_payment_submit`

now load shared workflow readiness through the F3F27 `get_workflow_readiness()` service.

Preview payloads expose:

- workflow source;
- Workflow name;
- current Workflow state;
- currently permitted actions;
- next states;
- Workflow message;
- `workflow_eligible`.

## Direct submit safety

If an active Frappe Workflow exists, standard direct submit is blocked.

The existing submit endpoints continue to row-lock, re-read, revalidate scope and stale state, then call the existing blocker service before `doc.submit()`.

The blocker service now treats an active Frappe Workflow as authoritative and therefore prevents the direct submit call from being reached.

Direct **Submit Payment** is available only when:

- no active Payment Entry Workflow exists;
- the Payment Entry is still a supported standard payment shape;
- Company/Branch/party/reference/account checks pass;
- normal Payment Entry submit permission exists.

ERPNext remains authoritative for the actual Payment Entry submission and its GL, Payment Ledger and outstanding-balance side effects.

## Workflow eligibility and complex payments

An active Workflow does not automatically make every Payment Entry suitable for EdgeSuite workflow execution.

EdgeSuite surfaces Workflow buttons only when the draft has no blocker other than the active-Workflow blocker itself.

Therefore complex or unsupported Payment Entry shapes remain Advanced ERPNext review, including existing exclusions such as:

- unsupported payment type/party shape;
- multi-currency standard-payment cases;
- multi-document allocation;
- unsupported return allocation;
- deductions or exchange-difference cases;
- incomplete accounts;
- unsupported supplier advances;
- allocation/outstanding mismatches;
- Branch or Company scope mismatches.

This preserves the existing standard-payment explanation boundary while still honoring Workflow for supported payments.

## EdgeSuite workflow actions

When a supported Payment Entry is workflow-controlled, EdgeSuite shows only the transitions returned by Frappe for the current user and document state.

The two owning UI surfaces are:

- Payment Management customer draft review;
- Business Hub Simple Payment review for customer and supplier payments.

Both delegate actions to:

`retailedge.workflow_actions.apply_document_workflow_action`

Each call supplies:

- `doctype = Payment Entry`;
- document name;
- selected Workflow action;
- expected `modified`;
- expected Workflow state.

The shared F3F27 bridge then revalidates the snapshot, checks the action is currently permitted and calls Frappe's own `apply_workflow()`.

EdgeSuite never writes `workflow_state` or `docstatus` directly.

## UI behavior

For an eligible workflow-controlled Payment Entry:

- status displays Workflow / Workflow Action Required rather than Advanced Review;
- direct **Submit Payment** is hidden;
- current Workflow and state are shown;
- permitted Workflow actions are rendered in EdgeSuite;
- if no action is permitted for the current user, EdgeSuite says so instead of inventing a transition;
- Advanced ERPNext remains an explicit fallback only where that surface already permits native Desk.

After a Workflow action:

- the authoritative payment preview/list is refreshed;
- if the Payment Entry remains draft, the new Workflow state/actions are shown;
- if the transition submits the Payment Entry, normal ERPNext balances/ledger remain authoritative and the draft leaves the draft queue.

## Customer payment scope

Existing customer-payment rules remain unchanged:

- Receive / Customer Payment Entry only;
- Company and Customer validation;
- Branch attribution/access;
- one supported Sales Invoice allocation or customer advance;
- company-currency standard shape;
- positive amount;
- account completeness;
- current Sales Invoice outstanding validation.

Workflow precedence does not weaken any of those checks.

## Supplier payment scope

Existing supplier-payment rules remain unchanged:

- Pay / Supplier Payment Entry only;
- Company and Supplier validation;
- Branch attribution/access;
- one supported Purchase Invoice allocation;
- no standard supplier advance;
- company-currency standard shape;
- Bank/Cash payment account;
- Supplier payable account;
- full supported allocation;
- positive current Purchase Invoice outstanding.

Workflow precedence does not weaken any of those checks.

## Accounting safety

F3F35 does not create a new payment ledger or mutate accounting directly.

It does not:

- write GL Entry;
- write Payment Ledger Entry;
- directly update Sales Invoice outstanding;
- directly update Purchase Invoice outstanding;
- directly update customer/supplier balances;
- assign Workflow state;
- assign docstatus;
- use `ignore_permissions`;
- manually commit.

Payment Entry and Frappe Workflow remain the authoritative engines.

## Compatibility

No schema migration is required.

Existing Payment Entries remain unchanged.

Sites without an active Payment Entry Workflow preserve the F3F1/F3F2 direct standard-submit behavior.

Sites with an active Payment Entry Workflow now receive the F3F27 precedence that was previously missing.

## Tests required

Focused contract coverage verifies:

- customer preview includes shared workflow readiness;
- supplier preview includes shared workflow readiness;
- active Workflow blocks direct customer submit;
- active Workflow blocks direct supplier submit;
- submit permission is consulted only for the direct no-Workflow path;
- Workflow eligibility requires no additional standard-shape blockers;
- Payment Management uses the shared workflow-action bridge;
- Business Hub customer review uses the same bridge;
- Business Hub supplier review uses the same bridge;
- stale `modified` and expected Workflow state are passed;
- direct Submit Payment is hidden when Workflow owns the document;
- UI does not assign state/docstatus directly;
- shared F3F27 bridge continues to call Frappe `apply_workflow()`.

The four governed exact-head gates remain:

1. RetailEdge Theme Compatibility
2. Linters
3. clean Frappe v16 standalone CI
4. EdgeSuite UI Candidate Compatibility

## Manual QA at consolidated RIR2E acceptance

Validate at least:

1. no Payment Entry Workflow + standard customer payment → direct Submit Payment remains available;
2. no Payment Entry Workflow + standard supplier payment → direct Submit Payment remains available;
3. active Workflow + supported customer payment → direct Submit Payment disappears;
4. active Workflow + supported supplier payment → direct Submit Payment disappears;
5. available Frappe actions appear in EdgeSuite;
6. user sees only actions permitted by Workflow role/condition;
7. stale Workflow state/modified blocks the transition;
8. intermediate draft transition refreshes the state/actions without posting;
9. submit-state transition posts through Frappe Workflow and removes the draft from the queue;
10. complex customer payment remains Advanced ERPNext even when Workflow is active;
11. complex supplier payment remains Advanced ERPNext even when Workflow is active;
12. Branch-restricted user cannot workflow-process an out-of-scope payment;
13. invoice outstanding changes only through authoritative ERPNext posting;
14. no duplicate Payment Entry or GL/Payment Ledger write is created.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.

## Out of scope

Purchase Order, Purchase Receipt, Purchase Invoice and purchase-return workflow parity are separate slices.

Also out of scope:

- multi-currency standard-payment expansion;
- multi-document standard-payment expansion;
- Payment Reconciliation;
- Payment Orders;
- Workflow configuration UI;
- RetailEdge-specific Payment Entry approval settings.
