# RIR2F3F20 — Supplier Document Purchase Invoice EdgeSuite Completion

## Goal

Complete the accepted Supplier Document → ERPNext Purchase Invoice workflow inside EdgeSuite without replacing ERPNext buying or accounting truth.

## Existing Gap

E16 correctly creates an auditable **draft-only** Purchase Invoice from ERPNext's Purchase Order mapper. The Supplier Document Review page then opens that draft in native ERPNext Desk for final review and submission. For an EdgeSuite-only user this leaves the business workflow incomplete after the draft has already been persisted.

Simply hiding the native route would strand the approved draft. F3F20 therefore adds a bounded read-only EdgeSuite review and a standard submit path for the exact immutable handoff.

## Scope

- `retailedge/supplier_document_review.py`
- `retailedge/public/js/supplier_document_review/SupplierDocumentReview.vue`
- reconcile the original draft-only handoff test so the **prepare** endpoint remains draft-only
- focused F3F20 contract test
- this decision document

## Ownership Contract

1. E16 draft preparation remains unchanged in principle: ERPNext `make_purchase_invoice(po.name)` owns Supplier, Company, Purchase Order linkage, remaining items, quantities, rates and taxes.
2. Extraction evidence remains advisory and must never overwrite ERPNext totals, taxes, item values or accounting fields.
3. The EdgeSuite review may load only the exact Purchase Invoice referenced by the immutable Supplier Document Purchase Invoice Handoff.
4. Review revalidates accepted Supplier Document Intake, latest accepted extraction review, submitted Purchase Order, Supplier, Company and Branch authority.
5. Standard submission is permitted only for a draft that:
   - remains linked to the authoritative Purchase Order;
   - has extracted currency available and equal to the ERPNext draft currency;
   - has extracted total available and matching the mapped ERPNext grand total within ₦/currency rounding tolerance of 0.01;
   - does not use Purchase Invoice `Update Stock`;
   - has submit permission for the current user.
6. A mismatch, missing reconciliation evidence, Update Stock, foreign/missing PO linkage, or missing submit permission fails closed. Native Desk-capable users may use the explicit Advanced ERPNext path to investigate; EdgeSuite-only users cannot escape into native Desk.
7. Submit locks the exact Purchase Invoice, rejects a stale review using `modified`, reruns blockers, then calls normal ERPNext `purchase_invoice.submit()`.
8. No direct GL Entry, Stock Ledger Entry, Payment Entry, database commit, submitted-document mutation, or alternate accounting engine is allowed.
9. Already-submitted handed-off invoices return an idempotent submitted result.

## UI Requirements

- After `Prepare Draft PI`, stay in Supplier Document Review and open the EdgeSuite Purchase Invoice review instead of routing to native Desk.
- Existing handed-off invoices expose `Review PI` inside EdgeSuite.
- Show mapped total, extracted total, difference, Supplier, status and mapped item rows.
- Show standard-submit blockers explicitly.
- Native Purchase Order/Purchase Invoice detail/list and DocType/Report menu routes require final `navigation.access.can_use_native_desk`.
- Use the final master Business Hub context fallback.

## Out of Scope

- generic Purchase Invoice editing
- changing mapped quantities, rates, taxes or accounts in EdgeSuite
- Update Stock Purchase Invoice completion
- serial/batch editing
- supplier payment
- Purchase Order mutation
- changing extraction evidence
- schema, patch, migration or data changes

## Tests Required

- E16 prepare endpoint remains draft-only and still uses ERPNext PO mapping.
- Review is bound to the immutable handoff and revalidates Supplier/Company/PO/Branch authority.
- Submit locks the Purchase Invoice and rejects stale `modified`.
- Standard blockers cover missing/mismatched extraction currency/total, Update Stock, PO linkage and submit permission.
- Submit uses only ERPNext `purchase_invoice.submit()`; no direct GL/SLE/Payment/commit/ignore-permission path.
- UI opens EdgeSuite review after draft preparation and can submit from that review.
- Native Purchase Order/Purchase Invoice and DocType/Report routes are final-capability gated.

## Freeze Rule

F3F20 is frozen only when RetailEdge Theme Compatibility, Linters/Semgrep/dependency audit, clean Frappe v16 CI and governed EdgeSuite UI Candidate Compatibility all pass on the same exact head. Manual browser/persona QA remains deferred unless separately executed.
