# RetailEdge Document Action Contract

## Purpose

RetailEdge uses one product-wide meaning for document actions. A list, queue, history, register, dashboard drill-down, or operational workspace must not use **View** as an alias for printing or sharing.

## Action meanings

| Action | RetailEdge meaning |
| --- | --- |
| **View** | Open the saved submitted/cancelled record in the relevant RetailEdge operational review surface. The source document stays read-only and the review may expose only server-authorised next business actions. |
| **Review** | Open an operational review surface when a document still requires review, approval, reconciliation, or another decision. |
| **Edit / Complete** | Open a draft in the appropriate persistent/editor surface and complete it through ERPNext/Frappe Workflow. |
| **Print & Share** | Open **Document Output & Sharing** with the selected supported document preloaded. Print format, PDF, email, WhatsApp handoff, and document selection remain output concerns. |
| **Advanced: ERPNext** | Explicitly open the native ERPNext document or report when native Desk access is permitted. |

## Product-wide rules

1. **View must never route to Document Output & Sharing.**
2. **Document Output & Sharing is share-only.** It has no operational `view` mode.
3. Submitted ERPNext accounting and stock documents are never mutated by View.
4. A View surface may show next actions only when the backend says they are permitted.
5. Draft actions remain separate: a draft uses Review/Edit/Complete rather than pretending to be a submitted View.
6. **Print & Share** is offered only for document types supported by the output registry. It is not mechanically added to every internal operational record.
7. **Advanced: ERPNext** is separate from View and Print & Share.
8. Company, Branch, tenant and role permissions are revalidated by the backend; frontend labels do not grant permission.

## Current operational ownership

### Selling

- Quotation View → RetailEdge selling preview → permitted Sales Order / Invoice actions.
- Sales Order View → RetailEdge selling preview → permitted Delivery / Invoice / payment actions.
- Delivery Note View → RetailEdge delivery preview → permitted Invoice/output actions.
- Sales Invoice View → RetailEdge invoice preview → permitted Payment / Delivery / Return actions.
- Print & Share → Document Output & Sharing.

### Purchasing

- Draft Purchase Order → **Review / Edit**.
- Submitted Purchase Order → **View**, read-only, with permitted Receive Stock / Create Purchase Invoice actions.
- Submitted Purchase Order → separate **Print & Share** → Document Output & Sharing with the Purchase Order preselected.
- Draft Purchase Invoice → **Review & Complete**.
- Submitted Purchase Invoice → **View**, read-only, with permitted Pay Supplier / Supplier Debit Note / Supplier Payables actions.
- Purchase Receipt History is a persistent EdgeSuite page; it exposes **Print & Share**, Create Invoice where permitted, and explicit Advanced ERPNext without inventing an output-based View action.
- A newly submitted Purchase Receipt exposes **Print & Share** beside its permitted next workflow actions.
- Purchase Order, Purchase Receipt and Purchase Invoice output all use the shared Document Output & Sharing workbench.

### Payments

- Draft Payment Entry → **Review**, with standard submit where permitted.
- Submitted/cancelled Payment Entry → **View**, read-only.
- Payment review remains an EdgeSuite popup and does not route to Document Output & Sharing.

### Expenses

- Cashier Expense and Business Expense records use their RetailEdge detail/review surfaces.
- Expense review actions remain workflow/review actions, not print/share aliases.
- Native ERPNext fallback is exposed only as an explicit Advanced action where applicable.

### Stock and Banking

- Stock operational completion/review remains separate from printing.
- Bank statement import/detail and reconciliation review remain EdgeSuite operational surfaces.
- Native records are opened only through explicit Advanced/native controls where the workflow requires them.

## Shared routing rule

Any supported **Print & Share** action must use the shared routing contract. Module code should import:

```javascript
import { openDocumentOutputSharing } from "../documentOutputNavigation";
openDocumentOutputSharing(documentKey, documentName);
```

The navigation utility delegates to `window.retailedge.openDocumentOutputSharing(...)` when the global runtime helper is present and otherwise applies the same share-only target before routing to `document-output-sharing`. This avoids silent no-op clicks on pages where the global helper has not yet attached. Operational View code must never call either output helper.

## Regression protection

`test_retailedge_document_action_contract.py` scans RetailEdge public JavaScript/Vue sources and fails if:

- any output target uses `mode: "view"`;
- an operational `openDocumentOutput(..., "view")` path returns;
- Document Output restores a legacy `outputMode` View branch;
- core Selling, Purchasing and Payment list action semantics regress;
- Purchase Order/Purchase Receipt Print & Share paths stop using the shared output navigation contract or are accidentally merged back into View;
- output target assignment or direct output routing appears outside the two approved shared routing modules.

## Manual QA

For every list or history surface that contains a View action:

1. Click **View**.
2. Confirm the current operational page remains active and an EdgeSuite review/preview opens.
3. Confirm submitted/cancelled source fields are read-only.
4. Confirm only backend-authorised next business actions appear.
5. Close the preview and confirm the list retains its state.
6. Where **Print & Share** exists, invoke it separately.
7. Confirm the route changes to `/app/document-output-sharing`.
8. Confirm the selected document is preloaded while the document selector remains usable.
9. Confirm print/PDF/email/WhatsApp options are visible according to permission/configuration.
10. Confirm **Advanced: ERPNext** is a separate action and is hidden when native Desk is unavailable.
