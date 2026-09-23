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

Requires EdgeSuite UI draft PR #25 (`agent/signature-financial-dashboard-fd1`) or an accepted release containing `EdgeFinancialDashboard`.
