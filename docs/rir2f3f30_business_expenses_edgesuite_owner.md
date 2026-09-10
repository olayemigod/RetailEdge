# RIR2F3F30 — Business Expenses EdgeSuite Owner

## Goal

Turn the F3F29 Business Expense foundation into a complete normal-user EdgeSuite operational surface.

The page owns direct non-POS Business Expense capture, queueing, draft editing, evidence, record detail and workflow actions. It does not own supplier credit bills or employee reimbursement accounting semantics.

## Business boundary

- Cashier/POS spend remains RetailEdge Cashier Expense.
- Direct non-POS spend uses RetailEdge Business Expense.
- Supplier credit bills remain ERPNext Purchase Invoice.
- Employee reimbursement remains Expense Claim where installed.
- Posted financial truth remains the ERPNext accounting source surfaced by Expense Register.

Business Expenses is an operational queue, not a second financial ledger.

## EdgeSuite page

New Page: `business-expenses`.

It includes:

- current Company and Branch-aware queue;
- filters for period, Branch, Expense Category, status and search text;
- bounded pagination;
- modern guided entry;
- saved-draft editing;
- Supplier or Other/Merchant payee modes;
- Expense Category → Expense Account/Cost Centre context;
- Cash/Bank Paid From selection;
- optional Project;
- receipt/reference and evidence;
- record detail;
- workflow status and available actions;
- linked accounting reference when future posting has occurred.

No normal Business Expense action opens the native DocType form.

## Smart-form contract

All dependent options are searched through the existing F3F29 permission-aware backend:

- Company first;
- Branch filtered to the current operational scope;
- Expense Category filtered by Company;
- Paid From filtered to active Cash/Bank accounts in Company;
- Cost Centre filtered to leaf Company values;
- Project filtered to Company;
- Supplier read remains permission-aware.

Changing Company clears dependent Branch/Category/payment/cost-centre/project values. Changing Branch clears category-derived cost centre. Backend validation remains authoritative.

## Draft editing and stale safety

F3F29 supported draft create and read. This slice adds draft update.

Only docstatus 0 can be edited. Write permission is required and the displayed `modified` timestamp must still match. Status, ledger state, reviewer fields and posting references cannot be changed through the generic draft-values payload.

## Evidence

Evidence is uploaded from EdgeSuite using Frappe FileUploader.

Frappe checks write permission on the target Business Expense before saving the File. The uploaded file URL is then linked to the Business Expense Attach field only after the server verifies that the File belongs to the same document and that the document version is current.

The F3F29 submission rule remains authoritative: when RetailEdge Settings requires evidence, draft save is allowed but submission is blocked until evidence exists.

## Workflow

The page renders `workflow_readiness.available_actions` from the server.

It does not hard-code an approval sequence. Every action goes through F3F27 `apply_document_workflow_action` with expected document version and expected workflow state.

Therefore active Frappe Workflow remains authoritative. If no Frappe Workflow exists, the F3F29 RetailEdge fallback process applies.

## Expense Register handoff

For eligible consolidated users, Expense Register **Record Expense** now opens Business Expenses in new-entry mode.

Cashier-only users use the existing EdgeSuite Cashier Expense dialog with native fallback disabled.

Expense Categories route to RetailEdge Setup rather than the native Expense Category list.

Generic native DocType/Report navigation from Expense Register now also respects final `can_use_native_desk`.

## Navigation

The final Expenses group adds Business Expenses when the feature is enabled and the current user may open the Page.

Raw RetailEdge Business Expense is removed as an everyday peer if present.

Raw RetailEdge Expense Category is removed from the normal Expenses group when the EdgeSuite Setup owner is available.

## Accounting boundary

Accounting posting remains out of scope for F3F30.

This slice does not:

- create Journal Entry, Payment Entry or GL Entry;
- mark a Business Expense Posted;
- mutate a posting reference;
- change Cashier Expense posting;
- change ERPNext Purchase Invoice or Expense Claim behavior;
- mutate submitted accounting documents.

No submitted accounting document is mutated.

## Next

F3F31 should implement the separately gated accounting-posting action for Approved/Pending Ledger Business Expenses, with idempotency and ERPNext Journal Entry lifecycle safety, then reconcile Expense Register de-duplication.

Manual browser/persona QA remains deferred to consolidated RIR2E acceptance.
