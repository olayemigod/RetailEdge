# RetailEdge R11.6 — Discount & Sales Quality

## Business goal

Give owners and managers a practical, read-only view of recorded selling-price reductions and transactional margin quality without inventing a new discount ledger or replacing ERPNext accounting truth.

## Source of truth

- Submitted ERPNext Sales Invoice = invoice/date/customer/return truth.
- Submitted ERPNext Sales Invoice Item = recorded selling reference, net sales and line-discount truth.
- `Sales Invoice.base_discount_amount` and `additional_discount_percentage` = ERPNext additional invoice discount truth.
- `Sales Invoice Item.base_rate_with_margin`, falling back to `base_price_list_rate`, = recorded company-currency reference used for price-reduction analysis.
- R8 `incoming_rate × stock_qty` = transactional cost basis only when RetailEdge cost visibility permits.
- ERPNext Profit and Loss remains financial profit truth.

## Important definitions

### Recorded Price Reduction

For positive-quantity sales lines with a valid recorded reference rate:

`reference value = recorded base rate with margin (or base price-list rate) × quantity`

`recorded price reduction = max(reference value - submitted base net amount, 0)`

The report does not fabricate a discount when the source row has no usable reference. Missing-reference lines are explicitly counted instead.

### Additional Discount

ERPNext invoice-level additional discount is displayed separately from the recorded reference-to-net reduction. It is not added again to the reduction metric, avoiding double counting.

### Returns

Returns are reported separately by count and value. They are not labelled as discount leakage and do not inflate the sales-quality reduction metrics.

### Transactional Margin

When cost visibility permits:

- recorded cost = `incoming_rate × stock_qty`
- transactional gross profit = submitted base net sales - recorded cost
- transactional gross margin = transactional gross profit / submitted base net sales

This is analytical transaction margin, not a replacement for ERPNext financial statements.

## Filters

- Company
- Branch
- From Date / To Date
- Customer
- Salesperson
- Item Group
- Item
- Warehouse
- High Reduction Threshold
- Low Margin Threshold when cost visibility permits

Dependent filters reuse the existing bounded, permission-aware RetailEdge sales-reporting search contract.

## Cost visibility

Cost-restricted users do not merely have cost columns hidden. The backend decides cost visibility before querying Sales Invoice Item and omits `stock_qty` and `incoming_rate` from the query entirely. Cost, gross profit, margin and low-margin actions are therefore unavailable to restricted users by construction.

## Performance and safety

- Reuses the existing 2,000 submitted-invoice scan cap.
- Reuses the existing 10,000 Sales Invoice Item scan cap.
- Branch/company/customer/product/warehouse/salesperson permissions reuse existing sales-reporting validation.
- No Sales Invoice or other submitted accounting document is mutated.
- No discount, margin or sales-quality DocType is introduced.

## EdgeSuite UX

The `Discount & Sales Quality` page is under **Insights**. It uses the shared EdgeSuite report shell, export contract, smart filters, bounded pagination and native drill-through rules. Sales Invoice and Customer native pages open in new tabs.

## Automated coverage

Tests cover:

- reference-to-net price reduction math;
- rate-with-margin preference over plain price-list rate;
- missing reference handling without fabrication;
- explicit high-reduction threshold;
- R8-compatible transactional margin;
- restricted payload omission of cost/profit fields;
- restricted backend query omission of `incoming_rate` and `stock_qty`;
- authorized query inclusion of the required R8 cost inputs.

Exact R11.6 head `d17b5db5c2ff36a30b11f407bad578110a2e0da0` passed Linters and full standalone Frappe v16 CI.
