# Sales Item Discount and Tax Category Engineering Decision

Date: 2026-10-13
Updated: 2026-10-15

## ERPNext / Frappe baseline

Current ERPNext selling already provides the authoritative building blocks required for this slice:

- Sales Invoice Item owns `discount_percentage`, `discount_amount`, `rate`, `amount` and Pricing Rule references.
- ERPNext Pricing Rule is the repeatable promotion mechanism and can apply rates, percentage discounts, fixed discounts or free products based on transaction context.
- Direct transaction discount fields are appropriate for one-off adjustments; RetailEdge should not create a second promotion engine.
- Tax Category identifies tax treatment context. It does not calculate tax itself.
- Tax Rule and Sales Taxes and Charges Template remain responsible for selecting/carrying tax rows and ERPNext remains responsible for calculating the resulting totals.
- Disabled Tax Categories and tax templates must not be offered for new work, while historical references remain valid.

Primary current references:

- https://docs.frappe.io/erpnext/pricing-rule
- https://docs.frappe.io/erpnext/tax-category
- https://docs.frappe.io/erpnext/tax-rule
- https://docs.frappe.io/erpnext/sales-taxes-and-charges-template
- ERPNext v16 transaction controller and Sales Invoice Item source on `frappe/erpnext`.

## External workflow benchmarks

Shopify POS supports line-item and whole-cart custom discounts as percentage or fixed amount and permission-gates staff access. Its current POS documentation explicitly states that a line-item amount discount is applied per unit. This matches ERPNext Sales Invoice Item `discount_amount` semantics.

Square supports manual and automatic percentage/fixed discounts and separately supports discount eligibility. The useful pattern is to distinguish operator-entered discounts from centrally configured automatic promotion rules rather than silently mixing the two.

References:

- https://help.shopify.com/en/manual/sell-in-person/shopify-pos/discount-management/overview
- https://help.shopify.com/en/manual/sell-in-person/shopify-pos/discount-management/applying-discounts
- https://squareup.com/help/us/en/article/3955-create-and-manage-discounts

## Chosen RetailEdge approach

1. **ERPNext remains commercial truth.** Manual input is mapped only to native Sales Invoice Item fields; taxes and final totals are calculated by ERPNext.
2. **Manual input is kept separate from resolved promotion output.** RetailEdge keeps request fields `manual_discount_percentage` and `manual_discount_amount` without adding database fields. Make Sale presents those choices as one **Discount** selector (`Percentage` or `Amount / unit`) plus one **Value** field, then maps that compact editor back to the existing request fields before preview/save.
3. **Automatic Pricing Rule and manual line discount do not silently stack.** If ERPNext resolves an automatic Pricing Rule on a line where a manual discount was requested, the preview/save fails closed and asks the user to remove the manual discount or review the Pricing Rule.
4. **Existing price governance is reused.** Where the current POS/Profile/Price List context locks the selling rate, RetailEdge also blocks manual line discounts because they reduce the effective selling price. No parallel RetailEdge discount-permission schema is introduced in this slice.
5. **Make Sale owns richer line editing without overloading the item grid.** The compact Discount + Value editor is exposed on persistent Make Sale. The resolved discount percentage is no longer a permanent extra Make Sale column; the effective line Amount and the Sale Summary remain the primary operator feedback. Quick Sale stays compact and keeps its resolved ERPNext discount read-only rather than exposing manual discount editing.
6. **Fixed line discount meaning remains explicit.** The Discount selector uses `Amount / unit` because ERPNext item `discount_amount` is rate/unit based.
7. **Tax Category is a governed Link, not a rate field.** Only enabled categories the current user may use are searchable. Changing category clears stale tax-template rows before ERPNext resolves the new treatment.
8. **Tax templates remain company/category safe.** Search narrows to the active Company and selected Tax Category while still allowing generic templates. Backend validation remains authoritative.
9. **No manual tax-row editor is added.** Account heads, charge types and tax rates remain advanced ERPNext configuration rather than cashier-facing RetailEdge controls.

## Deliberate deviations / deferred work

- Shopify/Square-style separate discount-manager permissions or item-level discount-eligibility masters are not copied because ERPNext permissions plus existing RetailEdge selling-rate governance already provide a narrower safe boundary for this MVP slice. A new policy should be added only if real merchant requirements cannot be represented safely with existing governance.
- Automatic and manual discounts are not stacked by default. The fail-closed rule is deliberately more conservative than some POS systems because ERPNext Pricing Rule is authoritative and silent stacking can change margin unexpectedly.
- RetailEdge does not hardcode Nigerian VAT or any tax rate. Tax configuration remains company/localization/accounting setup.
- No schema migration is required.

## Risks and validation focus

- Confirm ERPNext Pricing Rule output is detected consistently after both in-memory preview and actual draft save.
- Confirm read/create/write personas see only permitted Tax Category/template actions and read-only users can still open authorized drafts without write-only API calls.
- Confirm company/category cascade prevents invalid tax-template combinations through direct API attempts as well as UI search.
- Confirm rate-locked POS/Profile contexts reject manual line discounts server-side.
- Confirm percentage and per-unit amount discounts remain mutually exclusive and totals match ERPNext.
- Confirm switching Discount type clears the old Value so a percentage is never reinterpreted as a currency amount, or vice versa.
- Confirm theme/dark mode and mobile behavior through EdgeSuite/browser persona validation.

## Smallest mergeable boundary

This work remains limited to Make Sale item-level manual discounts plus shared Tax Category handling and their preview/draft-save contracts. Pricing Rule administration, tax-row editing, new discount policy DocTypes, submission/workflow changes and payment/return flows remain out of scope.
