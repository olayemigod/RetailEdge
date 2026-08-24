# R11 — Customer & Sales Intelligence

## Business goal

Give RetailEdge owners and managers an actionable view of who is buying, who is returning, customer value, current receivable exposure, returns, and customer-level transactional profitability without creating a second sales or accounting truth.

R11 is an intelligence layer over ERPNext and existing RetailEdge reporting. It does not become a CRM, mutate submitted invoices, or create a parallel customer ledger.

## Source-of-truth contracts

| Intelligence | Canonical source |
| --- | --- |
| Period sales and returns | Submitted ERPNext Sales Invoice |
| Customer relationship start | Earliest submitted non-return Sales Invoice in the same permitted company/branch scope |
| Current outstanding / overdue | Existing RetailEdge Customer Receivables, based on current ERPNext Sales Invoice outstanding balances |
| Customer transactional profit | R8 profitability contract: Sales Invoice Item `incoming_rate × stock_qty` |
| Financial profit | ERPNext accounting reports remain the financial truth; customer transactional profit is analytical, not a replacement P&L |
| Salesperson allocation | ERPNext Sales Team; R11 salesperson enhancement must reuse the R8 allocation contract before promotion |

## R11.1 — Customer Intelligence Foundation

Initial foundation provides:

- customer count;
- new vs returning customers;
- submitted sales invoice count;
- return count and return value;
- sales value and net sales;
- average purchase value;
- first purchase date;
- last purchase date and days since last purchase;
- current outstanding;
- overdue outstanding;
- open invoice count and oldest overdue days;
- customer transactional gross profit and margin when RetailEdge cost visibility permits it.

### New vs returning definition

A customer is **New** when the earliest submitted non-return Sales Invoice in the same permitted company/branch scope falls on or after the report `from_date`.

A customer is **Returning** when that first purchase is before `from_date`.

Customer master creation date is deliberately not used because a Customer can be created before or after the actual commercial relationship begins.

Returns do not establish the first purchase date. They reduce period net sales.

### Receivables definition

Receivables are current exposure, not a historical balance reconstructed at the report `to_date`. This matches the existing Customer Receivables contract. The UI and exports must not imply that current outstanding is an as-of-period historical balance.

### Cost visibility

Users restricted from cost price must still be able to use non-cost customer sales intelligence. The backend therefore omits customer cost, gross profit, and gross margin fields when the RetailEdge cost-visibility policy hides cost.

Cost fields must never be fetched merely to hide them in the frontend.

## Planned slices

### R11.2 — Customer 360

Drill into a customer with bounded, permission-aware views of sales history, items and categories purchased, payment/outstanding behaviour, returns, and profitability where permitted.

### R11.3 — Retention & Opportunity Intelligence

Introduce explicit, evidence-based dormancy and declining-frequency/value signals. Thresholds must be configurable or clearly documented. Do not call a customer churned merely because they did not buy inside an arbitrary report window.

### R11.4 — Salesperson Intelligence

Extend existing Salesperson Performance using ERPNext Sales Team allocation. Reuse the R8 allocation rule including explicit residual/unallocated handling; do not use a separate default-100%-per-row calculation.

### R11.5 — Basket & Product Affinity

Bounded invoice-basket analysis for frequently bought-together items and cross-sell signals. Avoid unbounded pair explosions.

### R11.6 — Discount & Sales Quality

Discount and margin-leakage analysis by customer, item, invoice and salesperson using submitted transaction truth and cost visibility.

### R11.7 — Action Centre

Surface customer/sales exceptions and opportunities through the existing RetailEdge Action Centre. Follow-up state must remain separate from the underlying accounting/sales document and must never falsely mark a business condition as resolved.

## Filters and permissions

R11 inherits the RetailEdge sales-reporting controls:

- Company is required and read-permission checked.
- Branch is validated against the current user's permitted branches.
- Customer filters are permission checked.
- Sales Invoice retrieval uses permission-aware bounded queries.
- Branch-restricted users must not fall back to company-wide results when branch attribution is unavailable.
- Dependent selectors must use bounded search rather than preloading every Customer, Sales Person, Item or Warehouse.

## Performance rules

- Reuse existing bounded Sales Invoice and item scan limits.
- Aggregate customer first-purchase dates server-side rather than issuing one query per customer.
- Do not calculate basket affinity in R11.1.
- Do not preload customer masters.
- Export must use the same permission and business-rule path as the visible report.

## Accounting and data safety

- Never mutate submitted Sales Invoices, Payment Entries, GL Entries or other accounting documents.
- Do not create cached customer balances as a competing ledger truth.
- Do not reconstruct historical receivables unless a later slice explicitly implements and reconciles a ledger-based historical contract.
- Preserve ERPNext Profit and Loss as financial truth.

## QA gate

R11 is stacked on R10 and remains Draft while predecessor QA/promotion is pending. Automated validation may run on the stacked head. Before manual/browser QA, reconcile the R11 branch against the promoted R10 predecessor and rerun exact-head linters/CI.

## Manual QA checklist for R11.1

- Global-access user sees permitted company-wide customer metrics.
- Branch-restricted user sees only permitted branch customer activity.
- Explicit Branch filter cannot escape user branch access.
- Customer with first sale in period is New.
- Customer with an earlier submitted sale is Returning.
- Return reduces net sales and does not increase purchase count.
- Return posting date does not replace last purchase date.
- Current outstanding agrees with Customer Receivables for the same Company/Branch/Customer scope.
- Overdue amount and oldest overdue days agree with Customer Receivables.
- Cost-authorized user sees transactional customer profit/margin.
- Cost-restricted user does not receive cost/profit fields in the API payload.
- Export and visible results use identical definitions.
- Links to ERPNext native documents, where retained, open in a new tab; EdgeSuite guided flows remain available without forcing users into native forms.
