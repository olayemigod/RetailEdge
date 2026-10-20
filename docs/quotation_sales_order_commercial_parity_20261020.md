# Quotation and Sales Order commercial parity — 2026-10-20

## Requirement

Quotation and Sales Order should expose the same governed commercial-calculation experience already used by Make Sale, Quick Sale and Sales Invoice: server-authoritative pricing, automatic promotions, manual line discounts, coupon code, tax category/template, additional document discount, tax/totals preview and pricing breakdown.

## ERPNext / Frappe baseline

RetailEdge currently validates against the v16 line, with CI using Frappe v16.52.0 and ERPNext v16.51.1. The canonical ProcessEdge skill still requires compatibility with the supported v16.50+ baseline.

ERPNext v16.51.1 already exposes the required native fields on both Quotation and Sales Order:

- Selling Price List and Pricing Rule evaluation;
- Tax Category and Sales Taxes and Charges Template;
- Shipping Rule;
- Coupon Code;
- Apply Additional Discount On;
- Additional Discount Percentage / Discount Amount;
- Pricing Rules child state and ERPNext taxes-and-totals calculation.

The ERPNext Pricing Rule documentation explicitly applies pricing rules to Quotation, Sales Order and Sales Invoice. ERPNext discount documentation likewise supports one-off item discounts on Quotation and Sales Order. RetailEdge therefore must reuse ERPNext transaction calculation rather than add a parallel quotation/order arithmetic engine.

Primary references:

- ERPNext v16.51.1 Quotation DocType source: `frappe/erpnext@v16.51.1/erpnext/selling/doctype/quotation/quotation.json`
- ERPNext v16.51.1 Sales Order DocType source: `frappe/erpnext@v16.51.1/erpnext/selling/doctype/sales_order/sales_order.json`
- ERPNext Pricing Rule documentation: https://docs.frappe.io/erpnext/pricing-rule
- ERPNext Applying a Discount documentation: https://docs.frappe.io/erpnext/applying-discount
- ERPNext Quotation documentation: https://docs.frappe.io/erpnext/quotation
- ERPNext Sales Order documentation: https://docs.frappe.io/erpnext/sales-order

## Existing ProcessEdge capability to reuse

RetailEdge already has the governed pieces:

- `sales_commercial_terms.py` for coupon/tax/document-discount validation and application;
- `sales_item_discounts.py` for native ERPNext manual line-discount mapping;
- `sales_commercial_preview.py` for persistence-free ERPNext calculation;
- shared `SalesCommercialTermsControls.vue`;
- shared `SalesCommercialSummary.vue`;
- governed Price List and item-pricing resolution used by Professional Selling.

The current limitation is that the first three are still named and partially permission-scoped around Sales Invoice, while Professional Quotation and Professional Sales Order only expose rate + Shipping Rule and save without the shared commercial terms/preview.

## External workflow benchmark

Mature sales systems keep quotation/order calculations aligned with later invoicing rather than introducing a separate quote-only pricing model:

- Odoo quotations carry pricelists, special line pricing/discounts, taxes and total cost into the accepted sales-order flow.
- Shopify draft orders expose one calculated commercial view containing line discounts, order discounts, taxes and totals, and calculate before persistence/checkout confirmation.

Useful principle for RetailEdge: commercial intent should be visible before commitment, but the platform transaction engine remains authoritative. Browser previews must not become save authority.

References:

- Odoo Sales Quotations: https://www.odoo.com/documentation/18.0/applications/sales/sales/sales_quotations.html
- Shopify Draft Orders: https://help.shopify.com/en/manual/fulfillment/managing-orders/create-orders
- Shopify `draftOrderCalculate`: https://shopify.dev/docs/api/admin-graphql/2026-07/mutations/draftOrderCalculate

## Chosen bounded design

1. Generalize commercial-term permission/search context to supported selling DocTypes: Sales Invoice, Quotation and Sales Order, while preserving current Sales Invoice API defaults.
2. Add a generic persistence-free sales commercial preview entrypoint that builds the requested ERPNext sales document in memory and runs ERPNext missing-values, tax, totals and Pricing Rule logic. Keep the current Sales Invoice preview endpoint as a backward-compatible wrapper.
3. Reuse the existing manual line-discount mapping for Quotation Item and Sales Order Item because ERPNext uses the same native discount fields and pricing semantics.
4. Apply the same commercial terms to Quotation and Sales Order draft creation before insert; ERPNext remains the final validator/calculator.
5. Reuse `SalesCommercialTermsControls` and `SalesCommercialSummary` in Professional Quotation and new standalone Professional Sales Order mode.
6. Make shared UI wording document-neutral/configurable so Quotation and Sales Order do not display invoice-specific labels.
7. Keep `From Submitted Quotation` Sales Order conversion unchanged. It must preserve the accepted submitted Quotation commercial state through ERPNext's native mapper rather than re-price through the new-order editor.
8. Keep Shipping Rule finalization on save in this slice. The live discount/tax preview will disclose that the selected delivery charge is applied when the draft is saved and is not included in the live discount/tax preview, matching the existing Professional Sales Invoice contract.

## Governance and safety

- no direct database-write bypasses;
- no submitted Quotation/Sales Order mutation;
- no permission widening;
- no browser-computed totals submitted as authority;
- Company -> Branch -> Stock Location and Price List governance remain server-validated;
- draft editability and native Advanced access remain unchanged;
- converted Sales Orders preserve submitted Quotation lineage and accepted commercial terms;
- automatic Pricing Rule promotions and manual discounts cannot silently stack where the existing RetailEdge guard rejects that combination.

## Validation focus

- Quotation and Sales Order use the same commercial controls/summary contract as Sales Invoice;
- coupon/tax/additional-discount search respects the target DocType's create/read/write permission;
- line discount percentage/amount map to ERPNext native child fields;
- live preview and saved ERPNext grand total agree before Shipping Rule-only finalization differences;
- stale/failed previews block save for new Quotation/new standalone Sales Order;
- converted Sales Order mode remains independent of new-order preview;
- existing Sales Invoice/Make Sale/Quick Sale behavior remains backward compatible;
- full RetailEdge five-gate validation runs on one exact candidate SHA before merge.
