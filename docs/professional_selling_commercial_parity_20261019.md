# Professional Selling commercial parity — 2026-10-19

## Problem

Professional Selling can create a new ERPNext Sales Invoice draft, choose a Selling Price List and Shipping Rule, and redeem Loyalty Points, but its new-invoice dialog does not show the same server-calculated commercial preview and governed invoice discount/tax controls already available in Make Sale and Quick Sale.

The server path is already stronger than the UI: `create_professional_sales_invoice_draft()` delegates new invoice creation to `_create_simple_sales_invoice_draft()`, whose guarded engine resolves governed pricing, applies native/manual item discounts, applies supported commercial terms and lets ERPNext calculate the resulting document before insert. Professional Selling therefore has a presentation/preview parity gap, not a missing pricing engine.

## ERPNext / Frappe baseline

Supported ProcessEdge baseline remains ERPNext/Frappe v16.50.

ERPNext already owns the required commercial semantics:

- Pricing Rules are the repeatable rule engine for rate replacement, percentage/fixed discounts, margins and free products across supported sales transactions.
- One-off item discounts belong on the transaction item rather than in a second RetailEdge promotion engine.
- Invoice-wide additional discount is native ERPNext state and may apply on Net Total or Grand Total, with ERPNext recalculating taxes/totals.
- Coupon Codes are inputs to coupon-based Pricing Rules; the coupon does not define a separate RetailEdge discount.
- Shipping Rule is ERPNext's native mechanism for applying delivery charges to sales transactions.

ERPNext taxes-and-totals remains the calculation authority. RetailEdge must not duplicate commercial arithmetic in the browser.

## Existing ProcessEdge capability to reuse

RetailEdge already has one shared persistence-free endpoint:

`retailedge.sales_commercial_preview.get_sales_invoice_commercial_preview`

It builds an in-memory Sales Invoice, runs the governed price/discount/tax path and serializes ERPNext-calculated values without inserting or committing a document. Make Sale and Quick Sale already use this endpoint together with:

- `SalesCommercialTermsControls.vue`
- `SalesCommercialSummary.vue`
- `retailedge.sales_commercial_terms` search/capability governance

The Professional Selling new-invoice dialog should consume those existing capabilities rather than create a parallel calculation or bespoke tax/discount editor.

## Chosen bounded approach

1. Add the shared commercial terms controls and summary to **new Sales Invoice** mode only.
2. Use `get_sales_invoice_commercial_preview` as the only live total/discount/tax calculation source.
3. Add stale-response protection: an async preview may only apply when its request token and commercial signature still match the current user input.
4. Block saving a new invoice while the required commercial preview is missing, stale, loading or errored.
5. Surface resolved UOM, effective discount and line amount from the preview without using those display fields as save authority.
6. Keep source-document conversion modes unchanged. Quotation / Sales Order / Delivery Note conversions must preserve their accepted/source ERPNext commercial terms rather than reprice through the new-sale editor.
7. Keep Shipping Rule validated and applied by `professional_sales_invoice.py`. The shared commercial preview remains the discount/tax preview owner in this slice; delivery charge finalization continues through ERPNext Shipping Rule on draft creation unless a separately validated persistence-free Shipping Rule preview is proven safe.
8. Loyalty remains separately governed and revalidated on draft save; its displayed estimate must not be treated as authoritative invoice arithmetic.

## Deliberate non-goals

- no second pricing, tax, coupon, promotion or shipping engine;
- no schema/migration;
- no submitted document mutation;
- no change to source conversion semantics;
- no permission widening;
- no new product-specific UI primitive where a shared EdgeSuite/RetailEdge component already exists.

## Validation focus

- new Sales Invoice mode consumes the shared preview/controls and fails closed on stale/failed preview;
- source conversion/return modes remain unchanged;
- Customer / Company / Branch / Stock Location / Price List cascades continue to invalidate stale preview state;
- current ERPNext role/document permissions remain authoritative;
- browser QA checks light/dark/mobile and real pricing/tax/discount data.