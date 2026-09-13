# RIR2F3F27 — EdgeSuite Workflow Execution Foundation

## Goal

Make EdgeSuite capable of following the authoritative ERPNext/Frappe Workflow configured for a document instead of merely reporting that a workflow exists.

This foundation is required by the RetailEdge Expense Entry experience and becomes the reusable product rule for EdgeSuite transaction pages.

## Governing Rule

For any EdgeSuite-owned document surface:

1. If the underlying DocType has an active Frappe Workflow, that Workflow is authoritative.
2. EdgeSuite must display the live workflow state and only the transitions returned as permitted for the current user.
3. EdgeSuite must execute the selected action through Frappe's own `frappe.model.workflow.apply_workflow()`.
4. EdgeSuite must never assign the workflow state field or `docstatus` directly.
5. Frappe transition conditions, role checks, self-approval rules, state update fields, transition tasks, submit/cancel behavior and document validation remain authoritative.
6. If no active Frappe Workflow exists, a documented RetailEdge-owned lifecycle may be used only when its RetailEdge setting enables it.
7. If neither exists, ordinary document save/submit permissions apply; EdgeSuite must not invent an approval workflow.

Frappe v16 source confirms that `apply_workflow` obtains the live permitted transitions, validates the selected action and approval access, updates the configured workflow state, and then performs the required save/submit/cancel operation through the document lifecycle rather than bypassing it.

## Cashier Expense precedence

`RetailEdge Cashier Expense` now follows:

- active Frappe Workflow → Frappe Workflow;
- otherwise `RetailEdge Settings.enable_cashier_expense_workflow = 1` → RetailEdge Cashier Expense lifecycle;
- otherwise → no RetailEdge workflow is claimed and normal document rules apply.

This corrects the prior readiness helper, which always advertised the RetailEdge fallback lifecycle even when its setting was disabled.

## Transition API

`retailedge.workflow_actions.apply_document_workflow_action` is POST-only and:

- loads the current stored document;
- requires read permission;
- optionally verifies the expected `modified` timestamp;
- optionally verifies the expected workflow state;
- re-checks the live permitted transition list;
- delegates active Frappe Workflow actions to `frappe.model.workflow.apply_workflow`;
- delegates the settings-enabled Cashier Expense fallback only to its existing submit/approve/reject/reopen functions;
- returns fresh workflow readiness after the action.

Rejecting a Cashier Expense through the fallback lifecycle requires remarks, preserving the existing review expectation.

## Stale-client safety

Expense Entry and other EdgeSuite pages must send the version/state they displayed before applying a transition. If the document changed or its workflow state moved, the server fails closed and the page must refresh before proceeding.

This prevents two reviewers from acting on stale workflow assumptions.

## Explicitly prohibited

The bridge must not:

- set `workflow_state` directly;
- set `docstatus` directly;
- use `ignore_permissions`;
- call `frappe.db.commit()`;
- bypass Workflow conditions;
- manufacture actions based on frontend roles;
- submit a document merely because an EdgeSuite button was displayed.

## Expense Entry dependency

The next bounded slice will build the Expense Entry page on this foundation. The page will:

- capture expense information and evidence in EdgeSuite;
- create the correct underlying draft transaction;
- render workflow state/history/readiness;
- render only server-returned workflow actions;
- apply them through this bridge;
- remain on EdgeSuite after transition.

## Wider MVP rule

Every existing RetailEdge EdgeSuite owner that supports a workflow-capable ERPNext/Frappe document must be audited before MVP freeze. Active ERPNext Workflow cannot become a reason to push normal users into native Desk.

## Tests

The slice requires:

- active Frappe Workflow precedence;
- live-transition fail-closed behavior;
- settings-gated Cashier Expense fallback;
- stale `modified` protection;
- stale state protection;
- no direct state/docstatus mutation;
- no permission bypass or manual commit;
- all four governed PR #55 gates on one exact head.

Manual browser/persona workflow QA remains part of consolidated RIR2E acceptance.
