# RetailEdge Financial Dashboard Consumer

This branch upgrades the existing `owner-dashboard` route to the EdgeSuite Signature Financial Dashboard while preserving the dashboard capability key and route compatibility.

## Data authority

- Net Sales: existing Sales by Item provider, using submitted Sales Invoice Item base net amounts.
- Customer Receipts: explicitly labelled **Customer Receipts — Payment Entries** until verified POS, Journal, refund and other settlement coverage is complete.
- Posted Expenses: governed consolidated expense register.
- Receivables / Payables: current outstanding providers without period filters.
- Cash & Bank: current Company balance only where unrestricted Company accounting scope is safe.
- Stock Value and profitability: protected by existing cost visibility.
- Accounting profit: existing profitability/accounting integration only; the dashboard does not derive P&L from sales minus expense-register totals.

Invoice-cohort collection rate and days-to-full-payment are deliberately unavailable until complete allocation semantics are implemented.

## Shared dependency

Requires EdgeSuite UI draft PR #25 (`agent/signature-financial-dashboard-fd1`, restacked head `276ebd20767b5157d2b9de9ee563c39ae404ce3e`) or an accepted release containing `EdgeFinancialDashboard`.


## Business Hub alignment

The existing Sales Invoice Register now exposes both **Net Sales** (tax-exclusive `base_net_total`) and **Net Invoiced** (tax-inclusive `base_grand_total`). Owner/Business Hub financial headlines use Net Sales; Net Invoiced remains separately labelled. The lightweight Business Hub sales trend and Branch mix now aggregate `base_net_total`, so a visual labelled Net Sales no longer uses tax-inclusive invoice totals.


## CI dependency pin

RetailEdge CI, browser persona, upgrade validation and EdgeSuite compatibility checks on this branch use exact EdgeSuite UI commit `276ebd20767b5157d2b9de9ee563c39ae404ce3e`. This prevents the consumer from appearing green against a shared runtime that does not yet contain `EdgeFinancialDashboard`.


## Repeated destination handoff validation

Cached report pages must consume each fresh Business Hub handoff on route activation. The Expense Register now listens for Frappe page activation and refreshes Smart Date, filters and data from the newest handoff, covering the required chart A → report → Back → chart B → same report contract.
