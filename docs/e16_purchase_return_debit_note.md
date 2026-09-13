# E16 C17 — Guided Purchase Return / Debit Note Handoff

## Goal

Make supplier returns and supplier credit corrections discoverable from RetailEdge Professional Purchasing while ERPNext v16 remains authoritative for returnable quantities, warehouses, taxes, stock, accounting, supplier balances and downstream payment/reconciliation effects.

C17 must not create a second purchase-return, supplier-credit or accounting engine. It is a bounded draft-first handoff into native ERPNext return documents.

## Business value

RetailEdge Professional Purchasing already guides Purchase Request → RFQ → Purchase Order → Purchase Receipt and exposes native purchasing/reporting fallbacks. The remaining operational gap is correction after receipt or supplier billing: users should not need to know which ERPNext return action to find or risk using the wrong document for a physical stock return versus an accounting-only supplier credit.

C17 therefore exposes two explicit workflows and keeps them separate:

1. **Return received goods** — prepare a native Purchase Receipt return for physical goods being sent back to the supplier.
2. **Create supplier debit note** — prepare a native Purchase Invoice return/debit note for a supplier invoice correction or credit.

The user chooses the business intent. RetailEdge never silently creates both documents.

## ERPNext source of truth

### Physical received-goods return

Delegate to ERPNext v16:

`erpnext.stock.doctype.purchase_receipt.purchase_receipt.make_purchase_return(source_name)`

ERPNext remains authoritative for:

- `is_return` / `return_against` linkage;
- negative return quantities and remaining returnable quantity;
- Purchase Order / Purchase Receipt item references;
- warehouse and stock-ledger behavior;
- batch / serial rules;
- taxes, valuation and stock-accounting consequences;
- validation and submission of the eventual Purchase Receipt return.

### Supplier debit note

Delegate to ERPNext v16:

`erpnext.accounts.doctype.purchase_invoice.purchase_invoice.make_debit_note(source_name)`

ERPNext remains authoritative for:

- Purchase Invoice return/debit-note mapping;
- `is_return` / `return_against` linkage;
- Supplier and Company consistency;
- negative return quantities / amounts and remaining returnable values;
- taxes, currency and exchange-rate behavior;
- Update Stock semantics where applicable;
- GL, Stock Ledger and Payment Ledger effects at submission;
- outstanding balance, payment allocation and reconciliation behavior.

Both native mappers ultimately rely on ERPNext's shared sales/purchase return controller. RetailEdge must not reproduce the mapper or calculate returnable quantities itself.

## Scope

### Backend — Professional Purchasing only

Extend `retailedge.professional_purchasing` rather than creating a new service or DocType.

Add bounded, permission-aware source discovery and one draft-preparation action for each workflow.

#### A. Return received goods

Source discovery must show only permitted Purchase Receipts that are reasonable candidates for a physical return:

- submitted Purchase Receipt;
- not itself a return;
- active Operating Company scope;
- active/permitted Branch scope when Branch attribution is available;
- optional Supplier filter where appropriate;
- bounded result count and permission-aware query.

The POST action must:

1. require Purchase Receipt create permission;
2. require read permission on the selected Purchase Receipt;
3. re-read the source server-side;
4. require `docstatus == 1` and reject return/cancelled sources;
5. validate Company and Branch against the current Operating Context and user Branch access;
6. call ERPNext `make_purchase_return(source_name)`;
7. verify the mapped target is a **draft Purchase Receipt return** linked to the exact selected source;
8. verify Supplier and Company match the source;
9. preserve/revalidate Branch attribution without overriding ERPNext stock/warehouse mapping;
10. reject a mapper result with no remaining returnable item quantity;
11. insert the mapped document as the current user, **draft only**;
12. return the native `/app/purchase-receipt/<name>` route for review.

#### B. Create supplier debit note

Source discovery must show only permitted Purchase Invoices that are reasonable candidates for a supplier debit note:

- submitted Purchase Invoice;
- not itself a return;
- active Operating Company scope;
- active/permitted Branch scope when Branch attribution is available;
- optional Supplier filter where appropriate;
- bounded result count and permission-aware query.

The POST action must:

1. require Purchase Invoice create permission;
2. require read permission on the selected Purchase Invoice;
3. re-read the source server-side;
4. require `docstatus == 1` and reject return/cancelled sources;
5. validate Company and Branch against current Operating Context and user Branch access;
6. call ERPNext `make_debit_note(source_name)`;
7. verify the mapped target is a **draft Purchase Invoice return/debit note** linked to the exact selected source;
8. verify Supplier and Company match the source;
9. preserve/revalidate Branch attribution without changing ERPNext Update Stock semantics;
10. reject a mapper result with no remaining returnable item quantity/value;
11. insert the mapped document as the current user, **draft only**;
12. return the native `/app/purchase-invoice/<name>` route for review.

### EdgeSuite Professional Purchasing

Extend the existing Professional Purchasing workspace; do not add another page.

Add a compact **Returns & Supplier Credits** operational section or action area with two clearly differentiated actions:

- `Return Received Goods`
- `Create Supplier Debit Note`

The UI must explain the distinction in plain operational language:

- use **Return Received Goods** when physical received stock is being returned;
- use **Supplier Debit Note** when correcting/crediting a supplier invoice;
- if the selected Purchase Invoice uses Update Stock, the native ERPNext debit-note draft remains authoritative for its stock implications and the user must review it before submission.

Source selectors must use the existing EdgeSuite Link/search pattern and backend-filtered options. Changing Company, Branch or Supplier must clear any now-invalid selected source.

After successful preparation, route directly to the standard ERPNext draft for final quantity, warehouse, tax, stock and accounting review.

## Separation rule — prevent duplicate stock effects

RetailEdge must never automatically chain the two C17 workflows.

A Purchase Receipt return and a Purchase Invoice debit note can represent different business/accounting facts. Creating both automatically can duplicate stock effects, especially where a Purchase Invoice has `update_stock` enabled.

Therefore:

- each action prepares exactly one native ERPNext draft;
- the UI must not offer a combined `Return + Debit Note` automatic action;
- no automatic follow-up document is created after either draft;
- users complete any related second correction explicitly through ERPNext after reviewing the first document and the underlying purchase cycle.

## Permission and Operating Context rules

1. Source read permission and target create permission are mandatory.
2. Browser-supplied Company, Supplier or Branch is never authoritative for the selected source.
3. Source Company must match the active Operating Company when one is active.
4. Source Branch, when attributed, must be permitted and must match the active Operating Branch when one is active.
5. The mapped target must preserve source Company/Supplier identity.
6. Branch attribution may be copied only through the existing RetailEdge Branch-context helpers and must not overwrite native ERPNext warehouse/stock semantics.
7. No `ignore_permissions=True`.

## Safety rules

- Draft only.
- Never mutate, cancel, amend or resave the submitted source document.
- Use ERPNext `make_purchase_return` / `make_debit_note`; do not reproduce return calculations.
- No `.submit()`.
- No `frappe.db.commit()`.
- No direct GL Entry, Stock Ledger Entry or Payment Ledger Entry writes.
- No automatic Payment Entry, Journal Entry, refund, supplier settlement or reconciliation.
- No automatic creation of both a Purchase Receipt return and Purchase Invoice debit note.
- Do not alter ERPNext Update Stock behavior.
- Do not bypass batch, serial, warehouse, tax, currency, accounting-period or returnable-quantity validation.
- Preserve existing Professional Purchasing, Purchase Register and supplier-document flows.

## Files to inspect / expected bounded implementation

Primary:

- `retailedge/professional_purchasing.py`
- `retailedge/public/js/professional_purchasing/ProfessionalPurchasing.vue`
- `retailedge/tests/test_professional_purchasing.py`
- `retailedge/tests/test_professional_purchasing_ui_contract.py`

Add a dedicated focused contract test only if keeping C17 assertions isolated makes the existing test ownership clearer.

Do not modify unrelated accounting, stock, payment, supplier-portal, Professional Selling or reporting services unless a failing compatibility contract proves a narrowly necessary adjustment.

## Tests required

### Backend — Purchase Receipt return

1. Purchase Receipt create permission is required.
2. Source Purchase Receipt read permission is required.
3. Draft/cancelled/already-return source is rejected before mapping.
4. Operating Company/Branch mismatch or denied Branch is rejected before mapping.
5. ERPNext `make_purchase_return` is called exactly once with the selected source name.
6. Non-draft/non-return/wrong-`return_against`/wrong-Supplier/wrong-Company mapper output is rejected.
7. No-remaining-returnable-items mapper output is rejected.
8. Valid mapped return is inserted exactly once as draft only.
9. Submitted source remains unchanged.

### Backend — Purchase Invoice debit note

1. Purchase Invoice create permission is required.
2. Source Purchase Invoice read permission is required.
3. Draft/cancelled/already-return source is rejected before mapping.
4. Operating Company/Branch mismatch or denied Branch is rejected before mapping.
5. ERPNext `make_debit_note` is called exactly once with the selected source name.
6. Non-draft/non-return/wrong-`return_against`/wrong-Supplier/wrong-Company mapper output is rejected.
7. No-remaining-returnable-items/value mapper output is rejected.
8. Valid mapped debit note is inserted exactly once as draft only.
9. `update_stock` is not overridden by RetailEdge.
10. Submitted source remains unchanged.

### Search / source filtering

1. Source queries are bounded and permission-aware.
2. Company/Branch/Supplier filters cascade correctly.
3. Return documents and non-submitted sources are excluded.
4. Denied Branch records are not surfaced.
5. Source options return only the minimum fields needed by the Link UI.

### UI / contract

1. Professional Purchasing contains both explicit actions: `Return Received Goods` and `Create Supplier Debit Note`.
2. The actions remain visibly distinct and no combined automatic return/debit-note action exists.
3. Both use EdgeSuite Link/search patterns and server-side source filtering.
4. Company/Branch/Supplier changes clear invalid return-source selections.
5. Success routes to native ERPNext Purchase Receipt/Purchase Invoice drafts.
6. Existing Purchase Request → RFQ → PO → Receipt flows remain present.
7. No custom posting, refund or accounting editor is introduced.
8. EdgeSuite remains the only guided frontend runtime.

### Safety / source contracts

Assert that C17 introduces no:

- `.submit()`;
- `frappe.db.commit()`;
- `ignore_permissions=True`;
- direct GL/SLE/PLE write;
- source mutation;
- automatic chained Purchase Receipt return + Purchase Invoice debit note creation.

## Migration and backward compatibility

C17 should require no new DocType, schema field or patch. Existing native ERPNext documents remain the system of record.

If implementation can remain within the existing Python service and Vue workspace, no migration should be required beyond the normal asset build used by the branch CI.

Existing users may continue using native ERPNext return/debit-note actions directly; C17 adds a guided entry point and does not remove or override native routes.

## Out of Scope

- custom supplier-credit ledger;
- automatic supplier refund/payment receipt;
- Payment Entry / Journal Entry generation;
- payment reconciliation or allocation;
- supplier dispute/claims workflow;
- landed-cost reversal or adjustment orchestration;
- automated replacement Purchase Order;
- exchange/replacement stock orchestration;
- auto-submit;
- custom return quantity/value calculations;
- direct accounting or stock posting;
- rewriting Purchase Register verification;
- changing existing Supplier Document Intake/Review/Handoff behavior;
- manual QA before cumulative implementation reconciliation.

## Acceptance and execution gate

1. Commit this C17 audit/contract only on the existing PR #53 branch.
2. Freeze its exact head.
3. Require the exact contract head to pass:
   - RetailEdge Theme Compatibility;
   - Linters / pre-commit / Semgrep / vulnerable dependency audit;
   - clean Frappe v16 standalone CI including full RetailEdge tests;
   - governed EdgeSuite UI Candidate Compatibility including build/migrate/full tests.
4. Only after that exact head is green may C17 production implementation begin on the same PR #53 branch.
5. After implementation, freeze a new exact head and repeat the same validation gate before any C18 audit.
6. Manual/browser QA remains deferred to the cumulative consolidated QA branch.
