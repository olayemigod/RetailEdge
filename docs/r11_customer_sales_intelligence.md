# R11 — Customer & Sales Intelligence

## Business goal

Give RetailEdge owners and managers actionable customer and sales intelligence over ERPNext truth without creating a second sales, receivables, profitability, discount, or task ledger.

R11 is read-only intelligence. Submitted accounting documents are never mutated.

## Source-of-truth contracts

| Intelligence | Canonical source |
| --- | --- |
| Period sales and returns | Submitted ERPNext Sales Invoice |
| Product/discount transaction detail | Submitted ERPNext Sales Invoice Item |
| Customer relationship start/latest purchase | Submitted non-return Sales Invoice in the same permitted company/branch scope through the selected To Date |
| Current outstanding / overdue | Existing RetailEdge Customer Receivables over current ERPNext outstanding balances |
| Transactional profit | R8 `incoming_rate × stock_qty` contract |
| Salesperson allocation | ERPNext Sales Team through the shared R8/R11 allocation resolver |
| Financial profit | ERPNext Profit and Loss remains financial truth |
| Follow-up metadata | Existing RetailEdge Action Follow Up only |

## R11.1 — Customer Intelligence Foundation

Implemented:

- New vs Returning classification from earliest submitted non-return sale.
- Submitted sales and returns.
- Net sales and average purchase value.
- Last purchase and recency.
- Current receivable exposure.
- Transactional customer profitability when cost visibility permits.
- Permission-aware Company/Branch/Customer scope and bounded pagination/export.

Receivables are explicitly **current exposure**, not a historical balance reconstructed at the selected report end date.

## R11.2 — Customer 360

Customer 360 is an EdgeSuite drill-in, not a replacement Customer master or customer ledger.

Relationship and period behaviour are deliberately separated:

- **First Purchase** and **Latest Purchase** are historical submitted non-return sales through the selected To Date in the same permitted company/branch scope.
- **Days Since Purchase** uses that latest historical purchase.
- **Purchases in Period** and **Average Days Between Purchases** use only the selected reporting window.

Current outstanding, overdue exposure, open invoice count and ageing come from Customer Receivables only. They do not fall back to zero merely because the customer has no sale in the selected period.

Top items and recent invoices remain selected-period evidence. Native Customer, Sales Invoice and Item documents open in new tabs.

## R11.3 — Retention & Opportunity Intelligence

The selected period is compared with the immediately preceding equal-length period.

Implemented signals:

- no current-period purchase after prior-period purchase;
- declining sales value;
- declining purchase frequency;
- current overdue receivable exposure;
- growing sales value;
- growing purchase frequency.

These describe observed behaviour only. RetailEdge does not assert churn or dormancy from a selected window.

## R11.4 — Salesperson Intelligence Alignment

Implemented one shared Sales Team allocation contract:

- positive ERPNext percentages are respected;
- allocations above 100% fail closed;
- positive totals below 100% leave an explicit Unallocated residual;
- all-zero/missing percentages split evenly across named team members;
- no Sales Team produces Unassigned Salesperson.

This same contract is shared with R8 profitability intelligence so salesperson totals do not diverge from transactional profitability attribution.

## R11.5 — Basket & Product Affinity

Implemented bounded co-purchase analysis from submitted non-return Sales Invoices.

- duplicate product lines count once per basket occurrence;
- returns do not create affinity;
- Item and Item Group act as affinity anchors after complete permitted basket construction;
- 50 distinct products per basket and 5,000 unique generated pairs are fail-closed limits;
- association metrics are descriptive, not recommendation or causality claims.

## R11.6 — Discount & Sales Quality

Implemented recorded price-reduction and transactional sales-quality analysis.

When Item, Item Group or Warehouse is selected, **Reference Value, Net Sales, Price Reduction, Return Value, Cost and Margin are calculated only from matching Sales Invoice Item rows**. The filter no longer merely qualifies an invoice and then reports the whole invoice value.

ERPNext invoice-level `base_discount_amount` / `additional_discount_percentage` remain displayed separately and are not apportioned to selected item lines. Returns remain separate from discount leakage.

Cost-restricted users do not fetch `incoming_rate` or `stock_qty`.

## R11.7 — Customer & Sales Action Centre Integration

Implemented aggregate actions for:

- retention follow-up;
- customer growth opportunity;
- high recorded price reduction;
- low/negative transactional margin when cost visibility permits.

Overdue receivables remain owned by the existing Receivables Action Centre source. Basket Affinity remains insight-only.

Action Centre uses lightweight R11 count providers rather than constructing complete report payloads, Sales Team display detail, or invoice-discount detail merely to obtain four counts.

R11 actions are period-dependent. Their follow-up fingerprint therefore opts into a bounded `from_date/to_date` scope. The global fingerprint function preserves the exact original six-field hash whenever no scope is supplied, so existing R4/R9/R10 follow-up identities remain backward-compatible.

Acknowledgement, snooze, assignment and scheduling remain follow-up metadata only; they never resolve the underlying business condition.

## Filters, permissions and smart forms

- Company is permission checked.
- Branch is validated against user access.
- Customer, Item, Item Group, Warehouse and Salesperson selectors use bounded searches.
- Parent filter changes clear dependent invalid values in the EdgeSuite UI.
- Backend validation remains authoritative for business correctness and branch isolation.
- Export uses the same permission/business-rule path as the visible report.

## Performance and safety

- Sales Invoice scans are bounded by the existing 2,000-row contract.
- Sales Invoice Item scans are bounded by the existing 10,000-row contract.
- Sales Team scans are bounded by the existing 5,000-row contract.
- Basket analysis has additional combinatorial fail-closed limits.
- Customer first/latest purchase uses aggregate server-side queries rather than N+1 lookups.
- Customer 360 limits recent invoice/top-item display.
- R11 Action Centre providers compute aggregate counts rather than full report payloads.
- No submitted accounting document is mutated.
- No parallel receivable, customer, sales, discount or profitability ledger is introduced.

## Manual QA gate

R11 remains stacked on R10 and Draft while predecessor QA/promotion is pending. Before R11 browser QA:

1. Promote/reconcile the predecessor through R10.
2. Reconcile R11 without losing its commits.
3. Rerun exact-head Linters and full standalone Frappe v16 CI.
4. Browser-test Company/Branch/customer/product filters, Customer 360 historical-vs-period semantics, current receivables, salesperson allocations, basket affinity, item-scoped sales quality, cost-restricted users, Action Centre period-specific follow-up state, export, native-new-tab drill-through, responsive layout and dark mode.
