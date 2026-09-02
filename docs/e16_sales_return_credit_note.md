# E16 C9A — Guided Sales Return / Credit Note Handoff

## Goal

Make Sales Invoice returns and credit notes discoverable from RetailEdge Professional Selling while ERPNext remains authoritative for return quantities, stock, taxes, accounting, outstanding balances and refund/reconciliation workflows.

## Business value

RetailEdge already supports flexible guided selling and draft Sales Invoice creation/conversion, but there is no equivalent guided path for correcting a submitted sale. ERPNext v16 already provides the correct native `Return / Credit Note` mapper from a submitted Sales Invoice. C9A exposes that mapper safely rather than creating a second refund or credit-note system.

## ERPNext source of truth

C9A must delegate return preparation to:

`erpnext.accounts.doctype.sales_invoice.sales_invoice.make_sales_return(source_name)`

ERPNext v16 delegates this to the shared sales/purchase return controller. Native return validation remains authoritative for:

- `is_return` and `return_against` linkage;
- Customer and Company consistency;
- posting timestamp and exchange-rate rules;
- negative return quantities;
- already-returned and maximum-returnable quantities;
- stock/warehouse rules when Update Stock applies;
- mapped taxes, pricing and packed items;
- consolidated POS invoice restrictions;
- Sales Invoice submission, GL/Stock Ledger and Payment Ledger effects.

## Scope

### Backend

Extend the existing `retailedge.professional_sales_invoice` service only.

1. Add ERPNext v16 `make_sales_return` as the native mapper.
2. Add a submitted Sales Invoice source option for Return / Credit Note mode.
3. Source search must remain bounded, permission-aware and constrained to the active Operating Company/Branch using the existing Professional Selling source/context rules.
4. Exclude return documents and obvious ineligible consolidated POS source invoices from the guided source list.
5. Add one POST action that:
   - requires Sales Invoice create permission;
   - re-reads the selected Sales Invoice server-side;
   - requires a submitted, non-return source;
   - validates Company/Branch against current Operating Context;
   - delegates mapping to ERPNext `make_sales_return`;
   - verifies the mapped target is a draft Sales Invoice return linked to the selected source;
   - verifies Customer and Company still match the source;
   - revalidates mapped stock-location/Branch context using the existing invoice stock-context helper;
   - inserts the mapped Sales Invoice as **draft only** as the current user;
   - returns the normal Sales Invoice route so the user can review and complete the native return form.

### EdgeSuite Professional Selling

Extend the existing `ProfessionalSalesInvoiceDialog.vue` mode switch with one mode:

- `Return / Credit Note`

For this mode:

- show a permission-aware submitted Sales Invoice source Link field;
- explain that ERPNext will prepare a draft return and the source invoice remains submitted/unchanged;
- prepare the draft through the new backend action;
- route the user to the standard ERPNext Sales Invoice draft for quantity, stock, payment/refund and accounting review;
- do not create a second returns page or custom refund editor.

## Out of Scope

- no automatic refund Payment Entry;
- no automatic cash/bank refund;
- no customer-wallet/store-credit ledger;
- no exchange transaction that silently creates a replacement Sales Invoice;
- no auto-submit;
- no mutation/cancellation of the submitted source Sales Invoice;
- no custom return quantity calculation;
- no custom tax reversal calculation;
- no direct GL, Stock Ledger or Payment Ledger writes;
- no POS Invoice/POSNext return-flow replacement;
- no Purchase Return implementation in this slice;
- no broad rewrite of Professional Selling.

For an exchange, users may create the return/credit note and then create the replacement sale as a separate standard selling transaction. A later audit may consider guided exchange orchestration only if it can remain explicit and accounting-safe.

## Permission and Branch rules

1. Current user must have Sales Invoice create permission and read permission on the selected source invoice.
2. Source Company must be readable and match current Operating Company when one is active.
3. Source Branch, when attributed, must be permitted and match the active Operating Branch when one is active.
4. Mapped warehouses must remain Company-safe and Branch-safe through existing `_validate_invoice_stock_context` behavior.
5. Browser-supplied Customer/Company/Branch is never authoritative; all identity comes from the selected submitted Sales Invoice.

## Safety rules

- Draft only.
- Use ERPNext `make_sales_return`; do not reproduce its mapper.
- No `.submit()`.
- No `frappe.db.commit()`.
- No `ignore_permissions=True`.
- No direct GL/SLE/PLE writes.
- Do not mutate the submitted source Sales Invoice.
- Do not automatically create a Payment Entry/refund.

## Files to inspect / change

- `retailedge/professional_sales_invoice.py`
- `retailedge/public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue`
- focused backend tests in the existing Professional Sales Invoice test ownership or one dedicated C9A test file;
- focused source/UI contract test.

## Tests required

Backend:

1. Sales Invoice create permission is required.
2. Source Sales Invoice read permission is required.
3. Draft/cancelled/return source is rejected.
4. Company/Branch Operating Context mismatch is rejected before mapper insertion.
5. ERPNext `make_sales_return` is called with the source invoice name.
6. Non-draft/non-return/wrong-return-against/wrong-Customer/wrong-Company mapped targets are rejected.
7. Mapped stock-location/Branch context is revalidated.
8. Valid mapped return is inserted as draft only.
9. No Payment Entry, GL Entry, Stock Ledger Entry or manual commit is introduced.

UI/source contract:

1. `Return / Credit Note` appears as one Professional Sales Invoice source mode.
2. Return mode uses the existing source Link pattern and the new backend POST action.
3. Existing new/Quotation/Sales Order/Delivery Note modes remain present.
4. No custom Frappe dialog, refund form or payment action is introduced.
5. EdgeSuite runtime remains the only new guided UI runtime.

## Acceptance

Freeze one exact C9A head and require:

- RetailEdge Theme Compatibility green;
- Linters / pre-commit / Semgrep / vulnerable dependency audit green;
- clean Frappe v16 standalone CI green including full RetailEdge tests;
- governed EdgeSuite UI Candidate Compatibility green including build/migrate/full tests.

Manual/browser QA remains deferred to the cumulative consolidated QA branch.
