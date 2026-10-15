# Sales pricing provenance decision — 2026-10-15

## Problem

Make Sale and Quick Sale currently flatten several different ERPNext pricing effects into generic discount/adjustment figures. That makes a user-entered selling-rate change, an automatic item Pricing Rule, a manual line discount, an automatic transaction Pricing Rule, and a manual invoice discount look interchangeable even though they have different business meanings and calculation bases.

It also makes Grand Total promotions hard to reconcile because ERPNext allocates the transaction discount across net and tax amounts while RetailEdge previously displayed the full discount beside already-adjusted tax.

## ERPNext v16 baseline

ERPNext remains authoritative for Item Price, Pricing Rule, Sales Invoice Item rate/discount fields, transaction-level `additional_discount_percentage` / `discount_amount`, `apply_discount_on`, taxes, rounding and final totals.

ERPNext Pricing Rules can apply at item level or transaction level. Transaction-level price rules write to the same native invoice discount fields used by a manual invoice discount and record the applied Pricing Rule separately. RetailEdge therefore has to preserve provenance when presenting those native values; it must not create a second pricing engine.

## Chosen RetailEdge vocabulary

- Price-list value: governed Item Price basis.
- Item promotion: automatic ERPNext Pricing Rule affecting an item.
- Selling rate adjustment: operator-entered selling-rate difference from the ERPNext-resolved automatic rate.
- Line discount: operator-entered discount on a specific item row.
- Invoice promotion: automatic transaction-level ERPNext Pricing Rule.
- Invoice discount: operator-entered invoice-wide discount.
- Tax/VAT, rounding and Invoice Total: ERPNext-calculated values.

`Price adjustment` is retired from the sale summary because it mixed multiple pricing events into one figure.

## Calculation and display contract

RetailEdge serializes the authoritative in-memory ERPNext Sales Invoice after normal pricing/tax calculation and adds explanation-only provenance fields. No preview data is persisted.

For each item, the preview separates price-list value, automatic item promotion, selling-rate adjustment, line discount and final line amount. Multiple items aggregate those categories independently.

For transaction-level adjustments, RetailEdge classifies a native invoice discount field as `Invoice promotion` when an applied transaction Pricing Rule is present, otherwise as `Invoice discount`.

A manual invoice discount and an automatic invoice promotion are not allowed to silently compete for the same native ERPNext fields. The preview fails closed with a business-facing message if both are requested at the same time.

For `Grand Total` promotion/discount, the summary shows tax and grand total before the invoice-level adjustment, then the invoice promotion/discount, then ERPNext total/rounding. The tax breakdown still exposes the final tax after ERPNext allocation. This keeps the visible arithmetic reconcilable.

For `Net Total` promotion/discount, the summary shows the invoice-level adjustment before the net-after-adjustment and final tax.

## Shared UI boundary

`SalesCommercialSummary.vue` and `SalesCommercialTermsControls.vue` are shared by Make Sale and Quick Sale, so both surfaces receive the same terminology, arithmetic hierarchy and automatic-promotion behavior from one backend preview contract.

No new EdgeSuite primitive is required. Existing EdgeSuite controls and theme tokens remain in use.

## Safety boundary

This change does not:

- modify ERPNext/Frappe core;
- create a parallel promotion or tax engine;
- alter submitted Sales Invoices;
- alter GL, Payment Ledger or Stock Ledger entries;
- persist preview-only provenance;
- change Pricing Rule eligibility semantics;
- permit manual line discounts to silently override an existing automatic item Pricing Rule.

## Regression coverage

The bounded correction covers multi-item invoices, item promotions, manual selling-rate changes, line discounts, transaction-level promotions, manual invoice discounts, Grand Total tax allocation, and the shared Make Sale/Quick Sale presentation contract.
