# R11.5 — Basket & Product Affinity

## Business goal

Help RetailEdge owners and sales managers understand which products are commonly purchased together so they can improve merchandising, bundles, cross-sell prompts and sales conversations without introducing a black-box recommendation engine.

## Source of truth

- Submitted ERPNext Sales Invoice is the basket event.
- Sales Invoice Item is the product membership source.
- Return invoices never establish co-purchase affinity.
- Duplicate lines of the same product on one invoice count once for pair occurrence.
- No accounting document is changed and no parallel sales ledger is created.

## Metrics

- **Together**: number of submitted sale invoices containing both products.
- **Basket Share %**: pair invoice count divided by the number of multi-item baskets in scope.
- **A Invoices / B Invoices**: submitted sale invoices containing each product, including single-product invoices.
- **A → B %**: pair invoice count divided by invoices containing Product A.
- **B → A %**: pair invoice count divided by invoices containing Product B.

These are descriptive association metrics. RetailEdge does not claim that one product causes purchase of another or that a pair is automatically a recommendation.

## Filters

Company, Branch, From Date, To Date, Customer and Salesperson narrow the permitted invoice population.

Product and Product Group act as **affinity anchors** after complete permitted baskets are built. This is deliberate: filtering item rows before pair generation would remove the companion products the report is supposed to discover.

Warehouse remains a source-row scope where supplied.

## Performance and safety

The implementation reuses existing RetailEdge sales-reporting limits:

- maximum submitted invoices scanned: 2,000;
- maximum Sales Invoice Item rows scanned: 10,000.

R11.5 adds two explicit combinatorial controls:

- maximum distinct products in one basket: 50;
- maximum unique generated product pairs: 5,000.

The report fails closed with a clear request to narrow scope when either combinatorial limit is exceeded. It never silently truncates pair generation because silent truncation would make support/confidence metrics misleading.

## Navigation and UX

Basket & Product Affinity belongs under the existing **Insights** group. It does not create another top-level RetailEdge menu group.

The page uses the EdgeSuite single shell. Product links open the native ERPNext Item form in a new tab.

## QA checklist

- Branch-restricted users cannot scan invoices outside permitted scope.
- Customer and Salesperson filters only use permitted submitted invoices.
- Returns do not create pairs.
- Duplicate item lines on one invoice count once for pair occurrence.
- Single-product invoices affect directional confidence denominators but not multi-item basket share denominator.
- Product anchor retains companion products.
- Product Group anchor retains cross-group companion products.
- Per-basket product cap fails closed.
- Global unique-pair cap fails closed.
- Export uses the same dataset contract as the visible report.
- Item links open in new tabs.
