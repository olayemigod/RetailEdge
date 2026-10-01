# RetailEdge Sales & Purchase Persistent Workflow Guide

## Purpose

This guide defines the RetailEdge entry and completion contract for Sales Invoices and direct Purchase Invoices.

The business rule is simple:

- **Quick Sale / Quick Purchase are fast draft-entry surfaces.**
- **Make Sale / Record Purchase are the persistent working surfaces.**
- **Approval and submission happen on the persistent page, not in a second completion popup.**
- **ERPNext and active Frappe Workflow remain authoritative for document submission, accounting, stock, payables and receivables.**

This avoids nested modal workflows, protects longer transaction work, and gives users one durable place to review status and complete a transaction.

## Surface ownership

| Business action | Entry surface | What it may do | Completion owner |
| --- | --- | --- | --- |
| Quick Sale | EdgeSuite modal | Create a small Sales Invoice draft only | Make Sale |
| Make Sale | Persistent EdgeSuite page | Create/edit draft, show blockers, run Workflow action or native submit, continue to payment/delivery/return/output | Make Sale |
| Professional Selling | Persistent EdgeSuite page and governed review surfaces | Quotation, Sales Order, Delivery, source-linked invoice and return workflows | Professional Selling |
| Quick Purchase | EdgeSuite modal | Create a small direct Purchase Invoice draft only | Record Purchase |
| Record Purchase – Direct | Persistent EdgeSuite page | Create/edit direct Purchase Invoice, show blockers, run Workflow action or native submit, continue to settlement/payables/output | Record Purchase |
| Standard Purchase | Professional Purchasing | Purchase Order → Purchase Receipt → Purchase Invoice → Payment | Professional Purchasing |
| Source-linked Purchase Invoice | Professional Purchasing governed completion | Preserve Purchase Order / Purchase Receipt ownership | Professional Purchasing |

## Quick-entry contract

Quick Sale and Quick Purchase are deliberately bounded entry surfaces. They must not become approval or accounting workspaces.

After a successful draft save:

1. Close the quick-entry modal.
2. Store the saved document name in the user-scoped handoff.
3. Route to the persistent page.
4. Reload the saved ERPNext draft through the permission-aware completion preview.
5. Show the workflow/submission section on the page.
6. Do not automatically put the page into edit mode.
7. Allow the user to choose **Continue Editing on Page** when edits are needed.

Unsaved quick-entry work must continue to warn before discard. Any Frappe confirmation opened over an EdgeSuite modal must be elevated above the active modal/backdrop.

## Persistent Sales Invoice contract

For a draft Sales Invoice on **Make Sale**:

- The page displays a **Workflow & submission** section.
- If an active Frappe Workflow owns the document, only the server-returned workflow actions are shown.
- If no active Workflow owns the document and ERPNext permits submission, show **Submit Sales Invoice**.
- Blockers returned by the server are visible on the page.
- **Refresh Status** reloads the authoritative document version and workflow state.
- Stale-document protection uses the reviewed `modified` timestamp.
- Workflow actions send the current workflow state for stale-state protection.
- Submitted Sales Invoices are never mutated. Follow-up actions create or allocate the appropriate ERPNext documents.

After submission, permitted next actions may include:

- Record Payment
- Create Delivery Note
- Return / Credit Note
- Print / Share

The page refreshes the authoritative selling action list after completion and after payment.

## Persistent direct Purchase Invoice contract

For a draft direct Purchase Invoice on **Record Purchase**:

- The page displays a **Workflow & submission** section.
- Active Frappe Workflow takes precedence over direct submit.
- Without an active Workflow, **Submit Purchase Invoice** is shown only when the backend says submission is allowed.
- Branch, stock location, item access, source ownership and accounting blockers continue to be revalidated server-side.
- Workflow actions use the reviewed `modified` value and current workflow state.
- Direct Purchase source mode remains `direct`.

After submission, permitted next actions may include:

- Pay Supplier
- Supplier Debit Note
- Supplier Payables
- Print / Share

## Standard purchasing contract

Do not collapse standard procurement into Direct Purchase.

The normal stock procurement sequence remains:

**Purchase Order → Purchase Receipt → Purchase Invoice → Payment**

Purchase Order, Purchase Receipt and source-linked Purchase Invoice completion remain owned by Professional Purchasing. Existing Frappe Workflow precedence is preserved:

- active Workflow → use permitted Workflow actions;
- no active Workflow → native ERPNext submit may be offered if the user has permission and validation passes.

## Accounting and stock safety

The persistent pages do not write GL Entry, Payment Ledger Entry, Stock Ledger Entry or workflow state directly.

They call the existing permission-aware RetailEdge completion services, which in turn delegate to ERPNext/Frappe:

- `submit_standard_sales_invoice`
- `apply_standard_sales_invoice_workflow_action`
- `submit_standard_purchase_invoice`
- `apply_standard_purchase_invoice_workflow_action`

Safety requirements:

- never mutate a submitted accounting document;
- fail closed on permission, branch, company, source or stale-version conflicts;
- keep active Frappe Workflow authoritative;
- keep Purchase Order / Purchase Receipt source ownership intact;
- preserve tenant/company/branch filtering;
- revalidate stock location and item access on the backend.

## QA checklist

### A. Quick Sale → Make Sale

1. Open Quick Sale.
2. Enter Customer, Branch/Stock Location and one item.
3. Save Draft.
4. Confirm the quick modal closes.
5. Confirm route changes to `/app/make-sale`.
6. Confirm the saved Sales Invoice name appears.
7. Confirm **Workflow & submission** is on the page.
8. Confirm no **Complete Sales Invoice** modal opens.
9. Confirm the page does not automatically enter draft edit mode.
10. Select **Continue Editing on Page** and verify the saved draft reloads before editing.

### B. Sales Invoice without Frappe Workflow

1. Use a role with Sales Invoice submit permission.
2. Save a valid draft.
3. Confirm **Submit Sales Invoice** appears on Make Sale.
4. Submit.
5. Confirm ERPNext sets `docstatus = 1`.
6. Confirm accounting/stock behaviour matches the invoice configuration.
7. Confirm submitted next actions are refreshed on the page.

### C. Sales Invoice with active Frappe Workflow

1. Activate a valid Sales Invoice Workflow.
2. Save a draft through Quick Sale or Make Sale.
3. Confirm direct **Submit Sales Invoice** is not shown.
4. Confirm current Workflow and state are visible.
5. Confirm only actions permitted for the logged-in role are shown.
6. Apply an action that does not submit; confirm state refreshes on the same page.
7. Apply the final action; confirm the invoice becomes submitted and next actions appear.
8. Test a role with no permitted action; confirm the page shows status but does not invent an action.

### D. Unsaved-change dialog layering

1. Open Quick Sale and make unsaved changes.
2. Close the modal.
3. Confirm the discard confirmation renders above the Quick Sale modal/backdrop.
4. Repeat on Quick Purchase.
5. In Professional Selling/Purchasing completion dialogs, edit a draft field and close.
6. Confirm the Sales/Purchase discard confirmation also renders above the completion modal.

### E. Quick Purchase → Record Purchase

1. Open Quick Purchase.
2. Enter Supplier, Branch/Receiving Stock Location as applicable and one item.
3. Save Draft.
4. Confirm route changes to `/app/record-purchase`.
5. Confirm the saved Purchase Invoice is shown.
6. Confirm **Workflow & submission** is on the page.
7. Confirm no Purchase Invoice completion modal opens.
8. Confirm **Continue Editing on Page** is optional rather than automatic.

### F. Direct Purchase without Frappe Workflow

1. Use a role with Purchase Invoice submit permission.
2. Test **Receive & Bill Now** with a valid branch stock location.
3. Confirm **Submit Purchase Invoice** appears.
4. Submit and verify payable plus stock posting through ERPNext.
5. Test **Bill Only** and confirm no stock movement is created.
6. Confirm supplier settlement/payables/output actions after submission.

### G. Direct Purchase with Frappe Workflow

1. Activate a Purchase Invoice Workflow.
2. Save a direct Purchase Invoice.
3. Confirm direct submit is hidden.
4. Confirm current workflow state and permitted actions.
5. Apply an intermediate action and verify same-page refresh.
6. Apply final approval/submission and verify post-submit actions.

### H. Standard Purchase regression

1. Start **Standard Purchase** from Record Purchase.
2. Confirm it routes to Professional Purchasing.
3. Create a Purchase Order.
4. Verify active Purchase Order Workflow takes precedence over direct submit.
5. Continue through Purchase Receipt and source-linked Purchase Invoice.
6. Confirm source-linked invoices remain owned by Professional Purchasing and are not redirected into the generic Direct Purchase editor.

### I. Failure and isolation cases

Verify all of the following fail closed without losing the saved ERPNext draft:

- stale `modified` timestamp;
- workflow state changed by another user;
- user loses submit/Workflow permission;
- invalid Branch or Stock Location;
- document belongs to another Company/Branch scope;
- item is no longer readable/permitted;
- source-linked Purchase Invoice is presented to Direct Purchase;
- submitted document is reopened for editing.

### J. Payment Management and Payment History

1. Open **Payment Management** and confirm historical records are not rendered inline below the transaction workspace.
2. Select Company, Branch and Customer, then click **Payment History**.
3. Confirm routing to `/app/payment-history` and that the Company/Branch/Customer scope is carried into the history page.
4. Click **Review** on a payment and confirm the Payment Review opens immediately in an EdgeSuite popup rather than below the history table.
5. Confirm Submit/Advanced/Close actions remain in the popup footer and submitted/cancelled Payment Entries stay read-only.
4. Return to Payment Management and create a Customer Advance using a Bank mode without Reference No.
5. Confirm the frontend marks Reference No/Reference Date as required and blocks creation with a friendly message; no traceback should be shown.
6. Enter a reference and create the draft.
7. Confirm the success message remains visible even if a later list refresh encounters a recoverable scope issue.
8. Confirm a stale/disabled Branch handoff is replaced by a valid operating Branch scope rather than exposing a raw Branch Setup traceback.
9. Confirm Payment History continues to use permission-aware ERPNext Payment Entry truth and does not mutate submitted payments.

### K. Draft Purchase Order editing

1. Open **Professional Purchasing** and click a draft Purchase Order row.
2. Confirm the review overlay exposes **Edit draft before completion** when the user has write permission.
3. Change Order Date, Terms, Qty, Rate or Required By date and confirm **Save Draft Changes** appears in the footer.
4. Click **Add Item**, search only permitted purchase Items, select an Item and confirm buying rate resolves in the saved Purchase Order context.
5. Confirm the new row inherits the governed Supplier, Branch, Buying Price List and receiving Stock Location. Existing item identity must remain protected.
6. Confirm Company, Supplier, Branch, Buying Price List and Stock Location are not editable from this bounded editor.
7. Save and confirm ERPNext adds the new line, recalculates totals and refreshes the Purchase Order queue.
6. Change a value without saving and attempt Submit/Workflow; confirm completion remains blocked until the draft is saved.
7. Close with unsaved changes and confirm the discard warning appears.
8. Open a submitted Purchase Order and confirm it is read-only in this surface.

### L. Direct-purchase inventory account warning

For **Receive & Bill Now** (Purchase Invoice with Update Stock), ERPNext may replace a row account such as **Stock Received But Not Billed** with the Warehouse inventory account (for example **Stock In Hand**) when the selected account is not the Warehouse/default inventory account. This is ERPNext preserving perpetual-inventory accounting truth. Confirm RetailEdge does not override that correction.

For the normal **Purchase Receipt → Purchase Invoice** flow, the Purchase Invoice should not repost stock merely to avoid this warning; ERPNext's Stock Received But Not Billed clearing flow remains authoritative.

## Focused automated QA

Run:

```bash
bench --site retail.local run-tests --app retailedge --module retailedge.tests.test_quick_entry_transaction_hardening
bench --site retail.local run-tests --app retailedge --module retailedge.tests.test_rir2g1d_standard_sales_invoice_completion_contract
bench --site retail.local run-tests --app retailedge --module retailedge.tests.test_rir2g2b_guided_purchase_invoice_completion_continuity
bench --site retail.local run-tests --app retailedge --module retailedge.tests.test_purchase_workflow_alignment
bench --site retail.local run-tests --app retailedge --module retailedge.tests.test_rir2f2f1_purchase_order_submit_contract
bench --site retail.local run-tests --app retailedge --module retailedge.tests.test_rir2f3f5_payment_history_revisit_contract
bench --site retail.local run-tests --app retailedge --module retailedge.tests.test_rir2g2e1_payment_management_state_contract
```

Then rebuild the focused RetailEdge assets used by Make Sale, Record Purchase and Business Hub, clear site cache, and hard-refresh the browser before manual QA.

## Migration and compatibility

- No schema migration is required.
- Existing ERPNext Sales Invoice and Purchase Invoice drafts remain valid.
- Existing Frappe Workflows are reused; no workflow definition is rewritten.
- Professional Selling and Professional Purchasing completion services remain available for their governed/source-driven workflows.
- Internal app/package identities are unchanged.
