# Sales Item Discount and Tax Category Engineering Decision

Date: 2026-10-13
Updated: 2026-10-15

## ERPNext / Frappe baseline

Current ERPNext selling already provides the authoritative building blocks required for this slice:

- Sales Invoice Item owns `discount_percentage`, `discount_amount`, `rate`, `amount` and Pricing Rule references.
- ERPNext Pricing Rule is the repeatable promotion mechanism and can apply rates, percentage discounts, fixed discounts or free products based on transaction context.
- Direct transaction discount fields are appropriate for one-off adjustments; RetailEdge should not create a second promotion engine.
- ERPNext's taxes-and-totals controller treats `price_list_rate` plus native margin fields as the pre-discount basis and `rate` as the resolved post-discount rate. ERPNext's own child-item update service represents an entered rate that differs from Price List as an `Amount` margin (`rate - price_list_rate`).
- Tax Category identifies tax treatment context. It does not calculate tax itself.
- Tax Rule and Sales Taxes and Charges Template remain responsible for selecting/carrying tax rows and ERPNext remains responsible for calculating the resulting totals.
- Disabled Tax Categories and tax templates must not be offered for new work, while historical references remain valid.

Primary current references:

- https://docs.frappe.io/erpnext/pricing-rule
- https://docs.frappe.io/erpnext/tax-category
- https://docs.frappe.io/erpnext/tax-rule
- https://docs.frappe.io/erpnext/sales-taxes-and-charges-template
- ERPNext v16 transaction controller, taxes-and-totals controller, child-item update service and Sales Invoice Item source on `frappe/erpnext`.

## External workflow benchmarks

Shopify POS supports line-item and whole-cart custom discounts as percentage or fixed amount and permission-gates staff access. Its current POS documentation explicitly states that a line-item amount discount is applied per unit. This matches ERPNext Sales Invoice Item `discount_amount` semantics.

Square supports manual and automatic percentage/fixed discounts and separately supports discount eligibility. The useful pattern is to distinguish operator-entered discounts from centrally configured automatic promotion rules rather than silently mixing the two.

References:

- https://help.shopify.com/en/manual/sell-in-person/shopify-pos/discount-management/overview
- https://help.shopify.com/en/manual/sell-in-person/shopify-pos/discount-management/applying-discounts
- https://squareup.com/help/us/en/article/3955-create-and-manage-discounts

## Chosen RetailEdge approach

1. **ERPNext remains commercial truth.** Manual input is mapped only to native Sales Invoice Item pricing/discount fields; taxes and final totals are calculated by ERPNext.
2. **Manual input is kept separate from resolved promotion output.** RetailEdge keeps request fields `manual_discount_percentage` and `manual_discount_amount` without adding database fields. Make Sale presents those choices as one **Discount** selector (`Percentage` or `Amount / unit`) plus one **Value** field, then maps that compact editor back to the existing request fields before preview/save.
3. **Selling Rate is preserved as the pre-discount basis while native `rate` remains the resolved post-discount value.** When the operator-entered Selling Rate equals the governed Price List rate, ERPNext calculates the discount directly from that Price List basis. When Selling Rate differs from the governed Price List, RetailEdge preserves the true `price_list_rate` and represents the entered Selling Rate with ERPNext's native `margin_type = Amount` and `margin_rate_or_amount = selling_rate - price_list_rate`, matching ERPNext's own child-item update pattern. If no Item Price exists, the entered Selling Rate becomes the native `price_list_rate` basis for that line. RetailEdge then clears only the intermediate final `rate`, allowing ERPNext to calculate the post-discount rate and Amount. A zero/cleared manual discount leaves the entered Selling Rate untouched.
4. **Saved drafts reopen with the same pre-discount Selling Rate.** RetailEdge exposes the native `rate_with_margin` as the editable Selling Rate when a manual line discount is active, while retaining the actual post-discount `rate` as ERPNext document truth. This avoids applying the same discount twice when a draft is edited again.
5. **Automatic Pricing Rule and manual line discount do not silently stack.** If ERPNext resolves an automatic Pricing Rule on a line where a manual discount was requested, the preview/save fails closed and asks the user to remove the manual discount or review the Pricing Rule.
6. **Existing price governance is reused.** Where the current POS/Profile/Price List context locks the selling rate, RetailEdge also blocks manual line discounts because they reduce the effective selling price. No parallel RetailEdge discount-permission schema is introduced in this slice.
7. **Make Sale owns richer line editing without overloading the item grid.** The compact Discount + Value editor is exposed on persistent Make Sale. The resolved discount percentage is no longer a permanent extra Make Sale column; the effective line Amount and the Sale Summary remain the primary operator feedback. Quick Sale stays compact and keeps its resolved ERPNext discount read-only rather than exposing manual discount editing.
8. **Fixed line discount meaning remains explicit.** The Discount selector uses `Amount / unit` because ERPNext item `discount_amount` is rate/unit based.
9. **Tax Category is a governed Link, not a rate field.** Only enabled categories the current user may use are searchable. Changing category clears stale tax-template rows before ERPNext resolves the new treatment.
10. **Tax templates remain company/category safe.** Search narrows to the active Company and selected Tax Category while still allowing generic templates. Backend validation remains authoritative.
11. **No manual tax-row editor is added.** Account heads, charge types and tax rates remain advanced ERPNext configuration rather than cashier-facing RetailEdge controls.

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
- Confirm a Price List reference of 155,000 with an operator-entered Selling Rate of 23,000 applies a manual discount to 23,000 while retaining 155,000 as the reference value.
- Confirm a manual Selling Rate still supports a manual discount when no configured Item Price exists; the line must not collapse to zero.
- Confirm saved discounted drafts reopen with the pre-discount Selling Rate rather than the already-discounted final rate.
- Confirm a zero/cleared manual discount does not clear or rewrite an entered Selling Rate.
- Confirm switching Discount type clears the old Value so a percentage is never reinterpreted as a currency amount, or vice versa.
- Confirm theme/dark mode and mobile behavior through EdgeSuite/browser persona validation.

## Smallest mergeable boundary

This work remains limited to Make Sale item-level manual discounts plus shared Tax Category handling and their preview/draft-save contracts. Pricing Rule administration, tax-row editing, new discount policy DocTypes, submission/workflow changes and payment/return flows remain out of scope.
