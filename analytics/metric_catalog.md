# RetailEdge Metric Catalog

This catalogue is the semantic contract for RetailEdge reporting and intelligence. Reports may present the same metric in different views, but they must not redefine its source or formula.

## Governance Rules

1. **ERPNext remains accounting truth.** RetailEdge reports may provide operational and analytical views, but General Ledger, Profit and Loss, Accounts Receivable, Accounts Payable and stock ledger/valuation remain authoritative for accounting.
2. **Sales analysis uses submitted Sales Invoices.** Draft and cancelled invoices are excluded. Sales returns/credit notes reverse the original direction rather than being counted as positive sales.
3. **R8 owns transactional profitability semantics.** Recorded item cost is based on Sales Invoice Item incoming_rate × stock_qty; transactional gross profit is analytical contribution, not a replacement for ERPNext accounting profit.
4. **Known commitments are not forecasts.** Payment-term-aware receivable/payable commitments are current known obligations. R12 owns behavioural forecasting and scenarios.
5. **Branch is used only when attribution is authoritative.** Restricted reporting fails closed when Branch scope cannot be applied safely. RetailEdge does not guess a Branch.
6. **Cashier is not document owner.** A cashier dimension may only be exposed from the canonical POS/opening-shift/cashier attribution contract. Sales Invoice.owner is not a cashier proxy.
7. **Cost visibility fails closed.** Cost, gross-profit and margin measures are omitted when the user cannot access profitability intelligence or is covered by the hidden-cost policy.
8. **Payment Mode belongs primarily to settlement analysis.** Invoice sales must not be labelled by payment mode when payment can occur later, be mixed, or be allocated through advances/reconciliation.

## Sales Metrics

| Metric | Definition / Formula | Grain / aggregation | Source | Owner | Caveats |
| --- | --- | --- | --- | --- | --- |
| Sales Value | Submitted non-return Sales Invoice Item base_net_amount | Additive across permitted lines | Sales Invoice + Sales Invoice Item | Sales reporting | Company currency; excludes returns from this positive-sales measure |
| Returns Value | Absolute submitted return/credit-note item base_net_amount | Additive across return lines | Sales Invoice + Sales Invoice Item | Sales reporting | Presented positive for readability; Net Sales applies the negative sign |
| Net Sales | Sales Value − Returns Value | Additive | Submitted Sales Invoice + Sales Invoice Item | Sales reporting | Operational transaction revenue; not P&L income |
| Sold Quantity | Positive quantity on submitted non-return invoice items | Additive operational volume | Sales Invoice Item | Sales reporting | May mix units of measure outside item-level analysis |
| Returned Quantity | Absolute quantity on submitted return items | Additive operational volume | Sales Invoice Item | Sales reporting | May mix units of measure outside item-level analysis |
| Net Quantity | Sold Quantity − Returned Quantity | Additive operational volume | Sales Invoice Item | Sales reporting | May mix units of measure outside item-level analysis |
| Invoice Count | Distinct submitted Sales Invoices represented after current filters | Distinct transaction count | Sales Invoice | Sales reporting | A salesperson dimension can associate one invoice with multiple allocated salespeople; row counts are therefore not additive across salespeople |
| Average Transaction Value | Net Sales ÷ distinct Invoice Count | Recomputed for each result bucket | Sales Invoice + Sales Invoice Item | Sales reporting | Returns are included in Net Sales |
| Average Selling Price | Net Sales ÷ Net Quantity | Item grouping only | Sales Invoice Item | Sales reporting | Not exposed as a general cross-product metric because units of measure may differ |
| Recorded Item Cost | Signed incoming_rate × stock_qty | Additive when cost visibility permits | Sales Invoice Item | R8 Profitability | Returns reverse cost; missing/zero recorded cost remains visible as a data-quality signal |
| Transactional Gross Profit | Net Sales − Recorded Item Cost | Additive analytical contribution | Sales Invoice Item | R8 Profitability | Not ERPNext accounting profit |
| Transactional Gross Margin | Transactional Gross Profit ÷ Net Sales × 100 | Recomputed per bucket | Sales Invoice Item | R8 Profitability | Reported only when Net Sales is positive and cost visibility permits |
| Accounting Gross / Net Profit | ERPNext financial-statement result | Company/accounting-period basis | ERPNext General Ledger / Profit and Loss | ERPNext Accounting | Authoritative accounting profit; do not substitute transactional contribution |

## Sales Analysis Dimensions

The Sales Analysis engine uses one bounded server-side dataset and named presets rather than separate calculation engines.

| Dimension | Authoritative source | Notes |
| --- | --- | --- |
| Day / Week / Month / Quarter / Year | Sales Invoice posting_date | ISO week; period views default chronologically |
| Item | Sales Invoice Item item_code / item_name | Average Selling Price is valid here |
| Item Group | Sales Invoice Item item_group | Quantity may mix UOMs |
| Customer | Sales Invoice customer / customer_name | Permission-scoped submitted invoices |
| Customer Group | Customer master reached from permitted invoice customers | Permission-aware Customer lookup; hidden/unavailable group fails to unspecified |
| Branch | Authoritative Sales Invoice RetailEdge/Branch attribution | Never inferred from document owner |
| Salesperson | ERPNext Sales Team shared R8/R11 allocation contract | Allocated percentages are respected; residual/unassigned buckets stay explicit |
| Warehouse | Sales Invoice Item warehouse | Filtered through Company/Branch operating scope |
| Cashier | **Not currently exposed** | Must use canonical POS/cashier/shift attribution before analytical grouping is enabled |
| Payment Mode | **Not a Sales Analysis dimension** | Belongs to Payment & Settlement Analysis |

## Money and Planning Ownership

| Metric family | Authoritative source | Owner / rule |
| --- | --- | --- |
| Customer Receivables | ERPNext AR allocation / submitted Sales Invoices | Receivables reporting |
| Supplier Payables | ERPNext AP allocation / submitted Purchase Invoices | Payables reporting |
| Customer Advances | Submitted Receive Payment Entries with current unallocated_amount | Advanced Payment Management; no shadow wallet |
| Known Cash Commitments | ERPNext receivable/payable allocation using native payment terms and due dates | 13-week commitments read model |
| Behavioural Cash Forecast | R12 forecasting models and scenarios | Must remain visibly distinct from known commitments |
| Bank Matching / Reconciliation | ERPNext Bank Transaction plus RetailEdge review/handoff state | Bank matching control layer; no parallel bank ledger |
| Stock Position / Movement | ERPNext Bin, Stock Ledger Entry and Item Reorder | Inventory intelligence; no parallel stock engine |

## Report Implementation Contract

- Reporting services must use permission-aware Company/Branch filters and bounded scans.
- Sorting, pagination, print and export must operate on the same governed dataset.
- Named report presets change filters/grouping only; they do not create alternate formulas.
- Drill-downs must lead to the controlling ERPNext/RetailEdge document or workflow.
- Submitted accounting documents must never be mutated by reporting code.
